"""Optional sidebar and navigation repairs resolved from native syntax contracts."""
import re
import hashlib
from collections import Counter
from selector_patch import parser, nodes, bindings, literal, UnsupportedPatch


def properties(obj):
    result = {}
    for item in obj.named_children:
        if item.type != 'pair': continue
        key = item.child_by_field_name('key')
        value = item.child_by_field_name('value')
        result[literal(key) or key.text.decode()] = value
    return result


def enclosing(node, types):
    while node is not None and node.type not in types: node = node.parent
    return node


def declarations(body):
    return {n.child_by_field_name('name').text.decode(): n.child_by_field_name('value')
            for statement in body.named_children if statement.type in ('lexical_declaration','variable_declaration')
            for n in statement.named_children if n.type == 'variable_declarator' and n.child_by_field_name('name').type == 'identifier'}


def returned_objects(root, source, token):
    seen = set()
    for match in re.finditer(rb'\b' + re.escape(token) + rb'\b', source):
        node = root.descendant_for_byte_range(match.start(), match.end())
        ret = enclosing(node, {'return_statement'})
        if ret is None or ret.start_byte in seen or not ret.named_children: continue
        seen.add(ret.start_byte)
        value = ret.named_children[0]
        if value.type == 'object': yield ret, value


def arrow_params(arrow):
    params = arrow.child_by_field_name('parameters')
    return params.named_children if params is not None else []


def assignment_arrow(root, source, symbol):
    matches = []
    for match in re.finditer(rb'\b' + re.escape(symbol.encode()) + rb'\s*=', source):
        node = enclosing(root.descendant_for_byte_range(match.start(), match.start()+len(symbol)), {'assignment_expression'})
        if node is None or node.child_by_field_name('left').text != symbol.encode(): continue
        value = node.child_by_field_name('right')
        if value.type != 'call_expression': continue
        args = value.child_by_field_name('arguments').named_children
        if len(args) >= 2 and args[1].type == 'arrow_function': matches.append(args[1])
    if len(matches) != 1: raise UnsupportedPatch('Could not locate the native sidebar mode selector', 'hide_gpt_projects')
    return matches[0]


