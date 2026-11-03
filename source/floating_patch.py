"""Discover a regular ChatGPT floating panel through native module contracts."""
import posixpath
import re
import json

from selector_patch import parser, nodes, literal, bindings, UnsupportedPatch
from sidebar_patch import properties as paired_properties, declarations as local_declarations


FEATURE = 'floating_chat'
PREFIX = '__customFloating'
MARKER = '---temporary---'


def properties(obj):
    result = paired_properties(obj)
    result.update({n.text.decode():n for n in obj.named_children if n.type == 'shorthand_property_identifier'})
    return result


def require_one(values, label):
    values = list(values)
    if len(values) != 1:
        raise UnsupportedPatch('Could not identify one native ' + label, FEATURE)
    return values[0]


class Module:
    def __init__(self, name, source):
        self.name, self.source = name, source
        self.root = parser().parse(source).root_node
        self.imports, self.exports, self.functions = {}, {}, {}
        for node in self.root.named_children:
            if node.type == 'import_statement':
                target = literal(node.child_by_field_name('source'))
                if target is None or not target.startswith('./'):
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                if not target.startswith('webview/'):
                    raise UnsupportedPatch('Unexpected floating-chat module path', FEATURE)
                for item in nodes(node):
                    if item.type != 'import_specifier': continue
                    original = item.child_by_field_name('name').text.decode()
                    alias = item.child_by_field_name('alias')
                    self.imports[(alias or item.child_by_field_name('name')).text.decode()] = (target, original)
            if node.type == 'export_statement':
                if node.child_by_field_name('source') is not None:
                    raise UnsupportedPatch('Unsupported floating-chat re-export', FEATURE)
                for item in nodes(node):
                    if item.type != 'export_specifier': continue
                    original = item.child_by_field_name('name')
                    alias = item.child_by_field_name('alias')
                    self.exports[(alias or original).text.decode()] = original.text.decode()
            function = node if node.type == 'function_declaration' else None
            if node.type == 'export_statement':
                function = next((n for n in node.named_children if n.type == 'function_declaration'), None)
                if function is not None:
                    key = function.child_by_field_name('name').text.decode()
                    self.exports[key] = key
            if function is not None:
                key = function.child_by_field_name('name').text.decode()
                if key in self.functions:
                    raise UnsupportedPatch('Duplicate floating-chat function', FEATURE)
                self.functions[key] = function


def calls(function):
    for node in nodes(function.child_by_field_name('body')):
        if node.type == 'call_expression':
            yield node, node.child_by_field_name('function'), node.child_by_field_name('arguments').named_children


def jsx_calls(function):
    for node, callee, args in calls(function):
        if len(args) < 2 or args[1].type != 'object': continue
        members = [n for n in nodes(callee) if n.type == 'member_expression'
                   and n.child_by_field_name('property').text in (b'jsx', b'jsxs')]
        if len(members) != 1: continue
        runtime = members[0].child_by_field_name('object')
        if runtime.type != 'identifier': continue
        yield node, runtime.text.decode(), args[0], properties(args[1])


def local_binding(function, key):
    params = function.child_by_field_name('parameters').named_children
    if len(params) == 1 and params[0].type == 'object_pattern':
        value = bindings(params[0]).get(key)
        if value: return value
    values = []
    for node in nodes(function.child_by_field_name('body')):
        if node.type != 'variable_declarator': continue
        pattern = node.child_by_field_name('name')
        if pattern.type == 'object_pattern' and key in bindings(pattern):
            values.append(bindings(pattern)[key])
    return require_one(values, key + ' binding')


