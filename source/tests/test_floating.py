from pathlib import Path
from unittest import TestCase
import json
import subprocess
import struct
import re
import tempfile

import engine
import features
import floating_patch
import sidebar_patch


# Authored structural fixtures, not extracted application code.
MODULES = {
    'entry.js': 'import{Page as P}from"./page.js";export{P as ChatGptConversationPage};',
    'page.js': '''
import{getReact,getJSX,useScope as hook,read}from"./shared.js";
import{Scope,ServerId,ConversationQuery,Pending,Status,isStreaming}from"./core.js";
import{Dialog}from"./provider.js";
var R,J;
function Render(props){const scope=hook(Scope);const[state]=R.useState(null);const server=read(ServerId,props.conversationId);
const pending=read(Pending,props.conversationId),status=read(Status,props.conversationId),active=isStreaming(status);
const turns={threadMapping:{},pendingSubmission:pending!=null?{prompt:pending}:null,isStreaming:active};
scope.get("settings");return J.jsx("native-chat",{...props})}
function Page(){const gate="chatgpt.conversations";return J.jsx(Render,{conversationId:"main",gate})}
function Menu(props){return J.jsx(Dialog,{open:props.open,onOpenChange:()=>{},isDeleting:false,onConfirm:()=>{},title:props.title})}
function init(){R=getReact();J=getJSX()}
init();
export{Page,Render,init};
''',
    'panel.js': '''
import{JSX as J,useValue as read,initialize,pathFor}from"./shared.js";
import{Account,User,Frame}from"./core.js";
import{Provider}from"./provider.js";
import{Render,init}from"./page.js";
function Panel(props){const{sideChat:s}=props;const a=read(Account),u=read(User);
if(a!==s.accountId||u!==s.userId)return null;
const url=pathFor(s.conversationId);
return J.jsx(Provider,{route:{conversationId:s.conversationId,pathname:url},children:J.jsx(Frame,{
children:J.jsx(Render,{conversationId:s.conversationId,isInlinePreview:true,isTemporaryChat:false,transcriptPresentation:"panel"})})})}
function setup(){initialize();init()}
setup();export{Panel as WorkSideChatContent};
''',
    'new.js': 'import{start,initialize}from"./core.js";initialize();export{start as startNewConversation};',
    'core.js': '''
import{runtime}from"./shared.js";
const Account="account",User="user",Scope="scope",Frame="native-frame",ServerId="server-id",ConversationQuery="conversation-query",Pending="pending",Status="status",Title="title",HasTitle="has-title";
function isStreaming(status){return status==="streaming"}
function create(scope,hints){return runtime.create(scope,hints)}
function start(scope,options){options.initialChatGptConversationId=create(scope,[])}
function initialize(){}
const api={safePost:(_path,props)=>runtime.rename(props),safeDelete:(_path,props)=>runtime.remove(props.conversationId)};
async function rename(props){return api.safePost("/conversation/id/{conversation_id}/rename",props)}
async function remove(props){return api.safeDelete("/conversation/id/{conversation_id}",props)}
function provisional(title){return title==null||title==="New chat"}
function updateTitle({scope,conversationId,onlyIfProvisional,title}){if(!onlyIfProvisional||provisional(scope.get(Title,conversationId)))scope.set(Title,conversationId,title)}
export{Account,User,Scope,Frame,ServerId,ConversationQuery,Pending,Status,Title,HasTitle,isStreaming,provisional,create,start,initialize,rename,remove};
''',
    'actions.js': '''import{rename,ServerId,ConversationQuery,Title,HasTitle}from"./core.js";
function renameAction(scope,id){const item=lookup(scope,id);if(!item)return;
const previous=scope.get(HasTitle,id)?scope.get(Title,id):item.title;
return{draftKey:item.conversation_id,protectedProjectId:null,requireNonEmpty:true,
onSave:title=>rename({scope,conversationId:item.conversation_id,previousTitle:previous,title})}}
function lookup(scope,id){const server=scope.get(ServerId,id);return server==null?null:scope.query.snapshot(ConversationQuery,server).getData()}
export{renameAction};''',
    'provider.js': '''import{JSX as J,getNavigate,getDOM,getJSX,TemporaryIcon,TemporaryAsset,NativeButton}from"./shared.js";
var DOM;function initDOM(){DOM=getDOM()}initDOM();
var UI;function initTemporaryUI(){UI=getJSX()}initTemporaryUI();
function TemporaryToggle(props){const{composerController,conversationId,isIndicator,isTemporaryChat,onToggle}=props;
return UI.jsx(NativeButton,{color:"ghostActive",size:"toolbar",uniform:true,
children:UI.jsx(TemporaryIcon,{asset:TemporaryAsset})})}
function NativePortal(props){return DOM.createPortal(props.children,props.container)}
function Provider(props){const{route,children}=props;return J.jsx("native-route",{...props,route,children})}
function Sidebar(props){const{conversationId,conversationOrigin,navigationState,statusState,title,route,href}=props;
const navigate=getNavigate();return J.jsx("native-history-row",{title,ariaLabel:title,statusState,renderActions:()=>{},
onClick:()=>navigate(route,{state:{navigationSource:"conversation_sidebar"}})})}
const Dialog="native-confirm";
export{Provider,Dialog,Sidebar};''',
    'shared.js': '''
const runtime={account:"account-a",user:"user-a",nested:false,drafts:[],fail:false,states:[],index:0,
instances:new Map(),effects:[],ids:new Map(),conversations:new Map(),pending:new Map(),statuses:new Map(),titles:new Map(),renames:[],deletes:[],navigations:[],reads:[],renameFail:false,deleteFail:false,
async rename(props){props.assertRequestCurrent?.();this.renames.push(props);if(this.renameFail)throw Error("rename failure");
this.conversations.set(props.conversationId,{...this.conversations.get(props.conversationId),title:props.title});this.titles.set(props.conversationId,props.title)},
async remove(id){this.deletes.push(id);if(this.deleteFail)throw Error("delete failure");this.conversations.delete(id)},
create(scope,hints){if(this.fail)throw Error("failed");this.drafts.push({scope,hints});return "client-"+this.drafts.length},
begin(key="panel"){this.index=0;if(!this.instances.has(key))this.instances.set(key,[]);this.states=this.instances.get(key)},
reset(key="panel"){for(const cell of this.instances.get(key)||[])cell?.cleanup?.();this.instances.delete(key)},
async flush(){while(this.effects.length)this.effects.shift()();for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve))}};
const React={Component:class{},useState(initial){const i=runtime.index++,cells=runtime.states;
if(!(i in cells))cells[i]=typeof initial==="function"?initial():initial;
return[cells[i],value=>cells[i]=typeof value==="function"?value(cells[i]):value]},
useRef(initial){const i=runtime.index++;if(!(i in runtime.states))runtime.states[i]={current:initial};return runtime.states[i]},
useEffect(effect,deps){const i=runtime.index++,cells=runtime.states,previous=cells[i];
if(!previous||deps.some((value,index)=>!Object.is(value,previous.deps[index]))){const record={deps};cells[i]=record;
runtime.effects.push(()=>{previous?.cleanup?.();record.cleanup=effect()})}},
createContext:()=>({Provider:"owner-context"}),useContext:()=>runtime.nested,
lazy:load=>({load}),Suspense:"suspense"};
const JSX={Fragment:"fragment",jsx:(type,props,key)=>({type,props,key}),jsxs:(type,props,key)=>({type,props,key})};
const TemporaryIcon="native-temporary-icon",TemporaryAsset="native-temporary-asset",NativeButton="button";
function serverId(id){return runtime.ids.get(id)||(runtime.conversations.has(id)?id:null)}
function liveTitle(id){return runtime.titles.get(id)??runtime.titles.get(serverId(id))}
const scope={get(key,id){return key==="server-id"?serverId(id):key==="pending"?runtime.pending.get(id):key==="status"?runtime.statuses.get(id):key==="has-title"?liveTitle(id)!=null:key==="title"?liveTitle(id):runtime[key]},
query:{snapshot:(_key,id)=>({getData:()=>runtime.conversations.get(id)})}};
function useScope(){return scope}
function useValue(key){return runtime[key]}
function initialize(){}
function getReact(){return React}function getJSX(){return JSX}
function getDOM(){return {createPortal:(children,container)=>({type:"portal",props:{children,container}})}}
function read(key,id){runtime.reads.push(key);return key==="server-id"?serverId(id):key==="pending"?runtime.pending.get(id):key==="status"?runtime.statuses.get(id):key==="has-title"?liveTitle(id)!=null:key==="title"?liveTitle(id):{data:runtime.conversations.get(id)}}
function pathFor(id){return "/c/"+encodeURIComponent(id)}
function getNavigate(){return async(path,options)=>{if(runtime.navigateFail)throw Error("navigation failed");runtime.navigations.push({path,options})}}
export{React,JSX,getReact,getJSX,getDOM,useScope,useValue,initialize,runtime,read,pathFor,getNavigate,TemporaryIcon,TemporaryAsset,NativeButton};
''',
}
ROOTS = {key: ['webview/assets/' + name] for key, name in (
    ('ChatGptConversationPage', 'entry.js'), ('WorkSideChatContent', 'panel.js'),
    ('startNewConversation', 'new.js'))}
