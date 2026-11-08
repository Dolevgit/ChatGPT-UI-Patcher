"""Resolve floating chat in Rspack chunks through their native factory runtime."""
from collections import defaultdict
import json
import re

from floating_patch import FEATURE, PREFIX, MARKER, calls, history_edits, jsx_calls, local_binding, properties, require_one
from selector_patch import UnsupportedPatch, bindings, literal, nodes, parser
from sidebar_patch import declarations, enclosing


CHUNK = re.compile(rb'\bexport const __rspack_esm_(?:id=(\d+)|ids=\[(\d+(?:,\d+)*)\]);')
FACTORY = re.compile(rb'(?<=[{,])\s*([\w$]+)\(\s*[\w$]+,\s*[\w$]+,\s*[\w$]+\s*\)\s*\{')
SIDE_LOADER = re.compile(
    rb'Promise\.all\(\[((?:[\w$]+\.e\(\d+\),?)+)\]\)\.then\(([\w$]+)\.bind\(\2,"([^"]+)"\)\)\)\.WorkSideChatContent\b'
)


def call_parts(node):
    if node is None or node.type != 'call_expression':
        return None, []
    callee = node.child_by_field_name('function')
    if callee.type == 'parenthesized_expression':
        sequence = callee.named_children[0]
        if sequence.type == 'sequence_expression' and sequence.named_children[0].text == b'0':
            callee = sequence.named_children[-1]
    return callee, node.child_by_field_name('arguments').named_children


def member(node):
    if node is not None and node.type == 'member_expression':
        obj = node.child_by_field_name('object')
        if obj.type == 'identifier':
            return obj.text.decode(), node.child_by_field_name('property').text.decode()
    return None


class Factory:
    def __init__(self, file, node):
        self.file, self.node = file, node
        self.id = node.child_by_field_name('name').text.decode()
        self.body = node.child_by_field_name('body')
        _, exports, load = node.child_by_field_name('parameters').named_children
        self.load, self.export_target = load.text.decode(), exports.text.decode()
        self.imports = {}
        for name, value in declarations(self.body).items():
            callee, args = call_parts(value)
            if callee is not None and callee.text == load.text and len(args) == 1 and literal(args[0]):
                self.imports[name] = literal(args[0])
        self.exports = {}
        for item in self.body.named_children:
            if item.type != 'expression_statement':
                continue
            for expr in nodes(item):
                callee, args = call_parts(expr)
                if member(callee) != (self.load, 'd') or len(args) < 2 or args[0].text != exports.text:
                    continue
                if args[1].type == 'object':
                    self.exports.update({key: value.child_by_field_name('body')
                                         for key, value in properties(args[1]).items()
                                         if value.type == 'arrow_function'})
                if len(args) == 3 and args[2].type == 'object':
                    self.exports.update(properties(args[2]))
        self.functions = {item.child_by_field_name('name').text.decode(): item for item in self.body.named_children
                          if item.type == 'function_declaration'}

    def ref(self, node):
        pair = member(node)
        if pair and pair[0] in self.imports:
            return self.imports[pair[0]], pair[1]
        return None

    def export(self, function):
        return require_one((key for key, value in self.exports.items()
                            if value == function or self.functions.get(value.text.decode()) == function),
                           'factory function export')

    def local_functions(self):
        return (*self.functions.values(), *(value for value in self.exports.values()
                                           if value.type == 'function_expression'))

    def exported_function(self, key):
        value = self.exports[key]
        if value.type == 'function_expression':
            return value
        return self.functions[value.text.decode()]

    def render_ref(self, ref):
        module, key = ref
        return f'{self.load}({json.dumps(module)})[{json.dumps(key)}]'