def plan(read, roots, template, host_template):
    """Return edits only; read supplies hash-checked archive modules lazily."""
    cache = {}
    def module(name):
        if name not in cache: cache[name] = Module(name, read(name))
        return cache[name]

    def resolve(name, exported, seen=()):
        if (name, exported) in seen or len(seen) > 8:
            raise UnsupportedPatch('Circular floating-chat export', FEATURE)
        item = module(name)
        local = item.exports.get(exported)
        if local in item.functions: return item, item.functions[local]
        if local in item.imports:
            return resolve(*item.imports[local], (*seen, (name, exported)))
        raise UnsupportedPatch('Missing native floating-chat export: ' + exported, FEATURE)

    def exported_root(key):
        return require_one((name for name in roots[key] if key in module(name).exports), key + ' export')
    page_root = exported_root('ChatGptConversationPage')
    panel_root = exported_root('WorkSideChatContent')
    start_root = exported_root('startNewConversation')
    page, page_fn = resolve(page_root, 'ChatGptConversationPage')
    panel, panel_fn = resolve(panel_root, 'WorkSideChatContent')
    starter, start_fn = resolve(start_root, 'startNewConversation')
    if PREFIX.encode() in page.source:
        raise UnsupportedPatch('Floating-chat feature is already present', FEATURE)
    if page_fn.has_error or panel_fn.has_error or start_fn.has_error:
        raise UnsupportedPatch('Invalid native floating-chat function', FEATURE)

    _, _, renderer, _ = require_one((
        c for c in jsx_calls(panel_fn)
        if {'conversationId', 'isInlinePreview', 'isTemporaryChat', 'transcriptPresentation'} <= c[3].keys()
    ), 'panel conversation renderer')
    renderer_module, render_fn = resolve(*panel.imports[renderer.text.decode()])
    if renderer_module.name != page.name:
        raise UnsupportedPatch('ChatGPT page and panel renderer do not share a module', FEATURE)
    if render_fn.has_error or b'chatgpt.conversations' not in page_fn.text:
        raise UnsupportedPatch('Unsupported ChatGPT page contract', FEATURE)
    renderer_name = render_fn.child_by_field_name('name').text.decode()
    if not any(c[2].text.decode() == renderer_name for c in jsx_calls(page_fn)):
        raise UnsupportedPatch('ChatGPT page does not use the native panel renderer', FEATURE)

    _, _, provider, _ = require_one((c for c in jsx_calls(panel_fn) if {'route', 'children'} <= c[3].keys()), 'panel route provider')
    host, host_fn = resolve(*panel.imports[provider.text.decode()])
    if host_fn.has_error or PREFIX.encode() in host.source or host.name == page.name:
        raise UnsupportedPatch('Unsupported shared conversation host', FEATURE)
    for key in ('route', 'children'): local_binding(host_fn, key)
    frame = require_one((c[2] for c in jsx_calls(panel_fn)
                         if set(c[3]) == {'children'} and c[2].type == 'identifier'), 'panel conversation frame')

    # Resolve identity checks from the native panel, not names of compiled atoms.
    side = local_binding(panel_fn, 'sideChat')
    declarations = {}
    for node in nodes(panel_fn):
        if node.type == 'variable_declarator' and node.child_by_field_name('name').type == 'identifier':
            declarations[node.child_by_field_name('name').text.decode()] = node.child_by_field_name('value')
    identities = {}
    for node in nodes(panel_fn):
        if node.type != 'binary_expression': continue
        left, right = node.child_by_field_name('left'), node.child_by_field_name('right')
        if node.child_by_field_name('operator').text != b'!==': continue
        if right.type != 'member_expression' or right.child_by_field_name('object').text.decode() != side: continue
        key = right.child_by_field_name('property').text.decode()
        value = declarations.get(left.text.decode())
        if key in ('accountId', 'userId') and value is not None and value.type == 'call_expression':
            identities[key] = value
    if set(identities) != {'accountId', 'userId'}:
        raise UnsupportedPatch('Missing native panel identity gate', FEATURE)

    # Find the lower-level draft initializer called by the ordinary New chat action.
    creators = []
    for node in nodes(start_fn):
        if node.type != 'assignment_expression': continue
        left, right = node.child_by_field_name('left'), node.child_by_field_name('right')
        if left.type == 'member_expression' and left.child_by_field_name('property').text == b'initialChatGptConversationId' and right.type == 'call_expression':
            callee = right.child_by_field_name('function')
            if callee.type == 'identifier': creators.append(callee.text.decode())
    creator = require_one(creators, 'regular ChatGPT draft initializer')
    creator_fn = starter.functions.get(creator)
    if creator_fn is None or creator_fn.has_error or len(creator_fn.child_by_field_name('parameters').named_children) != 2:
        raise UnsupportedPatch('Unsupported regular ChatGPT draft initializer', FEATURE)
    creator_export = require_one((k for k, v in starter.exports.items() if v == creator), 'draft initializer export')

    scope_candidates = []
    for node in nodes(render_fn):
        if node.type != 'variable_declarator': continue
        name, value = node.child_by_field_name('name'), node.child_by_field_name('value')
        if name.type != 'identifier' or value is None or value.type != 'call_expression': continue
        args = value.child_by_field_name('arguments').named_children
        callee = value.child_by_field_name('function')
        if len(args) != 1 or args[0].type != 'identifier' or callee.type != 'identifier': continue
        if re.search(rb'\b' + re.escape(name.text) + rb'\.get\(', render_fn.text):
            scope_candidates.append(value.text.decode())
    scope_expression = require_one(scope_candidates, 'ChatGPT scope hook')
    react = require_one(set(n.child_by_field_name('object').text.decode() for n in nodes(render_fn)
                            if n.type == 'member_expression' and n.child_by_field_name('property').text == b'useState'), 'React hooks runtime')
    jsx = require_one(set(c[1] for c in jsx_calls(render_fn)), 'ChatGPT JSX runtime')

    imports, replacements = [], {'__REACT__': react, '__JSX__': jsx,
                                 '__SCOPE__': scope_expression, '__RENDERER__': renderer_name,
                                 '__MARKER__': json.dumps(MARKER)}
    def add_import(target, exported):
        alias = PREFIX + 'Import' + str(len(imports))
        relative = posixpath.relpath(target, posixpath.dirname(page.name))
        if not relative.startswith('.'): relative = './' + relative
        if target == page.name:
            return module(target).exports[exported]
        imports.append('import{' + exported + ' as ' + alias + '}from"' + relative + '";')
        return alias
    for key, symbol in [('__PROVIDER__', provider.text.decode()), ('__FRAME__', frame.text.decode())]:
        replacements[key] = add_import(*panel.imports[symbol])
    replacements['__CREATE__'] = add_import(starter.name, creator_export)
    def native_action(endpoint, method):
        candidates = []
        for fn in starter.functions.values():
            if endpoint.encode() not in fn.text or method.encode() not in fn.text: continue
            if any(literal(n) == endpoint for n in nodes(fn)):
                candidates.append(fn)
        fn = require_one(candidates, method + ' conversation action')
        if fn.has_error: raise UnsupportedPatch('Invalid native conversation action', FEATURE)
        name = fn.child_by_field_name('name').text.decode()
        exported = require_one((k for k,v in starter.exports.items() if v == name), method + ' export')
        return add_import(starter.name, exported), exported
    replacements['__RENAME__'], rename_export = native_action('/conversation/id/{conversation_id}/rename', 'safePost')
    replacements['__DELETE__'], _ = native_action('/conversation/id/{conversation_id}', 'safeDelete')

    # Follow the ordinary rename UI's conversation lookup to its keyed server-ID
    # and query atoms. This avoids guessing a compiled atom or an arbitrary timer.
    lookups = []
    for name in roots.get('conversationActions', []):
        item = module(name)
        for fn in item.functions.values():
            if b'requireNonEmpty' not in fn.text: continue
            for _, callee, args in calls(fn):
                if callee.type != 'identifier' or item.imports.get(callee.text.decode()) != (starter.name, rename_export): continue
                if len(args) != 1 or args[0].type != 'object': continue
                props = properties(args[0])
                if not {'scope','conversationId','previousTitle','title'} <= props.keys(): continue
                value = props['conversationId']
                if value.type != 'member_expression' or value.child_by_field_name('property').text != b'conversation_id': continue
                target = value.child_by_field_name('object').text
                for declaration in nodes(fn):
                    if declaration.type != 'variable_declarator' or declaration.child_by_field_name('name').text != target: continue
                    init = declaration.child_by_field_name('value')
                    if init is not None and init.type == 'call_expression':
                        helper = item.functions.get(init.child_by_field_name('function').text.decode())
                        if helper is not None: lookups.append((item, helper, fn, props))
    actions, lookup, rename_ui, rename_props = require_one(lookups, 'regular conversation metadata lookup')
    title_value=local_declarations(rename_ui.child_by_field_name('body')).get(rename_props['previousTitle'].text.decode())
    if title_value is None or title_value.type!='ternary_expression':
        raise UnsupportedPatch('Missing native live-title selection',FEATURE)
    for key,branch in [('__TITLE__','consequence'),('__HAS_TITLE__','condition')]:
        expression=title_value.child_by_field_name(branch)
        if expression.type!='call_expression':raise UnsupportedPatch('Unsupported native title getter',FEATURE)
        callee=expression.child_by_field_name('function');args=expression.child_by_field_name('arguments').named_children
        if callee.type!='member_expression' or callee.child_by_field_name('property').text!=b'get' or len(args)!=2 or args[0].type!='identifier':
            raise UnsupportedPatch('Unsupported native title atom',FEATURE)
        replacements[key]=add_import(*actions.imports[args[0].text.decode()])
    title_updaters=[]
    for fn in starter.functions.values():
        params=fn.child_by_field_name('parameters').named_children
        if len(params)==1 and params[0].type=='object_pattern' and {'scope','conversationId','onlyIfProvisional','title'}<=bindings(params[0]).keys():
            title_updaters.append(fn)
    title_updater=require_one(title_updaters,'native provisional-title updater')
    provisional=set()
    for _,callee,args in calls(title_updater):
        if callee.type=='identifier' and len(args)==1 and callee.text.decode() in starter.functions and args[0].type=='call_expression':
            getter=args[0].child_by_field_name('function')
            if getter.type=='member_expression' and getter.child_by_field_name('property').text==b'get':provisional.add(callee.text.decode())
    provisional_name=require_one(provisional,'native provisional-title predicate')
    provisional_export=require_one((key for key,value in starter.exports.items() if value==provisional_name),'provisional-title export')
    replacements['__PROVISIONAL__']=add_import(starter.name,provisional_export)
    atoms = {}
    for _, callee, args in calls(lookup):
        if callee.type != 'member_expression' or len(args) != 2 or args[0].type != 'identifier': continue
        member = callee.child_by_field_name('property').text.decode()
        if member in ('get','snapshot') and args[0].text.decode() in actions.imports:
            if member in atoms: raise UnsupportedPatch('Ambiguous metadata atom', FEATURE)
            atoms[member] = actions.imports[args[0].text.decode()]
    if set(atoms) != {'get','snapshot'}:
        raise UnsupportedPatch('Missing regular conversation metadata atoms', FEATURE)
    replacements['__SERVER__'] = add_import(*atoms['get'])
    replacements['__QUERY__'] = add_import(*atoms['snapshot'])
    readers = set()
    for _, callee, args in calls(render_fn):
        if callee.type == 'identifier' and len(args) == 2 and args[0].type == 'identifier':
            if page.imports.get(args[0].text.decode()) == atoms['get']: readers.add(callee.text.decode())
    replacements['__READ__'] = require_one(readers, 'server-ID subscription hook')
    render_declarations = local_declarations(render_fn.child_by_field_name('body'))
    turn = require_one((properties(n) for n in nodes(render_fn) if n.type == 'object'
                        and {'pendingSubmission','threadMapping','isStreaming'} <= properties(n).keys()), 'native turn status contract')
    def read_atom(value):
        if value is None or value.type != 'call_expression': return None
        callee=value.child_by_field_name('function');args=value.child_by_field_name('arguments').named_children
        if callee.text.decode() == replacements['__READ__'] and len(args)==2 and args[0].type=='identifier':
            return page.imports.get(args[0].text.decode())
        return None
    condition=turn['pendingSubmission'].child_by_field_name('condition')
    if condition is None:raise UnsupportedPatch('Missing pending submission condition',FEATURE)
    pending=set()
    for node in nodes(condition):
        if node.type=='identifier':
            atom=read_atom(render_declarations.get(node.text.decode()))
            if atom:pending.add(atom)
    replacements['__PENDING__']=add_import(*require_one(pending,'pending submission atom'))
    statuses=set()
    def status_source(value,seen=()):
        if value is None:return
        if value.type=='identifier':
            symbol=value.text.decode()
            if symbol in seen:return
            declaration=render_declarations.get(symbol)
            if declaration is not None:status_source(declaration,(*seen,symbol))
            elif symbol in render_declarations:
                for node in nodes(render_fn):
                    if node.type=='assignment_expression' and node.child_by_field_name('left').text.decode()==symbol:
                        status_source(node.child_by_field_name('right'),(*seen,symbol))
        elif value.type=='call_expression':
            callee=value.child_by_field_name('function');args=value.child_by_field_name('arguments').named_children
            if callee.type=='identifier' and callee.text.decode() in page.imports and len(args)==1 and args[0].type=='identifier':
                atom=read_atom(render_declarations.get(args[0].text.decode()))
                if atom:statuses.add((page.imports[callee.text.decode()],atom))
        else:
            for child in value.named_children:status_source(child,seen)
    streaming_value=turn['isStreaming']
    # Native preview/access guards precede the actual activity value. Resolving
    # those unrelated compiler-cache branches would be both ambiguous and costly.
    while streaming_value.type=='binary_expression' and streaming_value.child_by_field_name('operator').text==b'&&':
        streaming_value=streaming_value.child_by_field_name('right')
    status_source(streaming_value)
    streaming,status=require_one(statuses,'native in-progress status helper')
    replacements['__IS_STREAMING__']=add_import(*streaming)
    replacements['__STATUS__']=add_import(*status)
    confirmations = set(c[2].text.decode() for fn in page.functions.values() for c in jsx_calls(fn)
                        if {'open','onOpenChange','isDeleting','onConfirm','title'} <= c[3].keys())
    replacements['__CONFIRM__'] = require_one(confirmations, 'native delete confirmation')
    for key, expr in identities.items():
        callee = expr.child_by_field_name('function').text.decode()
        atom = expr.child_by_field_name('arguments').named_children
        if len(atom) != 1 or atom[0].type != 'identifier':
            raise UnsupportedPatch('Unsupported identity hook arguments', FEATURE)
        atom_name = add_import(*panel.imports[atom[0].text.decode()])
        replacements['__ACCOUNT_ATOM__' if key == 'accountId' else '__USER_ATOM__'] = atom_name
        replacements['__ACCOUNT__' if key == 'accountId' else '__USER__'] = add_import(*panel.imports[callee])+'('+atom_name+')'

    sidebar_rows = []
    for fn in host.functions.values():
        if b'conversation_sidebar' not in fn.text: continue
        try:
            for key in ('conversationId','conversationOrigin','navigationState','statusState','title','route','href'):
                local_binding(fn,key)
        except UnsupportedPatch: continue
        row_calls = [c for c in jsx_calls(fn) if {'title','ariaLabel','onClick','renderActions','statusState'} <= c[3].keys()]
        if len(row_calls) == 1: sidebar_rows.append((fn, row_calls[0]))
    sidebar_fn, sidebar_row = require_one(sidebar_rows, 'ChatGPT history row')
    navigation = set()
    for _, callee, args in calls(sidebar_fn):
        if callee.type == 'identifier' and len(args) == 2 and args[1].type == 'object' and b'conversation_sidebar' in args[1].text:
            symbol = callee.text.decode()
            for declaration in nodes(sidebar_fn):
                if declaration.type != 'variable_declarator' or declaration.child_by_field_name('name').text.decode() != symbol: continue
                value = declaration.child_by_field_name('value')
                if value is not None and value.type == 'call_expression' and not value.child_by_field_name('arguments').named_children:
                    hook = value.child_by_field_name('function').text.decode()
                    if hook in host.imports: navigation.add(host.imports[hook])
    replacements['__NAVIGATE_HOOK__'] = add_import(*require_one(navigation, 'native history navigation hook'))
    paths = set()
    for _, callee, args in calls(panel_fn):
        if callee.type == 'identifier' and callee.text.decode() in panel.imports and len(args) == 1 and args[0].type == 'member_expression':
            if args[0].child_by_field_name('property').text == b'conversationId': paths.add(panel.imports[callee.text.decode()])
    replacements['__PATH__'] = add_import(*require_one(paths, 'native conversation path builder'))

    # Repeat the native panel's lazy module initialization, without importing the
    # panel module back into its own renderer (which would introduce an ESM cycle).
    initializers = []
    for item in [panel, module(start_root)]:
        for statement in item.root.named_children:
            if statement.type != 'expression_statement': continue
            expressions = statement.named_children
            if len(expressions) != 1 or expressions[0].type != 'call_expression': continue
            call = expressions[0]
            if call.child_by_field_name('arguments').named_children: continue
            name = call.child_by_field_name('function').text.decode()
            if name in item.imports:
                initializers.append(add_import(*item.imports[name]) + '();')
            elif name in item.functions:
                for _, fn, args in calls(item.functions[name]):
                    if fn.type == 'identifier' and not args and fn.text.decode() in item.imports:
                        initializers.append(add_import(*item.imports[fn.text.decode()]) + '();')
    if not initializers:
        raise UnsupportedPatch('Missing native panel initialization', FEATURE)
    replacements['__INITIALIZE__'] = ''.join(dict.fromkeys(initializers))

    # Obtain runtime factories through their assignments, not compiler symbols.
    def runtime_factory(symbol, item=None):
        item = item or page
        candidates = []
        for node in nodes(item.root):
            if node.type != 'assignment_expression': continue
            left, right = node.child_by_field_name('left'), node.child_by_field_name('right')
            if left.text.decode() != symbol or right.type != 'call_expression': continue
            fn = right.child_by_field_name('function')
            if fn.type == 'identifier' and fn.text.decode() in item.imports and not right.child_by_field_name('arguments').named_children:
                candidates.append(item.imports[fn.text.decode()])
        return require_one(set(candidates), symbol + ' runtime factory')

    portal_symbols = {node.child_by_field_name('object').text.decode() for node in nodes(host.root)
                      if node.type == 'member_expression' and node.child_by_field_name('property').text == b'createPortal'
                      and node.child_by_field_name('object').type == 'identifier'}
    portal_factory = require_one({runtime_factory(symbol, host) for symbol in portal_symbols}, 'portal runtime factory')
    toggles = []
    for fn in host.functions.values():
        if not all(key in fn.text for key in (b'composerController', b'isIndicator', b'isTemporaryChat', b'onToggle')):
            continue
        try:
            for key in ('composerController', 'conversationId', 'isIndicator', 'isTemporaryChat', 'onToggle'):
                local_binding(fn, key)
        except UnsupportedPatch:
            continue
        toggles.append(fn)
    toggle = require_one(toggles, 'temporary-chat toggle')
    toggle_locals = local_declarations(toggle.child_by_field_name('body'))
    icon_call = require_one((c for c in jsx_calls(toggle) if c[3].get('asset') is not None
                            and c[3]['asset'].type == 'identifier' and c[3]['asset'].text.decode() in host.imports
                            and c[3]['asset'].text.decode() not in toggle_locals),
                           'temporary-chat icon asset')
    button_call = require_one((c for c in jsx_calls(toggle) if literal(c[3].get('color')) == 'ghostActive'
                              and literal(c[3].get('size')) == 'toolbar'), 'temporary-chat toolbar button')
    ui_initializers = set()
    for node in nodes(host.root):
        if node.type != 'assignment_expression' or node.child_by_field_name('left').text.decode() != icon_call[1]:
            continue
        parent = node.parent
        while parent is not None and parent.type != 'function_declaration': parent = parent.parent
        if parent is not None: ui_initializers.add(parent.child_by_field_name('name').text.decode())
    ui_initializer = require_one(ui_initializers, 'temporary-chat UI initializer')
    replacements['__BUTTON__'] = add_import(host.name, '__customFloatingButton')
    replacements['__TEMP_ICON__'] = add_import(host.name, '__customFloatingTemporaryIcon')
    host_imports = []
    host_replacements = {'__HOST__': host_fn.child_by_field_name('name').text.decode(), '__MARKER__':json.dumps(MARKER),
                         '__NATIVE_UI_INIT__': ui_initializer, '__NATIVE_ICON__': icon_call[2].text.decode(),
                         '__NATIVE_ASSET__': icon_call[3]['asset'].text.decode(), '__NATIVE_BUTTON__': button_call[2].text.decode(),
                         '__PAGE_PATH__': './' + posixpath.relpath(page.name, posixpath.dirname(host.name))}
    for key, factory in [('__REACT_FACTORY__', runtime_factory(react)), ('__JSX_FACTORY__', runtime_factory(jsx)),
                         ('__PORTAL_FACTORY__', portal_factory)]:
        target, exported = factory
        alias = PREFIX + 'HostImport' + str(len(host_imports))
        relative = posixpath.relpath(target, posixpath.dirname(host.name))
        if not relative.startswith('.'): relative = './' + relative
        host_imports.append('import{' + exported + ' as ' + alias + '}from"' + relative + '";')
        host_replacements[key] = alias
    rendered = template
    for key, value in replacements.items(): rendered = rendered.replace(key, value)
    host_rendered = host_template
    for key, value in host_replacements.items(): host_rendered = host_rendered.replace(key, value)
    for data in [rendered, host_rendered]:
        if re.search(r'__[A-Z_]+__', data) or parser().parse(data.encode()).root_node.has_error:
            raise UnsupportedPatch('Could not construct floating-chat components', FEATURE)
    additions = '\n' + '\n'.join(imports) + '\n' + rendered + '\nexport{__customFloatingPanel};\n'
    host_name = host_fn.child_by_field_name('name')
    history_edits = []
    title = sidebar_row[3]['title'].text
    for _, _, _, props in jsx_calls(sidebar_fn):
        for key in ('title','ariaLabel'):
            value = props.get(key)
            if value is None or value.text != title: continue
            helper = '__customFloatingHistoryText'
            if key == 'title' and {'ariaLabel','onClick','renderActions','statusState'} <= props.keys(): helper='__customFloatingHistoryTitle'
            replacement = helper+'('+value.text.decode()+')'
            if value.type == 'shorthand_property_identifier': replacement=key+':'+replacement
            history_edits.append(dict(start=value.start_byte,end=value.end_byte,replacement=replacement,feature=FEATURE))
    return {
        page.name: [dict(start=len(page.source), end=len(page.source), replacement=additions, feature=FEATURE)],
        host.name: history_edits+[dict(start=host_name.start_byte, end=host_name.end_byte, replacement=PREFIX+'NativeHost', feature=FEATURE),
                    dict(start=len(host.source), end=len(host.source), replacement='\n'+'\n'.join(host_imports)+'\n'+host_rendered, feature=FEATURE)],
    }