ROOTS['conversationActions']=['webview/assets/actions.js']


class FloatingTests(TestCase):
    def plan(self, changes=None, roots=None):
        modules = {('webview/assets/' + name): text.encode() for name, text in MODULES.items()}
        modules.update(changes or {})
        folder=Path(__file__).parent.parent/'patches'
        template = (folder/'floating-state.js').read_text(encoding='utf-8')+'\n'+(folder/'floating-chat.js').read_text(encoding='utf-8')
        host = (Path(__file__).parent.parent/'patches/floating-host.js').read_text(encoding='utf-8')
        changes = floating_patch.plan(modules.__getitem__, roots or ROOTS, template, host)
        return modules, changes

    def test_rewrite_preserves_main_and_resolves_imports(self):
        modules, changes = self.plan()
        rewritten = sidebar_patch.apply(modules['webview/assets/page.js'], changes['webview/assets/page.js'])
        self.assertTrue(rewritten.startswith(modules['webview/assets/page.js']))
        self.assertIn(b'const gate="chatgpt.conversations";return J.jsx(Render,{conversationId:"main",gate})', rewritten)
        self.assertIn(b'__customFloatingPanel', rewritten)
        self.assertNotIn(b'__INITIALIZE__', rewritten)
        host = sidebar_patch.apply(modules['webview/assets/provider.js'],changes['webview/assets/provider.js'])
        self.assertIn(b'function __customFloatingNativeHost(',host)
        self.assertIn(b'import("./page.js")',host)

    def test_renamed_symbols_and_bundle_paths(self):
        renamed = dict(MODULES)
        for old, new in [('Render','RenamedRenderer'),('Provider','RouteHost'),('create','makeDraft'),('read','getValue')]:
            renamed = {name: re.sub(r'(?<![\w$])'+re.escape(old)+r'(?![\w$])',new,text) for name,text in renamed.items()}
        renamed = {name.replace('page.js','moved.js'): text.replace('./page.js','./moved.js') for name,text in renamed.items()}
        renamed['moved.js'] = 'const unicode="שלום";'+renamed['moved.js']
        modules = {'webview/assets/'+name:text.encode() for name,text in renamed.items()}
        folder=Path(__file__).parent.parent/'patches'
        template=(folder/'floating-state.js').read_text(encoding='utf-8')+'\n'+(folder/'floating-chat.js').read_text(encoding='utf-8')
        host=(Path(__file__).parent.parent/'patches/floating-host.js').read_text(encoding='utf-8')
        changes=floating_patch.plan(modules.__getitem__,ROOTS,template,host)
        name='webview/assets/moved.js'
        self.assertIn(name,changes)
        self.assertTrue(sidebar_patch.apply(modules[name],changes[name]).startswith('const unicode="שלום";'.encode()))
        rendered_host=sidebar_patch.apply(modules['webview/assets/provider.js'],changes['webview/assets/provider.js'])
        self.assertIn(b'import("./moved.js")',rendered_host)

    def test_missing_and_ambiguous_exports_fail_closed(self):
        for values in [[], ROOTS['WorkSideChatContent'] * 2]:
            roots=dict(ROOTS,WorkSideChatContent=values)
            with self.assertRaises(engine.UnsupportedPatch) as raised: self.plan(roots=roots)
            self.assertEqual(raised.exception.feature,'floating_chat')

    def test_missing_identity_or_draft_contract_fails_closed(self):
        for name, old, new in [('panel.js','accountId','otherIdentity'),('core.js','initialChatGptConversationId','otherDraft')]:
            changed={'webview/assets/'+name:MODULES[name].replace(old,new).encode()}
            with self.assertRaises(engine.UnsupportedPatch):self.plan(changed)

    def test_localization_text_is_not_an_export(self):
        roots=dict(ROOTS,WorkSideChatContent=ROOTS['WorkSideChatContent']+['webview/assets/translation.js'])
        self.plan({'webview/assets/translation.js':b'const text="as WorkSideChatContent";'},roots)

    def test_missing_shared_host_or_runtime_factory_fails_closed(self):
        for name,old,new in [('provider.js','{route,children}','{route,content}'),
                             ('provider.js','DOM.createPortal','DOM.otherPortal'),
                             ('provider.js','DOM=getDOM()','DOM=unknownFactory()'),
                             ('provider.js','isIndicator,isTemporaryChat','otherIndicator,isTemporaryChat'),
                             ('provider.js','asset:TemporaryAsset','asset:undefined'),
                             ('provider.js','color:"ghostActive"','color:"otherColor"'),
                             ('provider.js','UI=getJSX()','OtherUI=getJSX()'),
                             ('page.js','R=getReact()','R=unknownFactory()')]:
            with self.subTest(name=name),self.assertRaises(engine.UnsupportedPatch):
                self.plan({'webview/assets/'+name:MODULES[name].replace(old,new).encode()})

    def test_native_icon_ignores_shadowed_import(self):
        provider = MODULES['provider.js'].replace('TemporaryAsset,NativeButton',
                    'TemporaryAsset,TemporaryAsset as shadowAsset,NativeButton')
        provider = provider.replace('return UI.jsx(NativeButton,',
                    'const shadowAsset=null;UI.jsx(TemporaryIcon,{asset:shadowAsset});return UI.jsx(NativeButton,')
        self.plan({'webview/assets/provider.js': provider.encode()})

    def test_missing_lifecycle_contracts_fail_closed(self):
        for name,old,new in [
            ('core.js','/conversation/id/{conversation_id}/rename','/unsupported'),
            ('core.js','safeDelete','unsupportedDelete'),
            ('actions.js','scope.query.snapshot','scope.query.other'),
            ('actions.js','previousTitle:previous','previousTitle:item.title'),
            ('core.js','onlyIfProvisional','otherProvisional'),
            ('page.js','onConfirm:','otherConfirm:'),
            ('provider.js','conversation_sidebar','other_source'),
            ('page.js','pendingSubmission:','otherSubmission:'),
            ('panel.js','pathFor(s.conversationId)','pathFor("static")'),
        ]:
            with self.subTest(name=name,contract=old),self.assertRaises(engine.UnsupportedPatch):
                self.plan({'webview/assets/'+name:MODULES[name].replace(old,new).encode()})

    def test_ambiguous_lifecycle_and_history_rows_fail_closed(self):
        for name,function in [('actions.js','renameAction'),('provider.js','Sidebar'),('provider.js','TemporaryToggle')]:
            data=MODULES[name].encode();module=floating_patch.Module('webview/assets/'+name,data)
            extra=module.functions[function].text.replace(('function '+function+'(').encode(),('function '+function+'Again(').encode())
            with self.subTest(name=name),self.assertRaises(engine.UnsupportedPatch):
                self.plan({'webview/assets/'+name:data+b'\n'+extra})

    def test_disabled_by_default_and_legacy_preferences(self):
        self.assertFalse(features.normalize()['floating_chat'])
        self.assertFalse(features.normalize({'bug_fixes':True})['floating_chat'])
        self.assertTrue(features.normalize({'floating_chat':True})['floating_chat'])

    def test_generated_component_behavior(self):
        modules,changes=self.plan()
        for name,edits in changes.items():modules[name]=sidebar_patch.apply(modules[name],edits)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'package.json').write_text(json.dumps({'type':'module'}))
            for name,data in modules.items():
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            result=subprocess.run(['node',str(Path(__file__).parent/'floating.cjs'),str(root)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_engine_archive_round_trip_and_dependency_integrity(self):
        for tampered in [False,True]:
            with self.subTest(tampered=tampered), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'resources').mkdir()
                entries={};payload=b''
                for name,text in MODULES.items():
                    data=text.encode();value=engine.sha(data)
                    entries[name]={'offset':str(len(payload)),'size':len(data),'integrity':{
                        'algorithm':'SHA256','hash':'0'*64 if tampered and name=='core.js' else value,
                        'blockSize':4096,'blocks':[engine.sha(data[i:i+4096]) for i in range(0,len(data),4096)]}}
                    payload+=data
                tree={'files':{'webview':{'files':{'assets':{'files':entries}}}}}
                raw=json.dumps(tree).encode();padding=(-len(raw))%4
                header=struct.pack('<II',len(raw)+4+padding,len(raw))+raw+b'\0'*padding
                original=struct.pack('<II',4,len(header))+header+payload
                archive=root/'resources/app.asar';archive.write_bytes(original)
                launcher=root/'ChatGPT.exe';launcher.write_bytes(b'fixture-'+engine.sha(raw).encode())
                selected=features.normalize({'floating_chat':True},tabs=False)
                if tampered:
                    with self.assertRaises(engine.UnsupportedPatch) as raised:engine.plan_changes(root,selected)
                    self.assertEqual(raised.exception.feature,'floating_chat')
                else:
                    plan=engine.plan_changes(root,selected)
                    self.assertEqual(plan['contracts']['floating_chat'],1)
                    target=root/'patched.asar'
                    engine.patch_archive(archive,target,launcher,plan)
                    self.assertIn(engine.verify_archive(target).encode(),launcher.read_bytes())
                self.assertEqual(archive.read_bytes(),original)
