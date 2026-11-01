const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[2];
function configContext(hide,separate){
 const keys=['Gb','Sv','xv','A9n','Ner','aN','VW','p1i','V$i','B$i','L1i','i0i','sWi','y$i','vCi','lG'];
 const c=Object.fromEntries(keys.map(k=>[k,k]));
 Object.assign(c,{Q:{},K:(_q,fn)=>fn,AN:Boolean,NS:()=>({}),go:{LOCAL_PROJECTS:'local'},t5n:()=>new Map(),W$i:()=>true,$b:e=>e});
 c.xwi=(entries,options)=>({projectKeys:entries.filter(e=>e.kind==='project').map(e=>e.key),chatKeys:entries.filter(e=>e.kind==='conversation').map(e=>e.key)});
 vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(root,`initial-${hide}-${separate}.js`),'utf8'),c);
 const entries=[{key:'p',kind:'project',pinned:true},{key:'gpt',kind:'conversation',source:'chatgpt'},{key:'codex',kind:'conversation',source:'codex'}];
 const get=(key,arg)=>{
   if(typeof key==='function')return key(arg,{get});
   if(key==='Gb')return {isCapable:true,isLoading:false};
   if(key==='Sv'||key==='xv'||key==='V$i'||key==='B$i')return true;
   if(key==='A9n')return 'all';if(key==='VW')return {mode:'project'};
   if(key==='p1i')return 'project';if(['Ner','sWi','y$i','vCi','lG'].includes(key))return [];
   if(key==='i0i')return {layoutInput:{projectEntries:[{key:'unpinned',kind:'project'}],options:{}},chatOrderInput:{},entries,orderedPinnedProjectGroups:[{}],allCodexProjectGroups:[{}],codexProjectGroups:[{}],chatGptProjectTargets:[{}]};
   return false;
 };
 for(const mode of ['chatgpt','codex']){
   const config=c.r0i(mode,{get});
   assert.equal(config.mode,mode==='chatgpt'&&hide?'list':'project');
   assert.equal(config.source,mode==='codex'?'codex':separate?'chatgpt':'all');
   assert.equal(config.conversationFilter,mode==='codex'?'tasks':separate?'chats':'all');
   if(mode==='chatgpt'&&hide)assert.equal(config.flatConversationHistory,true);
   const view=c.a0i({sidebarMode:mode},{get});
   assert.equal(view.entries.some(e=>e.kind==='project'),!(mode==='chatgpt'&&hide));
   assert.equal(view.layout.projectKeys.length,mode==='chatgpt'&&hide?0:2);
   for(const key of ['orderedPinnedProjectGroups','allCodexProjectGroups','codexProjectGroups','chatGptProjectTargets'])assert.equal(view[key].length,mode==='chatgpt'&&hide?0:1);
   assert.deepEqual(Array.from(view.layout.chatKeys),['gpt','codex']);
 }
}
for(const hide of [0,1])for(const separate of [0,1])configContext(hide,separate);

function navigationContext(source){
 const c={_m:'shell',aE:'location',xD:'project',Okt:'memory',Pv:'activeThread',cD:'work',H0e:'codex',Qfe:'/codex-access'};
 Object.assign(c,{rkt:()=>{},pP:()=>{},YOt:l=>l,wkt:()=> 'home',Jf:p=>p==='/',ia:l=>l.pathname,$w:()=>({})});
 c.memory=new Map([['work',{location:{pathname:'/c/gpt-last'},selectedProject:null}],['codex',{location:{pathname:'/local/codex-last'},selectedProject:{projectId:'p',type:'local'}}]]);
 c.location={pathname:'/local/codex-current',state:null};c.mode='codex';c.newChats=0;c.project=null;
 c.store={get:(key,arg)=>key==='memory'?c.memory.get(arg):key==='location'?c.location:key==='project'?c.project:key==='activeThread'?{mode:c.mode}:false,
 set:(key,arg,value)=>{if(key==='memory')c.memory.set(arg,value)}};
 c.nEe=(_s,mode)=>{c.mode=mode};c.dm=(_s,project)=>{c.project=project};
 c.navigate=(route,options={})=>{c.location={pathname:route,state:options.state}};
 c.startNewConversation=()=>{c.newChats++;c.location={pathname:'/',state:{sidebarProductMode:c.mode}}};
 vm.createContext(c);vm.runInContext(source,c);
 c.switchTo=(mode,extra={})=>c.MP(c.store,{codexLocalAccessStatus:'allowed',currentMode:c.mode,nextMode:mode,navigate:c.navigate,startNewConversation:c.startNewConversation,...extra});
 return c;
}
const original=fs.readFileSync(path.join(__dirname,'fixtures/sidebar-primary.js'),'utf8');
let c=navigationContext(original);c.switchTo('work');assert.equal(c.location.pathname,'/local/codex-current','reproduces original route carryover bug');
const patched=fs.readFileSync(path.join(root,'primary-1-1.js'),'utf8');
c=navigationContext(patched);c.switchTo('work');assert.equal(c.location.pathname,'/c/gpt-last');
c.switchTo('codex');assert.equal(c.location.pathname,'/local/codex-current');
c.switchTo('work');assert.equal(c.location.pathname,'/c/gpt-last');
c=navigationContext(patched);c.memory.delete('work');c.switchTo('work');assert.equal(c.location.pathname,'/');assert.equal(c.newChats,1);
c=navigationContext(patched);c.mode='work';c.location={pathname:'/c/gpt-now'};c.memory.delete('codex');c.switchTo('codex');assert.equal(c.location.pathname,'/');assert.equal(c.newChats,1);
c=navigationContext(patched);c.switchTo('work',{restoreNavigation:false});assert.equal(c.location.pathname,'/local/codex-current');
c=navigationContext(patched);c.mode='work';c.switchTo('codex',{codexLocalAccessStatus:'denied'});assert.equal(c.location.pathname,'/codex-access');assert.equal(c.mode,'work');
c=navigationContext(patched);c.switchTo('work',{openHome:true});assert.equal(c.location.pathname,'/');
console.log('Native sidebar options, per-product navigation, new-chat fallback and Codex access checks passed.');
