// Only IDs, titles and tab metadata are persisted. Message data stays native.
var __customFloatingMarker = __MARKER__;
var __customFloatingBoundary;
var __customFloatingSessions = new Map();
var __customFloatingOperations = new Map();
function __customFloatingText(value) {
  const title = typeof value === "string" ? value : "";
  return title.startsWith(__customFloatingMarker) ? title.slice(__customFloatingMarker.length).trim() : title;
}
function __customFloatingStorageKey(owner) { return "chatgpt-ui-floating-tabs-v1:" + owner; }
function __customFloatingLayout(value) {
  const layout = {};
  for (const key of ["panel", "bar"]) {
    const point = value?.[key];
    if (point && Number.isFinite(point.x) && Number.isFinite(point.y)) layout[key] = { x: point.x, y: point.y };
  }
  return layout;
}
function __customFloatingLoad(owner) {
  const empty = { owner, tabs: [], selected: null, open: false, warning: "", layout: {} };
  if (!owner) return empty;
  try {
    const raw = globalThis.localStorage.getItem(__customFloatingStorageKey(owner));
    if (raw == null) return empty;
    const value = JSON.parse(raw);
    if (value.version !== 1 || value.owner !== owner || !Array.isArray(value.tabs)) throw Error("Invalid tab metadata");
    const seen = new Set();
    const tabs = value.tabs.map(tab => {
      if (!tab || typeof tab.id !== "string" || !tab.id || tab.id.length > 200 || seen.has(tab.id)
          || typeof tab.title !== "string" || typeof tab.tagged !== "boolean") throw Error("Invalid tab");
      seen.add(tab.id);
      return { key: tab.id, clientId: tab.id, serverId: tab.id, title: __customFloatingText(tab.title),
        tagged: tab.tagged, temporary: tab.temporary !== false, retry: 0 };
    });
    return { ...empty, tabs, layout: __customFloatingLayout(value.layout),
      selected: seen.has(value.selected) ? value.selected : tabs[0]?.key || null };
  } catch (_) {
    return { ...empty, warning: "Saved side-chat tabs could not be loaded. Your chats remain in native history." };
  }
}
function __customFloatingSession(owner) {
  if (!__customFloatingSessions.has(owner)) __customFloatingSessions.set(owner, __customFloatingLoad(owner));
  return __customFloatingSessions.get(owner);
}
function __customFloatingWrite(state) {
  if (!state.owner) return true;
  try {
    const tabs = state.tabs.filter(tab => tab.serverId).map(tab => ({ id: tab.serverId,
      title: tab.title, tagged: Boolean(tab.tagged), temporary: tab.temporary !== false }));
    const selected = state.tabs.find(tab => tab.key === state.selected)?.serverId || tabs[0]?.id || null;
    globalThis.localStorage.setItem(__customFloatingStorageKey(state.owner),
      JSON.stringify({ version: 1, owner: state.owner, tabs, selected, layout: __customFloatingLayout(state.layout) }));
    return true;
  } catch (_) { return false; }
}
function __customFloatingAssert(scope, identity) {
  if (scope.get(__ACCOUNT_ATOM__) !== identity.accountId || scope.get(__USER_ATOM__) !== identity.userId)
    throw Error("The active account changed");
}
function __customFloatingPending(scope, clientId) {
  return scope.get(__PENDING__,clientId) != null || __IS_STREAMING__(scope.get(__STATUS__,clientId));
}
function __customFloatingCurrentTitle(scope, tab) {
  const id = scope.get(__SERVER__,tab.clientId) ? tab.clientId : tab.serverId || tab.clientId;
  const local = scope.get(__HAS_TITLE__,id) ? scope.get(__TITLE__,id) : null;
  return typeof local === "string" ? local : scope.query.snapshot(__QUERY__,tab.serverId).getData()?.title || tab.title;
}
function __customFloatingQueue(owner, id, action) {
  const key = JSON.stringify([owner, id]);
  const promise = (__customFloatingOperations.get(key) || Promise.resolve()).catch(() => {}).then(action);
  __customFloatingOperations.set(key, promise);
  promise.finally(() => { if (__customFloatingOperations.get(key) === promise) __customFloatingOperations.delete(key); }).catch(() => {});
  return promise;
}

function __customFloatingConversation(props) {
  const { tab, identity, owner } = props;
  const scope = __SCOPE__;
  const routeId = tab.serverId || tab.clientId;
  const linkedServer = __READ__(__SERVER__, tab.clientId);
  const serverId = linkedServer || tab.serverId;
  const stateId = linkedServer ? tab.clientId : routeId;
  const query = __READ__(__QUERY__, serverId || null);
  const hasLocalTitle = __READ__(__HAS_TITLE__,stateId), localTitle = __READ__(__TITLE__,stateId);
  const rawTitle = hasLocalTitle && typeof localTitle === "string" ? localTitle : query?.data?.title;
  const submission = __READ__(__PENDING__,stateId), status = __READ__(__STATUS__,stateId);
  const turnPending = submission != null || __IS_STREAMING__(status);
  const callbacks = __REACT__.useRef(props);
  callbacks.current = props;
  const alive = __REACT__.useRef(true), attempted = __REACT__.useRef(null);
  __REACT__.useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  __REACT__.useEffect(() => {
    if (!serverId) return;
    try { __customFloatingAssert(scope, identity); } catch (_) { return; }
    const metadata = { serverId, loaded: query?.data != null };
    if (typeof rawTitle === "string") {
      metadata.title = __customFloatingText(rawTitle) || tab.title;
      metadata.temporary = rawTitle.startsWith(__customFloatingMarker);
      if (metadata.temporary) metadata.tagged = true;
    }
    callbacks.current.onMetadata(tab.key, metadata);
  }, [serverId, rawTitle, query?.data != null]);
  __REACT__.useEffect(() => {
    if (!serverId || query?.data == null || tab.tagged || rawTitle?.startsWith(__customFloatingMarker)
        || (__PROVISIONAL__(rawTitle) && turnPending)) return;
    const attempt = serverId + ":" + (tab.retry || 0);
    if (attempted.current === attempt) return;
    attempted.current = attempt;
    callbacks.current.onMetadata(tab.key, { marking: true, markFailed: false });
    __customFloatingQueue(owner, serverId, async () => {
      if (!alive.current) return;
      const assertRequestCurrent = () => __customFloatingAssert(scope, identity);
      assertRequestCurrent();
      const title = __customFloatingText(__customFloatingCurrentTitle(scope,{...tab,serverId}) || rawTitle || tab.title);
      await __RENAME__({ scope, conversationId: serverId, title: __customFloatingMarker + title,
        expectedIdentity: identity, assertRequestCurrent });
      assertRequestCurrent();
      if (alive.current) callbacks.current.onMetadata(tab.key, { tagged: true, temporary: true, title, marking: false });
      if (alive.current) callbacks.current.onError("");
    }).catch(() => {
      if (alive.current) {
        callbacks.current.onMetadata(tab.key, { marking: false, markFailed: true });
        callbacks.current.onError("Could not mark the side chat as temporary. Use Retry in its header.");
      }
    });
  }, [serverId, rawTitle, query?.data != null, turnPending, tab.tagged, tab.retry]);
  return __JSX__.jsx(__RENDERER__, {
    conversationId: routeId, isInlinePreview: true, isTemporaryChat: false,
    sharedConversationId: null, transcriptPresentation: "panel", disableAutoFocus: true,
  }, tab.key);
}
