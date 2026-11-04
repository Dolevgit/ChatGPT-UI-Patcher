"""Discover the native product selector from JavaScript syntax, not build IDs."""
import hashlib
import re
from tree_sitter import Language, Parser
import tree_sitter_javascript


class UnsupportedPatch(RuntimeError):
    def __init__(self,message='',feature=None):
        super().__init__(message)
        self.feature=feature


def parser():
    return Parser(Language(tree_sitter_javascript.language()))


def nodes(root):
    pending = [root]
    while pending:
        item = pending.pop()
        yield item
        pending.extend(reversed(item.named_children))


def literal(node):
    if node is None or node.type not in ('string', 'template_string'):
        return None
    raw = node.text
    if b'${' in raw or b'\\' in raw:
        return None
    return raw[1:-1].decode('utf-8')


def bindings(pattern):
    result = {}
    for item in pattern.named_children:
        if item.type == 'shorthand_property_identifier_pattern':
            result[item.text.decode()] = item.text.decode()
        elif item.type == 'pair_pattern':
            key = item.child_by_field_name('key')
            value = item.child_by_field_name('value')
            name = literal(key) if key.type == 'string' else key.text.decode()
            if value.type == 'assignment_pattern': value = value.child_by_field_name('left')
            if value.type == 'identifier': result[name] = value.text.decode()
    return result


def analyze(source):
    tree = parser().parse(source)
    candidates = []
    visited = set()
    for match in re.finditer(rb'\bcodexAvailable\b', source):
        node = tree.root_node.descendant_for_byte_range(match.start(), match.end())
        while node and node.type != 'function_declaration': node = node.parent
        if node is None or node.start_byte in visited: continue
        visited.add(node.start_byte)
        if node.has_error: continue
        scope = node.parent
        # Bundled modules can put their top-level declarations inside a factory method.
        in_factory = (scope.type == 'statement_block'
                      and scope.parent.type == 'method_definition'
                      and scope.parent.parent.type == 'object')
        if scope.type not in ('program', 'export_statement') and not in_factory: continue
        body = node.child_by_field_name('body')
        params = node.child_by_field_name('parameters').named_children
        if len(params) != 1: continue
        props = {}
        local_names = set()
        if params[0].type == 'object_pattern': props = bindings(params[0])
        for item in nodes(body):
            if item.type == 'variable_declarator':
                name = item.child_by_field_name('name')
                value = item.child_by_field_name('value')
                if name.type == 'identifier': local_names.add(name.text.decode())
                elif name.type == 'object_pattern':
                    bound = bindings(name)
                    local_names.update(bound.values())
                    if value and params[0].type == 'identifier' and value.text == params[0].text:
                        props.update(bound)
        required = {'codexAvailable', 'mode', 'disabled', 'onModeSelect', 'onNewChat', 'workModeAccess'}
        if not required <= props.keys(): continue
        strings = {literal(n) for n in nodes(body) if n.type in ('string', 'template_string')}
        if not {'sidebarElectron.productMode.trigger', 'sidebarElectron.productMode.home'} <= strings: continue
        runtimes = set()
        mode_calls = {}
        for item in nodes(body):
            if item.type != 'call_expression': continue
            fn = item.child_by_field_name('function')
            args = item.child_by_field_name('arguments')
            if fn is None or args is None: continue
            # Compilers emit both runtime.jsx(...) and (0,runtime.jsx)(...).
            for member in nodes(fn):
                if member.type != 'member_expression': continue
                obj = member.child_by_field_name('object')
                prop = member.child_by_field_name('property')
                if obj and prop and obj.type == 'identifier' and prop.text in (b'jsx', b'jsxs'):
                    runtimes.add(obj.text.decode())
            if fn.type == 'identifier' and len(args.named_children) == 1:
                mode = literal(args.named_children[0])
                if mode in ('work', 'codex'):
                    mode_calls.setdefault(fn.text.decode(), set()).add(mode)
        if len(runtimes) != 1 or not any({'work', 'codex'} <= modes for modes in mode_calls.values()): continue
        runtime = next(iter(runtimes))
        if runtime in local_names or (params[0].type == 'identifier' and runtime == params[0].text.decode()): continue
        candidates.append({'function': node.child_by_field_name('name').text.decode(), 'runtime': runtime,
                           'start': node.start_byte, 'end': node.end_byte,
                           'selectorSha256': hashlib.sha256(source[node.start_byte:node.end_byte]).hexdigest()})
    return candidates


def rewrite(source, plan, template):
    if hashlib.sha256(source).hexdigest() != plan['uiHash']:
        raise UnsupportedPatch('The UI changed during preparation')
    start, end = plan['start'], plan['end']
    if hashlib.sha256(source[start:end]).hexdigest() != plan['selectorSha256']:
        raise UnsupportedPatch('The product selector changed during preparation')
    replacement = template.replace('__SELECTOR__', plan['function']).replace('__JSX__', plan['runtime']).replace('__BUG_FIXES__','true' if plan.get('fixNavigation') else 'false').encode('utf-8')
    parsed = parser().parse(replacement)
    functions = [n for n in parsed.root_node.named_children if n.type == 'function_declaration']
    if parsed.root_node.has_error or len(functions) != 1:
        raise UnsupportedPatch('Could not construct the tabs component')
    return source[:start] + replacement + b'\n' + source[end:]