def discover(source, options):
    """Return edits and the individual contracts satisfied in this UI bundle."""
    root = parser().parse(source).root_node
    edits = []
    found = Counter()
    def edit(node, replacement, feature):
        edits.append({'start': node.start_byte, 'end': node.end_byte, 'replacement': replacement, 'feature': feature})
    def insert(offset, replacement, feature):
        edits.append({'start': offset, 'end': offset, 'replacement': replacement, 'feature': feature})

    if options['hide_gpt_projects'] or options['separate_recents']:
        for ret, obj in returned_objects(root, source, b'conversationFilter'):
            props = properties(obj)
            if not {'source','mode','conversationFilter','flatConversationHistory','workLocalSidebarContentVisible','linkedProjectsOnly'} <= props.keys(): continue
            arrow = enclosing(ret, {'arrow_function'})
            params = arrow_params(arrow) if arrow else []
            if len(params) != 2 or params[0].type != 'identifier' or params[1].type != 'object_pattern': continue
            if arrow.has_error: continue
            mode = params[0].text.decode()
            get = bindings(params[1]).get('get')
            if get is None: continue
            if options['separate_recents']:
                insert(obj.end_byte-1, f',source:{mode}==="codex"?"codex":"chatgpt",conversationFilter:{mode}==="codex"?"tasks":"chats"', 'separate_recents')
                found['source_filter'] += 1
            if options['hide_gpt_projects']:
                flat = props['flatConversationHistory'].text.decode()
                insert(obj.end_byte-1, f',flatConversationHistory:{mode}==="chatgpt"||({flat})', 'hide_gpt_projects')
                value = declarations(arrow.child_by_field_name('body')).get(props['mode'].text.decode())
                if value is None or value.type != 'call_expression' or value.child_by_field_name('function').text.decode() != get:
                    raise UnsupportedPatch('Could not resolve project grouping', 'hide_gpt_projects')
                args = value.child_by_field_name('arguments').named_children
                if len(args) != 2 or args[0].type != 'identifier' or args[1].text != params[0].text:
                    raise UnsupportedPatch('Unexpected project grouping contract', 'hide_gpt_projects')
                mode_arrow = assignment_arrow(root, source, args[0].text.decode())
                mode_params = arrow_params(mode_arrow)
                body = mode_arrow.child_by_field_name('body')
                if not mode_params or mode_params[0].type != 'identifier' or body.type != 'statement_block' or mode_arrow.has_error:
                    raise UnsupportedPatch('Could not customize project grouping', 'hide_gpt_projects')
                insert(body.start_byte+1, f'if({mode_params[0].text.decode()}==="chatgpt")return "list";', 'hide_gpt_projects')
                found['project_mode'] += 1

    if options['separate_recents']:
        for match in re.finditer(b'showSourceFilter',source):
            node=enclosing(root.descendant_for_byte_range(match.start(),match.end()),{'pair'})
            if node is None or node.child_by_field_name('key').text!=b'showSourceFilter':continue
            fn=enclosing(node,{'function_declaration'})
            if fn is not None and b'sidebarElectron.chatGptWork.recents' in fn.text:
                edit(node.child_by_field_name('value'),'false','separate_recents');found['source_filter_ui']+=1

    if options['hide_gpt_projects']:
        recent_functions=set()
        for match in re.finditer(b'sidebarElectron.chatGptWork.recents',source):
            fn=enclosing(root.descendant_for_byte_range(match.start(),match.end()),{'function_declaration'})
            if fn is None or fn.start_byte in recent_functions or fn.has_error:continue
            recent_functions.add(fn.start_byte)
            params=fn.child_by_field_name('parameters').named_children
            body=fn.child_by_field_name('body');mode=None
            if len(params)!=1 or params[0].type!='identifier':continue
            for statement in body.named_children:
                if statement.type not in ('lexical_declaration','variable_declaration'):continue
                for declaration in statement.named_children:
                    if declaration.type!='variable_declarator':continue
                    name=declaration.child_by_field_name('name');value=declaration.child_by_field_name('value')
                    if name.type=='object_pattern' and value is not None and value.text==params[0].text:
                        mode=bindings(name).get('sidebarMode') or mode
            if mode is None:continue
            writers=[];react=set()
            for node in nodes(body):
                if node.type=='member_expression' and node.child_by_field_name('property').text==b'useEffect':
                    obj=node.child_by_field_name('object')
                    if obj.type=='identifier':react.add(obj.text.decode())
                if node.type!='call_expression':continue
                call=node.child_by_field_name('function');args=node.child_by_field_name('arguments').named_children
                if call.type=='identifier' and len(args)==3 and literal(args[1])=='chats' and args[0].type=='identifier' and args[2].type=='identifier':
                    writers.append((call.text.decode(),args[0].text.decode()))
            if len(set(writers))!=1 or len(react)!=1:raise UnsupportedPatch('Could not open the native recent-chat section','hide_gpt_projects')
            write,store=writers[0];runtime=next(iter(react))
            statement=next(n for n in body.named_children if n.type in ('lexical_declaration','variable_declaration'))
            insert(statement.end_byte,f';(0,{runtime}.useEffect)(()=>{{if({mode}==="chatgpt"){write}({store},"chats",false)}},[{mode},{store}]);','hide_gpt_projects')
            found['recent_expansion']+=1

        for ret, obj in returned_objects(root, source, b'chatOrderInput'):
            props = properties(obj)
            if not {'entries','layout','chatOrderInput'} <= props.keys(): continue
            arrow = enclosing(ret, {'arrow_function'})
            params = arrow_params(arrow) if arrow else []
            if len(params) != 2 or params[0].type != 'identifier' or arrow.has_error: continue
            decls = declarations(arrow.child_by_field_name('body'))
            entries = decls.get(props['entries'].text.decode())
            layout = decls.get(props['layout'].text.decode())
            if entries is None or entries.type != 'array' or layout is None or layout.type != 'call_expression': continue
            args = layout.child_by_field_name('arguments').named_children
            if len(args) != 2 or args[0].type != 'array': continue
            mode = params[0].text.decode()+'.sidebarMode'
            for value in [entries,args[0]]:
                edit(value, f'({value.text.decode()}).filter(__customEntry=>{mode}!=="chatgpt"||__customEntry.kind!=="project")', 'hide_gpt_projects')
            insert(obj.end_byte-1,f',...({mode}==="chatgpt"?{{orderedPinnedProjectGroups:[],allCodexProjectGroups:[],codexProjectGroups:[],chatGptProjectTargets:[]}}:{{}})','hide_gpt_projects')
            found['project_layout'] += 1

        seen = set()
        for match in re.finditer(b'sidebarElectron.projectsNavLink',source):
            node = root.descendant_for_byte_range(match.start(),match.end())
            while node is not None:
                if node.type == 'ternary_expression':
                    consequence = node.child_by_field_name('consequence')
                    if consequence is not None and consequence.type == 'object' and b'/projects' in consequence.text and {'id','onSelect','label','isCurrentDestination'} <= properties(consequence).keys():
                        break
                node = node.parent
            if node is None or node.start_byte in seen: continue
            seen.add(node.start_byte)
            fn = enclosing(node,{'function_declaration'})
            if fn is None or fn.has_error: continue
            mode_names=[]
            for name,value in declarations(fn.child_by_field_name('body')).items():
                if value is not None and value.type == 'ternary_expression' and literal(value.child_by_field_name('consequence'))=='chatgpt' and literal(value.child_by_field_name('alternative'))=='codex':
                    mode_names.append(name)
            if len(mode_names)!=1: raise UnsupportedPatch('Could not resolve the Projects navigation mode', 'hide_gpt_projects')
            condition=node.child_by_field_name('condition')
            edit(condition,f'({mode_names[0]}==="codex"&&({condition.text.decode()}))','hide_gpt_projects')
            found['project_navigation']+=1

    if options['bug_fixes']:
        seen=set()
        for match in re.finditer(b'codexLocalAccessStatus',source):
            fn=enclosing(root.descendant_for_byte_range(match.start(),match.end()),{'function_declaration'})
            if fn is None or fn.start_byte in seen: continue
            seen.add(fn.start_byte)
            params=fn.child_by_field_name('parameters').named_children
            if len(params)!=2 or params[1].type!='object_pattern' or fn.has_error: continue
            props=bindings(params[1])
            if not {'currentMode','nextMode','navigate','restoreNavigation','startNewConversation'}<=props.keys():continue
            matches=[]
            for node in nodes(fn.child_by_field_name('body')):
                if node.type!='if_statement':continue
                condition=node.child_by_field_name('condition');body=node.child_by_field_name('consequence')
                if body is None or b'sidebarThreadLocationId' not in body.text:continue
                if not any(n.type=='identifier' and n.text.decode()==props['nextMode'] for n in nodes(condition)):continue
                if not any(literal(n)=='work' for n in nodes(condition)):continue
                matches.append(condition)
            if len(matches)!=1:raise UnsupportedPatch('Could not isolate the route reuse bug','bug_fixes')
            edit(matches[0],'(false)','bug_fixes');found['product_navigation']+=1
    return edits,found


def error_signature(tree):
    result=[];pending=[tree.root_node]
    while pending:
        node=pending.pop()
        if node.is_error or node.is_missing:
            result.append((node.type,hashlib.sha256(node.text).hexdigest()))
        elif node.has_error:
            pending.extend(node.named_children)
    return Counter(result)


def apply(source, edits):
    chunks=[];offset=0
    for value in sorted(edits,key=lambda e:(e['start'],e['end'])):
        start,end=value['start'],value['end']
        if start<offset or end<start or end>len(source):raise UnsupportedPatch('Overlapping UI changes')
        chunks.extend([source[offset:start],value['replacement'].encode()]);offset=end
    chunks.append(source[offset:]);result=b''.join(chunks)
    p=parser()
    if error_signature(p.parse(source))!=error_signature(p.parse(result)):
        raise UnsupportedPatch('The modified UI did not pass its syntax check')
    return result
