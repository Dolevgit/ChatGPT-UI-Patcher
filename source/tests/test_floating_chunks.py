from pathlib import Path
from unittest import TestCase

import floating_chunks
import sidebar_patch
from selector_patch import UnsupportedPatch


CHUNK = b'''
export const __rspack_esm_id=42;
export const factories={
  main(module,out,load){
    const lazy=async()=>(await Promise.all([load.e(42),load.e(65)]).then(load.bind(load,"side"))).WorkSideChatContent;
  },
  base(module,out,load){},
  side(module,out,load){
    const J=load("base"), page=load("chat"), provider=load("routes");
    function Side({sideChat:s}){
      const a=(0,J.useAtom)(J.account), u=(0,J.useAtom)(J.user);
      if(a!==s.accountId||u!==s.userId)return null;
      const path=(0,J.path)(s.conversationId);
      return J.jsx(provider.Host,{route:{path},children:J.jsx(J.Frame,{children:J.jsx(page.Render,{
        conversationId:s.conversationId,isInlinePreview:true,isTemporaryChat:false,transcriptPresentation:"panel"
      })})});
    }
    load.d(out,{WorkSideChatContent:()=>Side});
  },
  chat(module,out,load){
    const J=load("base");
    function Render({conversationId:id}){
      const scope=(0,J.useScope)(J.scope);
      scope.get(J.server,id);
      J.useState(null);
      const server=(0,J.read)(J.server,id), prompt=(0,J.read)(J.prompt,id), status=(0,J.read)(J.status,id);
      let stream;
      if(server)stream=(0,J.isStreaming)(status);
      else stream=null;
      const active=stream;
      return J.jsx(J.View,{pendingSubmission:prompt==null?null:{prompt},threadMapping:null,isStreaming:!!server&&active});
    }
    function Page(){
      const navigate=(0,J.useNavigate)();
      const gate="chatgpt.conversations";
      const onClick=id=>navigate((0,J.path)(id));
      return J.jsx(Render,{conversationId:"main",gate,onClick});
    }
    function confirm(){return J.jsx(J.Confirm,{open:true,onOpenChange:null,isDeleting:false,onConfirm:null,title:"chat"});}
    function portal(){return J.createPortal(null,document.body);}
    load.d(out,{ChatGptConversationPage:()=>Page,Render:()=>Render});
  },
  lookup(module,out,load){
    const J=load("base"), actions=load("actions");
    function lookup(scope,id){const server=scope.get(J.server,id);return scope.query.snapshot(J.query,server).getData();}
    function rename(scope,id){
      const item=lookup(scope,id), previous=scope.get(J.hasTitle,id)?scope.get(J.title,id):item.title;
      return J.dialog({draftKey:id,protectedProjectId:null,requireNonEmpty:true,onSave:title=>
        (0,actions.rename)({scope,conversationId:item.conversation_id,previousTitle:previous,title})});
    }
  },
  actions(module,out,load){
    const J=load("base"), titles=load("titles");
    async function rename({scope,conversationId,title}){
      await J.safePost("/conversation/id/{conversation_id}/rename");
      (0,titles.update)({scope,conversationId,title});
    }
    async function remove({scope,conversationId}){await J.safeDelete("/conversation/id/{conversation_id}");}
    load.d(out,{rename:()=>rename,remove:()=>remove});
  },
  titles(module,out,load){
    const J=load("base");
    function update({scope,conversationId,title,onlyIfProvisional}){
      if(!onlyIfProvisional||(0,J.provisional)(scope.get(J.title,conversationId)))scope.set(J.title,conversationId,title);
    }
    load.d(out,{update:()=>update});
  },
  starter(module,out,load){
    const J=load("base");
    function start(scope,options){options.initialChatGptConversationId=(0,J.create)(scope,[]);}
    load.d(out,{startNewConversation:()=>start});
  },
  tools(module,out,load){
    const J=load("base"), asset={};
    function Toggle({composerController,conversationId,isIndicator,isTemporaryChat,onToggle}){
      return J.jsx(J.Button,{color:"ghostActive",size:"toolbar",children:J.jsx(J.Icon,{asset})});
    }
  },
  history(module,out,load){
    const J=load("base");
    function Row({conversationId,conversationOrigin,navigationState,statusState,title,route,href}){
      return J.jsx(J.Row,{title,ariaLabel:title,onClick:()=>J.navigate(route,{navigationSource:"conversation_sidebar"}),
        renderActions:null,statusState});
    }
  }
};
'''
HOST = b'''
export const __rspack_esm_id=65;
export const factories={routes(module,out,load){
  const J=load("base");
  function Host({route,children}){const value=J.useContext(J.Context);return J.jsx(J.Provider,{value,route,children});}
  load.d(out,{Host:()=>Host});
}};
'''


class FloatingChunksTests(TestCase):
    def plan(self, entry=CHUNK):
        modules = {'webview/main.js': entry, 'webview/host.js': HOST,
                   'webview/other.js': HOST.replace(b'id=65', b'id=66').replace(b'function Host', b'function Other')
                                            .replace(b'()=>Host', b'()=>Other')}
        chunks = floating_chunks.Chunks()
        for name, source in modules.items():
            chunks.scan(name, source)
        assets = Path(__file__).parent.parent / 'patches'
        panel = '\n'.join((assets / name).read_text(encoding='utf-8')
                          for name in ('floating-state.js', 'floating-chat.js'))
        host = (assets / 'floating-host.js').read_text(encoding='utf-8')
        changes = floating_chunks.plan(modules.__getitem__, chunks, panel, host)
        return {name: sidebar_patch.apply(modules[name], edits) for name, edits in changes.items()}

    def test_bundled_panel_uses_runtime_exports_and_wraps_each_provider_copy(self):
        patched = self.plan()
        self.assertIn(b'load.d(out,{__customFloatingPanel:()=>__customFloatingPortal})', patched['webview/main.js'])
        self.assertIn(b'(0,load("base")["create"])(scope, [])', patched['webview/main.js'])
        self.assertIn(b'title:__customFloatingHistoryTitle(title)', patched['webview/main.js'])
        for key in ('host', 'other'):
            host = patched[f'webview/{key}.js']
            self.assertIn(b'function __customFloatingNativeHost(', host)
            self.assertIn(b'Promise.all([load.e(42),load.e(65)]).then(()=>load("chat"))', host)

    def test_bundled_planner_rejects_missing_identity_gate(self):
        with self.assertRaisesRegex(UnsupportedPatch, 'identity gate'):
            self.plan(CHUNK.replace(b'u!==s.userId', b'u!==s.unknownIdentity'))
