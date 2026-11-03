const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const saved = new Map();
  globalThis.localStorage = { getItem: key => saved.get(key) || null, setItem: (key,value) => saved.set(key,value) };
  const listeners = new Set();
  globalThis.document = { body: { viewport: true },
    addEventListener(type, listener, capture) { assert.equal(type,'pointerdown'); assert.equal(capture,true); listeners.add(listener); },
    removeEventListener(type, listener) { listeners.delete(listener); } };
  const resizeListeners = new Set();
  globalThis.window = { innerWidth: 1200, innerHeight: 900,
    addEventListener(type, listener) { assert.equal(type,'resize'); resizeListeners.add(listener); },
    removeEventListener(type, listener) { resizeListeners.delete(listener); } };
  const folder = path.join(process.argv[2], 'webview/assets');
  const load = name => import(pathToFileURL(path.join(folder, name)));
  const { ChatGptConversationPage } = await load('entry.js');
  const { Provider, Sidebar } = await load('provider.js');
  const { runtime } = await load('shared.js');
  assert.equal(ChatGptConversationPage().props.conversationId, 'main');
  const main = { native: true };
  const nativeHost = route => {
    const view = Provider({ route, children: main, marker: 'preserve-props' });
    assert.equal(view.type, 'owner-context');
    const host = view.props.children;
    const native = host.type(host.props);
    assert.equal(native.type, 'native-route');
    assert.equal(native.props.marker, 'preserve-props');
    return native;
  };
  for (const routeKind of ['home', 'chatgpt-thread', 'local-thread', 'client-local-thread', 'remote-thread']) {
    const native = nativeHost({ routeKind });
    assert.equal(native.props.children.props.children[0], main);
    assert.equal(native.props.children.props.children.length, 2);
  }
  runtime.nested = true;
  assert.equal(nativeHost({ routeKind: 'local-thread' }).props.children, main);
  runtime.nested = false;
  assert.equal(nativeHost({ routeKind: 'chatgpt-thread', __customFloatingSide: true }).props.children, main);
  assert.equal(nativeHost({ routeKind: 'settings' }).props.children, main);
  const native = nativeHost({ routeKind: 'local-thread' });
  const boundary = native.props.children.props.children[1];
  const loader = boundary.props.children;
  const renderLoader = key => { runtime.begin(key); return loader.type(loader.props); };
  assert.equal(renderLoader('loader-history'),null);
  assert.equal(renderLoader('loader-main'),null);
  await runtime.flush();
  const portal = renderLoader('loader-history');
  assert.equal(portal.type,'portal');
  assert.equal(portal.props.container,document.body); // Escape transformed/clipped sidebar ancestors.
  assert.equal(renderLoader('loader-main'),null); // Independent sibling roots share one owner.
  for (const cell of runtime.instances.get('loader-history')) cell?.cleanup?.();
  assert.equal(renderLoader('loader-main').type,'portal'); // Transfer when the old host unmounts.
  const suspense = portal.props.children;
  const Panel = (await suspense.props.children.type.load()).default;
  let mountedOwner;
  const render = (props = {}) => {
    runtime.begin('panel-wrapper'); const child = Panel(props);
    if (mountedOwner !== child.key) { runtime.reset(); mountedOwner = child.key; }
    runtime.begin(); return child.type(child.props);
  };
  const renderOther = (Component, key) => {
    runtime.begin(key+':wrapper'); const child = Component();
    runtime.begin(key); return child.type(child.props);
  };
  const bar = view => view.props.children[1];
  const controls = view => bar(view).props.children[2];
  const plus = view => controls(view).props.children[1];
  const tabs = view => controls(view).props.children[0].props.children.map(item => item.props.children[0]);
  const flames = view => controls(view).props.children[0].props.children.map(item => item.props.children[1]);
  const panes = view => view.props.children[0].props.children[1].props.children;
  const header = (view,label) => view.props.children[0].props.children[0].props.children.find(item => item?.props['aria-label'] === label);
  const observe = (view,index) => {
    const node = panes(view)[index].props.children.props.children.props.children.props.children;
    runtime.begin('observe:'+node.props.tab.key);
    return node.type(node.props);
  };
  let view = render();
  assert.equal(view.props.children[0], null);
  assert.equal(controls(view).props.style.display, 'none');
  assert.equal(bar(view).props.style.display,'flex');
  assert.equal(bar(view).props.style.flexWrap,'nowrap');
  const nativeIcon=node=>node.type(node.props);
  assert.equal(nativeIcon(bar(view).props.children[1].props.children[0]).props.asset,'native-temporary-asset');
  bar(view).props.onMouseEnter(); view = render();
  assert.equal(controls(view).props.style.display, 'flex');
  plus(view).props.onClick(); view = render();
  assert.equal(runtime.drafts.length, 1);
  assert.deepEqual(runtime.drafts[0].hints, []);
  const panel = view.props.children[0];
  assert.equal(panel.props.style.position, 'fixed');
  assert.equal(panel.props.style.display, 'flex');
  assert.equal(header(view,'Keep chat in history').props.children.type,'svg');
  assert.equal(header(view,'Expand side chat').props.children.props.children.props.d,'M4 4h16v16H4z');
  assert.equal(header(view,'Close and delete side chat').props.children.type,'svg');
  assert.equal(flames(view)[0].props.children.type,'svg');
  for(const label of ['Keep chat in history','Expand side chat','Minimize side chat','Close and delete side chat']) {
    const button=header(view,label),native=button.type(button.props);
    assert.equal(native.type,'button');
    assert.equal(native.props.color,'ghostActive');
    assert.equal(native.props.size,'toolbar');
    assert.equal(native.props.style.background,undefined); // Native hover/focus styles are not overridden.
  }
  assert.equal(nativeIcon(header(view,'Move side chat').props.children[0]).props.asset,'native-temporary-asset');
  await runtime.flush();
  const insidePanel = {}, insideBar = {};
  view.props.children[0].props.ref.current = { contains: target => target === insidePanel,
    getBoundingClientRect: () => ({left:740,top:240,width:440,height:580}) };
  bar(view).props.ref.current = { contains: target => target === insideBar,
    getBoundingClientRect: () => ({left:1000,top:840,width:160,height:44}) };
  for (const listener of listeners) listener({target:insidePanel});
  assert.equal(render().props.children[0].props.style.display,'flex');
  for (const listener of listeners) listener({target:insideBar});
  assert.equal(render().props.children[0].props.style.display,'flex');
  for (const listener of listeners) listener({target:{closest:()=>({nativeComposerMenu:true})}});
  assert.equal(render().props.children[0].props.style.display,'flex');
  for (const listener of listeners) listener({target:{mainComposer:true}});
  view=render();
  assert.equal(view.props.children[0].props.style.display,'none');
  assert.equal(runtime.drafts.length,1);
  tabs(view)[0].props.onClick();view=render();
  await runtime.flush();
  header(view,'Close and delete side chat').props.onClick();view=render();
  await runtime.flush();
  assert.equal(listeners.size,0); // Native confirmation clicks must not minimize the panel.
  view.props.children[2].props.onOpenChange(false);view=render();
  let route = panes(view)[0].props.children.props.children;
  assert.equal(route.props.route.conversationId, 'client-1');
  assert.equal(route.props.route.workSideChat, undefined);
  const chat = observe(view,0);
  assert.equal(chat.props.conversationId, 'client-1');
  assert.equal(chat.props.isTemporaryChat, false);
  assert.equal(chat.props.isInlinePreview, true);
  assert.equal(chat.props.parentConversationId, undefined);
  // A side conversation passes through the shared provider without a second bar.
  const side = route.type(route.props);
  assert.equal(side.props.children.props.children, route.props.children);
  plus(view).props.onClick(); view = render();
  assert.equal(runtime.drafts.length, 2);
  assert.equal(tabs(view).length, 2);
  assert.equal(panes(view).length, 2);
  assert.equal(panes(view)[0].props.style.display, 'none');
  assert.equal(panes(view)[1].props.style.display, 'block');
  tabs(view)[0].props.onClick(); view = render();
  assert.equal(panes(view)[0].props.style.display, 'block');
  assert.equal(panes(view)[1].props.style.display, 'none');
  header(view,'Minimize side chat').props.onClick(); view = render();
  assert.equal(view.props.children[0].props.style.display, 'none');
  assert.equal(panes(view).length, 2);
  tabs(view)[1].props.onClick(); view = render();
  assert.equal(view.props.children[0].props.style.display, 'flex');
  assert.equal(runtime.drafts.length, 2);
  let prevented = false, focused = false;
  tabs(view)[1].props.onKeyDown({ key: 'Home', preventDefault() { prevented = true; },
    currentTarget: { closest: () => ({ querySelectorAll: () => [{ focus() { focused = true; } }] }) } });
  view = render();
  assert.ok(prevented && focused);
  assert.equal(tabs(view)[0].props['aria-selected'], true);
  bar(view).props.onMouseLeave(); view = render();
  assert.equal(controls(view).props.style.display, 'none');
  assert.equal(view.props.children[0].props.style.display, 'flex');
  bar(view).props.onFocusCapture(); view = render();
  assert.equal(controls(view).props.style.display, 'flex');
  // Activating the focused handle must not pin a fake mouse-hover state.
  bar(view).props.children[1].props.onClick?.({ currentTarget: { focus() {} } });
  bar(view).props.onBlurCapture({ currentTarget: { contains: () => false }, relatedTarget: null }); view = render();
  assert.equal(controls(view).props.style.display, 'none');
  // Remounting on another product route restores the same in-memory tab handles.
  nativeHost({ routeKind: 'chatgpt-thread' });
  runtime.reset(); view = render();
  assert.equal(tabs(view).length, 2);
  assert.equal(runtime.drafts.length, 2);
  runtime.account = 'account-b'; view = render();
  assert.equal(view.props.children[0], null);
  assert.equal(tabs(view).length, 0);
  runtime.fail = true;
  plus(view).props.onClick(); view = render();
  assert.equal(view.props.children[0], null);
  assert.equal(bar(view).props.children[0].props.role, 'alert');
  runtime.fail = false;
  plus(view).props.onClick(); view = render();
  assert.equal(tabs(view).length, 1);
  assert.equal(runtime.drafts.length, 3);
  runtime.account = 'account-a'; view = render();
  assert.equal(tabs(view).length, 2);
  runtime.account = null;
  assert.equal(render(), null);
  runtime.account = 'account-a'; view = render();
  runtime.ids.set('client-1','server-1');
  runtime.conversations.set('server-1',{ conversation_id:'server-1', title:'Weather' });
  observe(view,0); await runtime.flush(); view = render();
  assert.equal(runtime.renames.at(-1).title,'---temporary---Weather');
  assert.equal(runtime.renames.at(-1).expectedIdentity.accountId,'account-a');
  assert.equal(tabs(view)[0].props.children,'Weather');
  const owner = JSON.stringify(['account-a','user-a']);
  const storageKey = 'chatgpt-ui-floating-tabs-v1:'+owner;
  let disk = JSON.parse(saved.get(storageKey));
  assert.equal(disk.tabs.length,1); // Unsent client-2 is not presented as a saved server chat.
  assert.deepEqual(Object.keys(disk.tabs[0]).sort(),['id','tagged','temporary','title']);
  assert.equal(disk.tabs[0].id,'server-1');
  runtime.ids.delete('client-1'); // Native ephemeral alias can expire after leaving the route.
  assert.equal(panes(view)[0].props.children.props.children.props.route.conversationId,'server-1');
  assert.equal(observe(view,0).props.conversationId,'server-1');
  await runtime.flush();view=render();
  // Prefix formatting changes only presentation of native history rows.
  const row = Sidebar({title:'---temporary---Weather',conversationId:'server-1',statusState:{},route:'/c/server-1'});
  assert.equal(row.props.ariaLabel,'Weather');
  assert.ok(row.props.title.props.style.border.includes('dashed'));
  assert.equal(nativeIcon(row.props.title.props.children[0]).props.asset,'native-temporary-asset');
  assert.equal(row.props.title.props.children[1].props.children,'Weather');
  assert.equal(Sidebar({title:'Ordinary',statusState:{}}).props.title,'Ordinary');
  runtime.ids.set('client-2','server-2');
  runtime.conversations.set('server-2',{conversation_id:'server-2',title:'Trip'});
  runtime.renameFail = true;
  tabs(view)[1].props.onClick(); view = render();
  observe(view,1); await runtime.flush(); view = render();
  assert.equal(runtime.conversations.get('server-2').title,'Trip');
  const retry = view.props.children[0].props.children[0].props.children.find(item => item?.props.children === 'Retry');
  assert.ok(retry);
  runtime.renameFail = false;
  retry.props.onClick(); view = render();
  observe(view,1); await runtime.flush(); view = render();
  assert.equal(runtime.conversations.get('server-2').title,'---temporary---Trip');
  assert.equal(tabs(view)[1].props.children,'Trip');
  // A fresh module instance mimics an app restart; restore uses server IDs.
  const restart = await import(pathToFileURL(path.join(folder,'page.js')).href+'?restart=1');
  runtime.reset('restart');runtime.begin('restart');
  const restored = renderOther(restart.__customFloatingPanel,'restart');
  assert.equal(tabs(restored).length,2);
  assert.equal(panes(restored)[0].props.children.props.children.props.route.conversationId,'server-1');
  assert.equal(restored.props.children[0].props.style.display,'none');
  assert.equal(runtime.drafts.length,3);
  // Expansion navigates natively without removing the marker or the tab.
  const renameCount = runtime.renames.length;
  runtime.navigateFail=true;
  await header(view,'Expand side chat').props.onClick();view=render();
  assert.equal(view.props.children[0].props.style.display,'flex');
  assert.equal(tabs(view).length,2);
  runtime.navigateFail=false;
  await header(view,'Expand side chat').props.onClick(); view = render();
  assert.equal(runtime.navigations.at(-1).path,'/c/server-2');
  assert.equal(tabs(view).length,2);
  assert.equal(runtime.renames.length,renameCount);
  assert.equal(view.props.children[0].props.style.display,'none');
  tabs(view)[1].props.onClick(); view = render();
  await header(view,'Keep chat in history').props.onClick(); view = render();
  assert.equal(runtime.conversations.get('server-2').title,'Trip');
  assert.equal(tabs(view).length,1);
  assert.equal(runtime.navigations.at(-1).path,'/c/server-2');
  // Merely opening/cancelling the existing confirmation performs no deletion.
  header(view,'Close and delete side chat').props.onClick();view=render();
  let dialog=view.props.children[2];
  assert.equal(dialog.type,'native-confirm');
  assert.equal(runtime.deletes.length,0);
  dialog.props.onOpenChange(false);view=render();
  assert.equal(tabs(view).length,1);
  runtime.deleteFail=true;
  flames(view)[0].props.onClick();view=render();
  await view.props.children[2].props.onConfirm();view=render();
  assert.equal(tabs(view).length,1);
  assert.equal(view.props.children[2].props.open,true);
  assert.equal(runtime.conversations.has('server-1'),true);
  runtime.deleteFail=false;
  await view.props.children[2].props.onConfirm();view=render();
  assert.equal(tabs(view).length,0);
  assert.equal(view.props.children[2],null);
  assert.equal(runtime.conversations.has('server-1'),false);
  assert.deepEqual(JSON.parse(saved.get(storageKey)).tabs,[]);
  // An unsent tab closes locally after confirmation, without a server delete.
  plus(view).props.onClick();view=render();
  const deletesBefore=runtime.deletes.length;
  flames(view)[0].props.onClick();view=render();
  await view.props.children[2].props.onConfirm();view=render();
  assert.equal(runtime.deletes.length,deletesBefore);
  assert.equal(tabs(view).length,0);
  // A request in flight is not an unsent draft: retain it until its server ID arrives.
  plus(view).props.onClick();view=render();
  const pendingId=panes(view)[0].props.children.props.children.props.children.props.children.props.tab.clientId;
  runtime.pending.set(pendingId,'pending prompt');
  flames(view)[0].props.onClick();view=render();
  await view.props.children[2].props.onConfirm();view=render();
  assert.equal(tabs(view).length,1);
  assert.equal(runtime.deletes.length,deletesBefore);
  runtime.pending.delete(pendingId);runtime.statuses.set(pendingId,'streaming');
  await view.props.children[2].props.onConfirm();view=render();
  assert.equal(tabs(view).length,1);
  runtime.ids.set(pendingId,'server-pending');
  runtime.conversations.set('server-pending',{conversation_id:'server-pending',title:'Pending'});
  await view.props.children[2].props.onConfirm();view=render();
  assert.equal(tabs(view).length,0);
  assert.equal(runtime.deletes.at(-1),'server-pending');
  // A queued mutation cannot run under a different account.
  plus(view).props.onClick();view=render();
  const guardedId=panes(view)[0].props.children.props.children.props.children.props.children.props.tab.clientId;
  runtime.ids.set(guardedId,'server-guarded');runtime.conversations.set('server-guarded',{conversation_id:'server-guarded',title:'Guarded'});
  flames(view)[0].props.onClick();view=render();
  const guardedDeletes=runtime.deletes.length;
  const guardedDelete=view.props.children[2].props.onConfirm();
  runtime.account='account-b';view=render();await guardedDelete;
  assert.equal(view.props.children[2],null);
  assert.equal(bar(view).props.children[0],null);
  assert.equal(runtime.deletes.length,guardedDeletes);
  runtime.account='account-a';view=render();
  assert.equal(tabs(view).length,1);
  assert.equal(view.props.children[2],null); // Account remount discards the old confirmation.
  // Keeping a chat waits for an in-flight automatic marker rename.
  const ordinaryRename=runtime.rename.bind(runtime);
  let release,queuedCalls=0;
  runtime.rename=async props=>{queuedCalls++;if(queuedCalls===1)await new Promise(resolve=>{release=resolve});return ordinaryRename(props)};
  observe(view,0);await runtime.flush();view=render();
  assert.equal(queuedCalls,1);
  const keeping=header(view,'Keep chat in history').props.onClick();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(queuedCalls,1);
  release();await keeping;view=render();
  assert.equal(queuedCalls,2);
  assert.equal(runtime.conversations.get('server-guarded').title,'Guarded');
  assert.equal(tabs(view).length,0);
  runtime.rename=ordinaryRename;
  // Prefer the native live generated title over a stale server "New chat".
  plus(view).props.onClick();view=render();
  const titledId=panes(view)[0].props.children.props.children.props.children.props.children.props.tab.clientId;
  runtime.ids.set(titledId,'server-title');runtime.conversations.set('server-title',{conversation_id:'server-title',title:'New chat'});
  runtime.statuses.set(titledId,'streaming');runtime.statuses.set('server-title','streaming');
  const titleRenames=runtime.renames.length;
  runtime.reads=[];observe(view,0);const initialReads=[...runtime.reads];
  await runtime.flush();view=render();
  assert.equal(runtime.renames.length,titleRenames);
  runtime.pending.set('server-title','pending');runtime.reads=[];
  observe(view,0);assert.deepEqual(runtime.reads,initialReads); // Hook order must not depend on pending status.
  await runtime.flush();view=render();
  runtime.titles.set('server-title','A generated title');
  observe(view,0);await runtime.flush();view=render();
  assert.equal(runtime.renames.at(-1).title,'---temporary---A generated title');
  assert.equal(tabs(view)[0].props.children,'A generated title');
  runtime.renameFail=true;
  await header(view,'Keep chat in history').props.onClick();view=render();
  assert.equal(tabs(view).length,1);
  assert.ok(runtime.conversations.get('server-title').title.startsWith('---temporary---'));
  runtime.renameFail=false;
  await header(view,'Keep chat in history').props.onClick();view=render();
  assert.equal(tabs(view).length,0);
  // Drag panel and bar independently, persist on drop, cancel safely, clamp on resize.
  plus(view).props.onClick();view=render();await runtime.flush();view=render();
  const rect = (node,kind) => ({left:node.props.style.left ?? (kind==='panel'?740:1000),
    top:node.props.style.top ?? (kind==='panel'?240:840),
    width:kind==='panel'?Math.min(440,window.innerWidth-40):160,
    height:kind==='panel'?Math.min(580,window.innerHeight-135):44});
  view.props.children[0].props.ref.current={contains:()=>false,getBoundingClientRect:()=>rect(view.props.children[0],'panel')};
  bar(view).props.ref.current={contains:()=>false,getBoundingClientRect:()=>rect(bar(view),'bar')};
  const captured=new Set();
  const target={setPointerCapture:id=>captured.add(id),hasPointerCapture:id=>captured.has(id),releasePointerCapture:id=>captured.delete(id)};
  const pointer=(x,y,id=1,button=0)=>({pointerId:id,button,clientX:x,clientY:y,currentTarget:target,preventDefault(){}});
  const panelHandle=()=>header(view,'Move side chat').props;
  const beforeDrag=saved.get(storageKey);
  panelHandle().onPointerDown(pointer(100,100,1,2));assert.equal(captured.size,0);
  panelHandle().onPointerDown(pointer(100,100));assert.equal(captured.size,1);
  panelHandle().onPointerMove(pointer(-500,-50));view=render();
  assert.equal(view.props.children[0].props.style.left,140);
  assert.equal(view.props.children[0].props.style.top,90);
  assert.equal(saved.get(storageKey),beforeDrag); // No storage churn while dragging.
  panelHandle().onPointerUp(pointer(-500,-50));view=render();
  assert.equal(captured.size,0);
  assert.deepEqual(JSON.parse(saved.get(storageKey)).layout.panel,{x:140,y:90});
  panelHandle().onPointerDown(pointer(100,100));
  panelHandle().onPointerMove(pointer(-5000,-5000));view=render();
  assert.equal(view.props.children[0].props.style.left,8);
  panelHandle().onPointerCancel(pointer(-5000,-5000));view=render();
  assert.equal(view.props.children[0].props.style.left,140);
  const barHandle=()=>bar(view).props.children[1].props;
  barHandle().onPointerDown(pointer(100,100));
  barHandle().onPointerMove(pointer(-400,-400));view=render();
  barHandle().onPointerUp(pointer(-400,-400));view=render();
  assert.deepEqual(JSON.parse(saved.get(storageKey)).layout.bar,{x:500,y:340});
  assert.equal(view.props.children[0].props.style.left,140); // Moving the bar does not move the chat.
  prevented=false;
  panelHandle().onKeyDown({key:'ArrowRight',shiftKey:true,preventDefault(){prevented=true}});view=render();
  assert.ok(prevented);
  assert.equal(view.props.children[0].props.style.left,190);
  await runtime.flush();view=render();
  window.innerWidth=500;window.innerHeight=300;
  for(const resize of resizeListeners)resize();view=render();
  assert.equal(view.props.children[0].props.style.left,52);
  assert.equal(bar(view).props.style.left,332);
  assert.equal(bar(view).props.style.top,248);
  panelHandle().onKeyDown({key:'Home',preventDefault(){}});view=render();
  assert.equal(view.props.children[0].props.style.left,undefined);
  assert.equal(JSON.parse(saved.get(storageKey)).layout.panel,undefined);
  // Persisted positions restore even with no server-backed tabs; legacy records had no layout.
  const repositioned=await import(pathToFileURL(path.join(folder,'page.js')).href+'?restart=layout');
  let positioned=renderOther(repositioned.__customFloatingPanel,'positioned');
  assert.equal(bar(positioned).props.style.left,500);
  assert.equal(tabs(positioned).length,0);
  bar(positioned).props.ref.current={getBoundingClientRect:()=>rect(bar(positioned),'bar')};
  await runtime.flush();positioned=renderOther(repositioned.__customFloatingPanel,'positioned');
  assert.equal(bar(positioned).props.style.left,332); // Restored collapsed handle is reachable without hovering first.
  assert.equal(bar(positioned).props.style.top,248);
  window.innerWidth=1200;window.innerHeight=900;
  flames(view)[0].props.onClick();view=render();await view.props.children[2].props.onConfirm();view=render();
  assert.equal(tabs(view).length,0);
  // A dispatched delete may finish after account switch; never navigate the new account.
  plus(view).props.onClick();view=render();
  const delayedId=panes(view)[0].props.children.props.children.props.children.props.children.props.tab.clientId;
  runtime.ids.set(delayedId,'server-delayed');runtime.conversations.set('server-delayed',{conversation_id:'server-delayed',title:'Delayed'});
  const ordinaryRemove=runtime.remove.bind(runtime);
  let finishDelete;
  runtime.remove=async id=>{await new Promise(resolve=>{finishDelete=resolve});return ordinaryRemove(id)};
  view=render({route:{routeKind:'chatgpt-thread',conversationId:'server-delayed'}});
  flames(view)[0].props.onClick();view=render({route:{routeKind:'chatgpt-thread',conversationId:'server-delayed'}});
  const navigationBefore=runtime.navigations.length;
  const delayedDelete=view.props.children[2].props.onConfirm();await runtime.flush();
  runtime.account='account-b';view=render();const otherTabs=tabs(view).length;
  finishDelete();await delayedDelete;view=render();
  assert.equal(tabs(view).length,otherTabs);
  assert.equal(view.props.children[2],null);
  assert.equal(runtime.navigations.length,navigationBefore);
  runtime.remove=ordinaryRemove;
  runtime.account='account-a';view=render();assert.equal(tabs(view).length,0);
  // Geometry is additive: old metadata without layout remains valid.
  const legacyRecord=JSON.parse(saved.get(storageKey));delete legacyRecord.layout;saved.set(storageKey,JSON.stringify(legacyRecord));
  const legacy=await import(pathToFileURL(path.join(folder,'page.js')).href+'?restart=legacy');
  const legacyView=renderOther(legacy.__customFloatingPanel,'legacy');
  assert.equal(bar(legacyView).props.style.left,undefined);
  assert.equal(bar(legacyView).props.children[0],null);
  saved.set(storageKey,'broken-json');
  const corrupt=await import(pathToFileURL(path.join(folder,'page.js')).href+'?restart=corrupt');
  runtime.reset('corrupt');runtime.begin('corrupt');
  const corruptView=renderOther(corrupt.__customFloatingPanel,'corrupt');
  assert.equal(tabs(corruptView).length,0);
  assert.equal(bar(corruptView).props.children[0].props.role,'alert');
  saved.delete(storageKey);
  const previousWrite=globalThis.localStorage.setItem;
  globalThis.localStorage.setItem=()=>{throw Error('storage full')};
  view=render();plus(view).props.onClick();view=render();
  assert.equal(tabs(view).length,1);
  assert.ok(bar(view).props.children[0].props.children.includes('saved locally'));
  globalThis.localStorage.setItem=previousWrite;
  console.log('Floating lifecycle: native naming, title masking, metadata-only restart, retry, keep, expansion, confirmed deletion, cancellation/failure and storage errors passed; shared-host/tab checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