class Chunks:
    def __init__(self):
        self.files = defaultdict(list)
        self.chunks = {}
        self.side_loads = set()
        self.starter_exports = []
        self.toolbar = []
        self.history = []

    def scan(self, name, source):
        chunk = CHUNK.search(source[:1024])
        if not chunk:
            return
        self.chunks[name] = {int(id) for id in (chunk[1] or chunk[2]).split(b',')}
        self.starter_exports.extend((name, m.start()) for m in re.finditer(rb'\bstartNewConversation:', source))
        if all(token in source for token in (b'composerController', b'isIndicator', b'isTemporaryChat', b'onToggle')):
            self.toolbar.extend((name, m.start()) for m in re.finditer(rb'\bisIndicator\b', source))
        if all(token in source for token in (b'conversation_sidebar', b'navigationState', b'renderActions')):
            self.history.extend((name, m.start()) for m in re.finditer(rb'["`]conversation_sidebar["`]', source))
        for match in FACTORY.finditer(source):
            self.files[match[1].decode()].append((name, match.start(1)))
        for match in SIDE_LOADER.finditer(source):
            dependencies = tuple(int(i) for i in re.findall(rb'\.e\((\d+)\)', match[1]))
            self.side_loads.add((match[3].decode(), dependencies))


def plan(read, chunks, template, host_template):
    side_id, dependencies = require_one(chunks.side_loads, 'lazy side-chat loader')
    cache = {}

    def tree_for(file):
        if file not in cache:
            cache[file] = parser().parse(read(file)).root_node
        return cache[file]

    def factory_for(file, node):
        node = enclosing(node, {'method_definition'})
        if node is None or node.has_error or node.parent.type != 'object':
            return None
        declaration = node.parent.parent
        if declaration.type == 'variable_declarator' and declaration.parent.parent.type == 'export_statement':
            params = node.child_by_field_name('parameters').named_children
            if len(params) == 3 and all(param.type == 'identifier' for param in params):
                return Factory(file, node)
        return None

    def candidates(module):
        for file, offset in chunks.files.get(module, ()):
            tree = tree_for(file)
            item = factory_for(file, tree.descendant_for_byte_range(offset, offset + len(module)))
            if item is not None and item.node.start_byte == offset:
                yield item

    def functions_at(locations):
        seen = set()
        for file, offset in locations:
            node = tree_for(file).descendant_for_byte_range(offset, offset + 1)
            fn = enclosing(node, {'function_declaration', 'function_expression'})
            if fn is None or (file, fn.start_byte) in seen:
                continue
            seen.add((file, fn.start_byte))
            yield file, fn

    def find(module, preferred=()):
        variants = list(candidates(module))
        matches = [item for item in variants if not chunks.chunks[item.file].isdisjoint(preferred)]
        if matches:
            return require_one(matches, 'loaded factory ' + module)
        if not variants:
            raise UnsupportedPatch('Could not locate native factory ' + module, FEATURE)
        # Replicated factories use one runtime ID. Loading any registered copy
        # supplies the same export namespace, with local names free to vary.
        return variants[0]

    def resolve(ref):
        seen = set()
        while ref and ref not in seen:
            seen.add(ref)
            module, key = ref
            item = find(module, dependencies)
            value = item.exports[key]
            if value.type == 'function_expression':
                return item, value
            if value.type == 'identifier' and value.text.decode() in item.functions:
                return item, item.functions[value.text.decode()]
            ref = item.ref(value)
        raise UnsupportedPatch('Could not resolve a native factory export', FEATURE)

    side = find(side_id, dependencies)
    panel = side.exported_function('WorkSideChatContent')
    _, _, renderer, _ = require_one((c for c in jsx_calls(panel)
                                    if {'conversationId', 'isInlinePreview', 'isTemporaryChat',
                                        'transcriptPresentation'} <= c[3].keys()), 'panel conversation renderer')
    page_id, render_export = side.ref(renderer)
    page = find(page_id, dependencies)
    render_fn = page.exported_function(render_export)
    page_fn = page.exported_function('ChatGptConversationPage')
    if b'chatgpt.conversations' not in page_fn.text or not any(
            c[2].text == render_fn.child_by_field_name('name').text for c in jsx_calls(page_fn)):
        raise UnsupportedPatch('Could not link the regular ChatGPT renderer', FEATURE)
    _, _, provider, _ = require_one((c for c in jsx_calls(panel) if {'route', 'children'} <= c[3].keys()), 'panel route provider')
    host_id, host_export = side.ref(provider)
    frame = require_one((c[2] for c in jsx_calls(panel) if set(c[3]) == {'children'} and side.ref(c[2])),
                        'panel conversation frame')
    side_param = local_binding(panel, 'sideChat')
    decls = declarations(panel.child_by_field_name('body'))
    identity = {}
    for node in nodes(panel):
        if node.type != 'binary_expression' or node.child_by_field_name('operator').text != b'!==':
            continue
        target = member(node.child_by_field_name('right'))
        if target and target[0] == side_param and target[1] in ('accountId', 'userId'):
            hook, args = call_parts(decls.get(node.child_by_field_name('left').text.decode()))
            if hook is not None and len(args) == 1 and side.ref(hook) and side.ref(args[0]):
                identity[target[1]] = (side.ref(hook), side.ref(args[0]))
    if set(identity) != {'accountId', 'userId'}:
        raise UnsupportedPatch('Could not resolve the native panel identity gate', FEATURE)

    path = require_one({side.ref(callee) for call, _, _ in calls(panel)
                        for callee, args in [call_parts(call)] if side.ref(callee) and len(args) == 1
                        and member(args[0]) == (side_param, 'conversationId')}, 'native conversation path')

    edits = defaultdict(list)

    def edit(factory, start, end, replacement):
        edits[factory.file].append(dict(start=start, end=end, replacement=replacement, feature=FEATURE))

    def append(factory, code):
        offset = factory.body.end_byte - 1
        edit(factory, offset, offset, ';\n' + code + '\n')

    # The renderer factory's sibling supplies the ordinary rename UI. Follow
    # its bindings to the metadata atoms and the native action exports.
    rename_candidates = []
    for module in chunks.files:
        if not any(file == page.file for file, _ in chunks.files[module]):
            continue
        for file, offset in chunks.files[module]:
            if file != page.file:
                continue
            tree = cache[file]
            node = enclosing(tree.descendant_for_byte_range(offset, offset + len(module)), {'method_definition'})
            if node is None or node.start_byte != offset or node.parent.parent.type != 'variable_declarator':
                continue
            if all(token in node.text for token in (b'protectedProjectId', b'draftKey', b'requireNonEmpty', b'previousTitle')):
                item = Factory(file, node)
                for fn in item.local_functions():
                    for call, _, _ in calls(fn):
                        callee, args = call_parts(call)
                        if item.ref(callee) and len(args) == 1 and args[0].type == 'object':
                            props = properties(args[0])
                            if {'scope', 'conversationId', 'previousTitle', 'title'} <= props.keys():
                                rename_candidates.append((item, fn, props, item.ref(callee)))
    actions, rename_ui, rename_props, rename = require_one(rename_candidates, 'regular conversation rename')
    action_module = find(rename[0], dependencies)
    delete_fn = require_one((fn for fn in action_module.local_functions()
                            if b'safeDelete' in fn.text and any(literal(n) == '/conversation/id/{conversation_id}'
                                                               for n in nodes(fn))), 'native delete action')
    remove = action_module.id, action_module.export(delete_fn)

    rename_decls = declarations(rename_ui.child_by_field_name('body'))
    lookup_name, _ = call_parts(rename_decls[member(rename_props['conversationId'])[0]])
    lookup = actions.functions[lookup_name.text.decode()]
    metadata = {}
    for call, callee, args in calls(lookup):
        if len(args) == 2 and actions.ref(args[0]) and callee.type == 'member_expression':
            metadata[callee.child_by_field_name('property').text.decode()] = actions.ref(args[0])
    server, query = metadata['get'], metadata['snapshot']
    selection = rename_decls[rename_props['previousTitle'].text.decode()]
    if selection.type != 'ternary_expression':
        raise UnsupportedPatch('Could not resolve the native live title', FEATURE)
    has_title = actions.ref(call_parts(selection.child_by_field_name('condition'))[1][0])
    title = actions.ref(call_parts(selection.child_by_field_name('consequence'))[1][0])

    # Resolve the ordinary New Chat action by its published name and follow
    # the assignment that supplies the new draft ID.
    starter_candidates = {}
    for file, offset in chunks.starter_exports:
        item = factory_for(file, tree_for(file).descendant_for_byte_range(offset, offset + 1))
        if item and 'startNewConversation' in item.exports:
            starter_candidates[file, item.id] = item
    starter = require_one(starter_candidates.values(), 'new conversation factory')
    start_fn = starter.exported_function('startNewConversation')
    create = require_one({starter.ref(call_parts(n.child_by_field_name('right'))[0]) for n in nodes(start_fn)
                          if n.type == 'assignment_expression'
                          and n.child_by_field_name('left').type == 'member_expression'
                          and n.child_by_field_name('left').child_by_field_name('property').text == b'initialChatGptConversationId'
                          and starter.ref(call_parts(n.child_by_field_name('right'))[0])}, 'ordinary draft initializer')

    render_decls = declarations(render_fn.child_by_field_name('body'))
    reader = require_one({page.ref(callee) for call, _, _ in calls(render_fn)
                          for callee, args in [call_parts(call)] if len(args) == 2
                          and page.ref(callee) and page.ref(args[0]) == server}, 'server-ID subscription hook')
    turn = require_one((properties(node) for node in nodes(render_fn) if node.type == 'object'
                        and {'pendingSubmission', 'threadMapping', 'isStreaming'} <= properties(node).keys()), 'native turn status')

    def read_atom(value):
        callee, args = call_parts(value)
        if page.ref(callee) == reader and len(args) == 2:
            return page.ref(args[0])
        return None

    pending_condition = turn['pendingSubmission'].child_by_field_name('condition')
    pending = require_one({read_atom(render_decls.get(n.text.decode())) for n in nodes(pending_condition)
                           if n.type == 'identifier' and read_atom(render_decls.get(n.text.decode()))},
                          'pending submission atom')
    activity = turn['isStreaming']
    while activity.type == 'binary_expression' and activity.child_by_field_name('operator').text == b'&&':
        activity = activity.child_by_field_name('right')
    assignments = defaultdict(list)
    for node in nodes(render_fn):
        if node.type == 'assignment_expression':
            left = node.child_by_field_name('left')
            if left.type == 'identifier':
                assignments[left.text.decode()].append(node.child_by_field_name('right'))
    statuses = set()
    pending_values = [activity]
    visited = set()
    while pending_values:
        value = pending_values.pop()
        if value is None or value.start_byte in visited:
            continue
        visited.add(value.start_byte)
        if value.type == 'identifier':
            key = value.text.decode()
            pending_values.extend([render_decls.get(key), *assignments[key]])
        else:
            callee, args = call_parts(value)
            if page.ref(callee) and len(args) == 1 and args[0].type == 'identifier':
                atom = read_atom(render_decls.get(args[0].text.decode()))
                if atom:
                    statuses.add((page.ref(callee), atom))
    streaming, status = require_one(statuses, 'native streaming status')

    rename_fn = action_module.exported_function(rename[1])
    updater = require_one({action_module.ref(callee) for call, _, _ in calls(rename_fn)
                           for callee, args in [call_parts(call)] if action_module.ref(callee) and len(args) == 1
                           and args[0].type == 'object' and {'scope', 'conversationId', 'title'} <= properties(args[0]).keys()},
                          'native title updater')
    updater_module, update = resolve(updater)
    provisional_flag = local_binding(update, 'onlyIfProvisional')
    provisional = require_one({updater_module.ref(call_parts(n.child_by_field_name('right'))[0])
                               for n in nodes(update) if n.type == 'binary_expression'
                               and n.child_by_field_name('operator').text == b'||'
                               and n.child_by_field_name('left').text.decode() == '!' + provisional_flag
                               and updater_module.ref(call_parts(n.child_by_field_name('right'))[0])},
                              'provisional title predicate')
    confirm = require_one({page.ref(c[2]) for fn in page.local_functions() for c in jsx_calls(fn)
                           if {'open', 'onOpenChange', 'isDeleting', 'onConfirm', 'title'} <= c[3].keys()
                           and page.ref(c[2])}, 'delete confirmation')
    scope_hook, scope_atom = require_one({
        (page.ref(callee), page.ref(args[0])) for key, value in render_decls.items()
        for callee, args in [call_parts(value)]
        if len(args) == 1 and page.ref(callee) and page.ref(args[0])
        and re.search(rb'\b' + re.escape(key.encode()) + rb'\.get\(', render_fn.text)
    }, 'ChatGPT scope hook')
    react = require_one({n.child_by_field_name('object').text.decode() for n in nodes(render_fn)
                         if n.type == 'member_expression' and n.child_by_field_name('property').text == b'useState'},
                        'React hooks runtime')
    jsx = require_one({c[1] for c in jsx_calls(render_fn)}, 'ChatGPT JSX runtime')
    portal = require_one({page.imports[obj] for n in nodes(page.body) if (pair := member(n))
                          for obj, key in [pair] if key == 'createPortal' and obj in page.imports},
                         'native portal runtime')

    # Mount from the side-chat factory. The native runtime can register any
    # copy of the page factory, so use its existing renderer export.
    react_module, jsx_module = page.imports[react], page.imports[jsx]
    replacements = {'__REACT__': f'{side.load}({json.dumps(react_module)})',
                    '__JSX__': f'{side.load}({json.dumps(jsx_module)})',
                    '__SCOPE__': f'(0,{side.render_ref(scope_hook)})({side.render_ref(scope_atom)})',
                    '__MARKER__': json.dumps(MARKER), '__INITIALIZE__': ''}
    refs = {'__PROVIDER__': side.ref(provider), '__FRAME__': side.ref(frame), '__PATH__': path,
            '__RENDERER__': (page_id, render_export),
            '__CREATE__': create, '__RENAME__': rename, '__DELETE__': remove, '__SERVER__': server,
            '__QUERY__': query, '__HAS_TITLE__': has_title, '__TITLE__': title, '__READ__': reader,
            '__PENDING__': pending, '__STATUS__': status, '__IS_STREAMING__': streaming,
            '__PROVISIONAL__': provisional, '__CONFIRM__': confirm}
    for key, (hook, atom) in identity.items():
        label = 'ACCOUNT' if key == 'accountId' else 'USER'
        refs[f'__{label}_ATOM__'] = atom
        replacements[f'__{label}__'] = f'(0,{side.render_ref(hook)})({side.render_ref(atom)})'

    # Follow the navigation hook used by the conversation page itself.
    page_decls = declarations(page_fn.child_by_field_name('body'))
    navigate = require_one({page.ref(call_parts(page_decls.get(callee.text.decode()))[0])
                            for call, _, _ in calls(page_fn) for callee, args in [call_parts(call)]
                            if callee.type == 'identifier' and args and page.ref(call_parts(args[0])[0]) == path
                            and page.ref(call_parts(page_decls.get(callee.text.decode()))[0])},
                           'conversation navigation hook')
    refs['__NAVIGATE_HOOK__'] = navigate

    toolbar_factories = {}
    for file, fn in functions_at(chunks.toolbar):
        try:
            for key in ('composerController', 'conversationId', 'isIndicator', 'isTemporaryChat', 'onToggle'):
                local_binding(fn, key)
        except UnsupportedPatch:
            continue
        toolbar = factory_for(file, fn)
        if toolbar is None:
            continue
        top_level = declarations(toolbar.body)
        icon = require_one({(c[1], c[2].text.decode(), c[3]['asset'].text.decode()) for c in jsx_calls(fn)
                            if 'asset' in c[3] and c[3]['asset'].text.decode() in top_level}, 'temporary-chat icon')
        button = require_one({c[2].text.decode() for c in jsx_calls(fn) if literal(c[3].get('color')) == 'ghostActive'
                              and literal(c[3].get('size')) == 'toolbar'}, 'temporary-chat toolbar button')
        toolbar_factories[file, toolbar.id] = toolbar
        runtime, component, asset = icon
        append(toolbar, f"""
function __customFloatingTemporaryIcon(props) {{return {runtime}.jsx({component},{{...props,asset:{asset}}})}}
function __customFloatingButton(props) {{return {runtime}.jsx({button},{{color:"ghostActive",size:"toolbar",uniform:true,...props}})}}
{toolbar.load}.d({toolbar.export_target},{{__customFloatingButton:()=>__customFloatingButton,__customFloatingTemporaryIcon:()=>__customFloatingTemporaryIcon}});
""")
    toolbar_id = require_one({item.id for item in toolbar_factories.values()}, 'temporary-chat toolbar factory')
    refs['__BUTTON__'] = toolbar_id, '__customFloatingButton'
    refs['__TEMP_ICON__'] = toolbar_id, '__customFloatingTemporaryIcon'

    for key, ref in refs.items():
        expr = side.render_ref(ref)
        replacements[key] = f'(0,{expr})'
    rendered = render_template(template, replacements)
    additions = rendered + f"""
function __customFloatingPortal(props) {{return {side.load}({json.dumps(portal)}).createPortal(
    {replacements['__JSX__']}.jsx(__customFloatingPanel,props),document.body)}}
{side.load}.d({side.export_target},{{__customFloatingPanel:()=>__customFloatingPortal}});
"""
    require_one(candidates(side_id), 'floating panel factory')
    append(side, additions)

    modules = ({ref[0] for ref in refs.values()} | {hook[0] for hook, _ in identity.values()}
               | {portal, react_module, jsx_module, scope_hook[0], scope_atom[0]})
    required_chunks = set(dependencies)
    for module in sorted(modules):
        ids = chunks.chunks[find(module, dependencies).file]
        if ids.isdisjoint(required_chunks):
            required_chunks.add(min(ids))

    host_body, history_template = host_template.split('// Floating chat history helpers.\n', 1)
    rows = []
    for file, fn in functions_at(chunks.history):
        try:
            for key in ('conversationId', 'conversationOrigin', 'navigationState', 'statusState', 'title', 'route', 'href'):
                local_binding(fn, key)
        except UnsupportedPatch:
            continue
        item = factory_for(file, fn)
        if item:
            for row in jsx_calls(fn):
                if {'title', 'ariaLabel', 'onClick', 'renderActions', 'statusState'} <= row[3].keys():
                    rows.append((item, fn, row))
    row_factory_id = require_one({item.id for item, _, _ in rows}, 'ChatGPT history row factory')
    for item in candidates(row_factory_id):
        fn, row = require_one(((fn, row) for factory, fn, row in rows if factory.file == item.file),
                              'ChatGPT history row')
        edits[item.file].extend(history_edits(fn, row))
        # History can render before the lazy toolbar chunk has loaded.
        # Keep its badge local to the sidebar factory.
        runtime = row[1]
        history = history_template.split('function __customFloatingTemporaryIcon', 1)[0]
        history += f"""
function __customFloatingTemporaryIcon(props) {{
  return {runtime}.jsx("svg",{{...props,viewBox:"0 0 16 16",fill:"none",stroke:"currentColor",
    children:{runtime}.jsx("circle",{{cx:8,cy:8,r:5.5,strokeDasharray:"2 2"}})}});
}}
"""
        history += 'function __customFloatingHistoryTitle' + history_template.split(
            'function __customFloatingHistoryTitle', 1)[1].split('export {', 1)[0]
        append(item, render_template(history, {'__MARKER__': json.dumps(MARKER), '__JSX_FACTORY__': f'(()=>{runtime})'}))

    for host in candidates(host_id):
        host_fn = host.exported_function(host_export)
        for key in ('route', 'children'):
            local_binding(host_fn, key)
        host_jsx = require_one({c[1] for c in jsx_calls(host_fn)}, 'route provider JSX runtime')
        # React is read by the route provider through its existing runtime.
        host_react = require_one({obj for n in nodes(host_fn) if (pair := member(n))
                                  for obj, key in [pair] if key == 'useContext' and obj in host.imports},
                                 'route provider React runtime')
        load = host.load
        chunk_loads = ','.join(f'{load}.e({id})' for id in sorted(required_chunks))
        lazy = f'Promise.all([{chunk_loads}]).then(()=>{load}({json.dumps(side.id)}))'
        name = host_fn.child_by_field_name('name')
        body = render_template(host_body, {'__HOST__': name.text.decode(), '__REACT_FACTORY__': f'(()=>{host_react})',
                                           '__JSX_FACTORY__': f'(()=>{host_jsx})', '__LOAD_PANEL__': lazy,
                                           '__MOUNT_PANEL__': 'panel'})
        edit(host, name.start_byte, name.end_byte, PREFIX + 'NativeHost')
        append(host, body)
    return dict(edits)


def render_template(template, replacements):
    for key, value in replacements.items():
        template = template.replace(key, value)
    if re.search(r'__[A-Z_]+__', template) or parser().parse(template.encode()).root_node.has_error:
        raise UnsupportedPatch('Could not construct bundled floating-chat components', FEATURE)
    return template
