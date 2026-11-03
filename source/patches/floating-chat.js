// ChatGPT tabs shared by both products; all remote actions remain native.

function __customFloatingIcon(name) {
  const paths = { save: "M4 3h13l4 4v14H3V3h1zm3 0v6h10V3M7 21v-8h10v8",
    maximize: "M4 4h16v16H4z", close: "m6 6 12 12M18 6 6 18", minimize: "M5 17h14" };
  return __JSX__.jsx("svg", { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.5, "aria-hidden": true,
    children: __JSX__.jsx("path", { d: paths[name] }) });
}

function __customFloatingPanel(props = {}) {
  __INITIALIZE__
  const accountId = __ACCOUNT__, userId = __USER__;
  return __JSX__.jsx(__customFloatingAccountPanel, props, JSON.stringify([accountId, userId]));
}

// Pointer moves stay in memory; only a completed drag or keyboard move writes metadata.
function __customFloatingPosition(element, position, save, visible) {
  const [point, setPoint] = __REACT__.useState(null);
  const [dragging, setDragging] = __REACT__.useState(false);
  const drag = __REACT__.useRef(null);
  const clamp = value => {
    const rect = element.current?.getBoundingClientRect();
    if (!rect) return value;
    return { x: Math.max(8, Math.min(value.x, window.innerWidth - rect.width - 8)),
      y: Math.max(8, Math.min(value.y, window.innerHeight - rect.height - 8)) };
  };
  const cancel = () => {
    const value = drag.current;
    drag.current = null;
    if (value?.target.hasPointerCapture?.(value.id)) value.target.releasePointerCapture(value.id);
  };
  __REACT__.useEffect(() => () => cancel(), []);
  __REACT__.useEffect(() => {
    const resize = () => {
      if (drag.current) return;
      if (!position) { setPoint(null); return; }
      const rect = element.current?.getBoundingClientRect();
      if (rect && rect.width && rect.height) setPoint(clamp(position));
    };
    // Re-measure when the panel/bar opens, including its changed dimensions.
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [position?.x, position?.y, visible]);
  const finish = (event, commit) => {
    const value = drag.current;
    if (!value || value.id !== event.pointerId) return;
    const next = clamp({ x: value.x + event.clientX - value.startX, y: value.y + event.clientY - value.startY });
    cancel(); setDragging(false);
    setPoint(commit ? next : null);
    if (commit) save(next);
  };
  return {
    dragging,
    style: (point || position) ? { left: (point || position).x, top: (point || position).y, right: "auto", bottom: "auto" } : {},
    handle: {
      onPointerDown: event => {
        if (event.button !== 0 || drag.current || !element.current) return;
        const rect = element.current.getBoundingClientRect();
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = { id: event.pointerId, target: event.currentTarget,
          x: rect.left, y: rect.top, startX: event.clientX, startY: event.clientY };
        setDragging(true); event.preventDefault();
      },
      onPointerMove: event => {
        const value = drag.current;
        if (value?.id === event.pointerId) setPoint(clamp({
          x: value.x + event.clientX - value.startX, y: value.y + event.clientY - value.startY }));
      },
      onPointerUp: event => finish(event, true),
      onPointerCancel: event => finish(event, false),
      onLostPointerCapture: () => { if (drag.current) { cancel(); setDragging(false); setPoint(null); } },
      onKeyDown: event => {
        if (event.key === "Home") { event.preventDefault(); setPoint(null); save(null); return; }
        const delta = { ArrowLeft: [-1,0], ArrowRight: [1,0], ArrowUp: [0,-1], ArrowDown: [0,1] }[event.key];
        const rect = element.current?.getBoundingClientRect();
        if (!delta || !rect) return;
        event.preventDefault();
        const step = event.shiftKey ? 50 : 10;
        const next = clamp({ x: rect.left + delta[0]*step, y: rect.top + delta[1]*step });
        setPoint(next); save(next);
      },
    },
  };
}

function __customFloatingAccountPanel(props) {
  __INITIALIZE__
  if (!__customFloatingBoundary) __customFloatingBoundary = class extends __REACT__.Component {
    constructor(props) { super(props); this.state = { failed: false }; }
    static getDerivedStateFromError() { return { failed: true }; }
    render() {
      return this.state.failed
        ? __JSX__.jsx("div", { role: "alert", style: { padding: 16 },
            children: "This side chat could not be displayed. Your main chat is still available." })
        : this.props.children;
    }
  };
  const scope = __SCOPE__;
  const navigate = __NAVIGATE_HOOK__();
  const accountId = __ACCOUNT__, userId = __USER__;
  const identity = { accountId, userId };
  const owner = accountId && userId ? JSON.stringify([accountId, userId]) : null;
  const initial = () => __customFloatingSession(owner);
  const [state, setState] = __REACT__.useState(initial);
  const [hovered, setHovered] = __REACT__.useState(false);
  const [focused, setFocused] = __REACT__.useState(false);
  const [error, setError] = __REACT__.useState("");
  const [deleteKey, setDeleteKey] = __REACT__.useState(null);
  const [busy, setBusy] = __REACT__.useState(null);
  const creating = __REACT__.useRef(false);
  const acting = __REACT__.useRef(false);
  const panelElement = __REACT__.useRef(null);
  const barElement = __REACT__.useRef(null);
  const current = state.owner === owner ? state : initial();
  const update = action => {
    const previous = __customFloatingSession(owner);
    let next = action(previous);
    if (next === previous) return;
    const written = __customFloatingWrite(next);
    next = { ...next, warning: written ? "" : "Side-chat tabs could not be saved locally. They may not reopen after restarting." };
    __customFloatingSessions.set(owner, next);
    setState(next);
  };
  const create = () => {
    if (!owner || creating.current) return;
    setError("");
    creating.current = true;
    try {
      __customFloatingAssert(scope, identity);
      const id = __CREATE__(scope, []);
      if (typeof id !== "string" || !id) throw new Error("No conversation identifier");
      update(value => ({ ...value, tabs: [...value.tabs, { key: id, clientId: id, serverId: null,
        title: "Side chat " + (value.tabs.length + 1), tagged: false, temporary: true, retry: 0 }],
        selected: id, open: true }));
    } catch (_) { setError("Could not create the side chat. Try again."); }
    finally { creating.current = false; }
  };
  const select = id => update(value => ({ ...value, selected: id, open: true }));
  const minimize = () => update(value => ({ ...value, open: false }));
  const savePosition = key => point => update(value => ({ ...value, layout: { ...value.layout, [key]: point } }));
  const panelPosition = __customFloatingPosition(panelElement, current.layout?.panel, savePosition("panel"), current.open);
  const barPosition = __customFloatingPosition(barElement, current.layout?.bar, savePosition("bar"), hovered || focused);
  __REACT__.useEffect(() => {
    if (!owner || !current.open || deleteKey) return;
    const outside = event => {
      if (panelElement.current?.contains(event.target) || barElement.current?.contains(event.target)) return;
      // Native composer menus can be portaled beside the panel in document.body.
      if (event.target?.closest?.('[role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"], [data-radix-popper-content-wrapper]')) return;
      minimize();
    };
    document.addEventListener("pointerdown", outside, true);
    return () => document.removeEventListener("pointerdown", outside, true);
  }, [owner, current.open, deleteKey]);
  const onTabKey = (event, index) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const count = current.tabs.length;
    if (!count) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? count - 1
      : (index + (event.key === "ArrowRight" ? 1 : -1) + count) % count;
    select(current.tabs[next].key);
    event.currentTarget.closest('[role="tablist"]').querySelectorAll('[role="tab"]')[next]?.focus();
  };
  const metadata = (key, values) => update(value => {
    const tab = value.tabs.find(item => item.key === key);
    if (!tab || Object.entries(values).every(([field, item]) => tab[field] === item)) return value;
    return { ...value, tabs: value.tabs.map(item => item.key === key ? { ...item, ...values } : item) };
  });
  const removeLocal = (key, keep) => update(value => {
    const index = value.tabs.findIndex(tab => tab.key === key);
    const tabs = value.tabs.filter(tab => tab.key !== key);
    return { ...value, tabs, selected: value.selected === key ? tabs[Math.min(index,tabs.length-1)]?.key || null : value.selected,
      open: keep ? false : value.open && tabs.length > 0 };
  });
  const expand = async (tab, kept = false) => {
    try {
      __customFloatingAssert(scope, identity);
      update(value => ({ ...value, open: false }));
      await navigate(__PATH__(tab.serverId || tab.clientId), { state: { navigationSource: "conversation_sidebar" } });
    } catch (_) {
      if (!kept) update(value => value.tabs.some(item => item.key === tab.key) ? { ...value, selected: tab.key, open: true } : value);
      setError(kept ? "Chat kept. Open it from history."
        : "Could not open this chat in the main area. Its tab is still available.");
    }
  };
  const keep = async tab => {
    if (acting.current || !tab.serverId || !tab.loaded) return;
    acting.current = true; setError("");setBusy({ key: tab.key, action: "keep" });
    try {
      await __customFloatingQueue(owner, tab.serverId, async () => {
        const assertRequestCurrent = () => __customFloatingAssert(scope, identity);
        assertRequestCurrent();
        const raw = __customFloatingCurrentTitle(scope,tab);
        await __RENAME__({ scope, conversationId: tab.serverId, title: __customFloatingText(raw) || tab.title,
          expectedIdentity: identity, assertRequestCurrent });
        assertRequestCurrent();
      });
      removeLocal(tab.key, true);
      await expand(tab,true);
    } catch (_) { setError("Could not keep this chat. Its tab remains available. Try again."); }
    finally { acting.current = false; setBusy(null); }
  };
  const confirmDelete = async () => {
    const tab = current.tabs.find(item => item.key === deleteKey);
    if (!tab || acting.current) return;
    acting.current = true; setError("");setBusy({ key: tab.key, action: "delete" });
    try {
      const serverId = scope.get(__SERVER__,tab.clientId) || tab.serverId;
      if (!serverId && __customFloatingPending(scope,tab.clientId)) throw Error("pending");
      const deletedId = await __customFloatingQueue(owner, serverId || tab.clientId, async () => {
        __customFloatingAssert(scope, identity);
        const latest = __customFloatingSession(owner).tabs.find(item => item.key === tab.key);
        const target = scope.get(__SERVER__,tab.clientId) || latest?.serverId;
        if (!target && __customFloatingPending(scope,tab.clientId)) throw Error("pending");
        if (target) await __DELETE__({ scope, conversationId: target });
        return target;
      });
      removeLocal(tab.key, false);setDeleteKey(null);
      if (props.route?.routeKind === "chatgpt-thread" && [deletedId,tab.clientId].filter(Boolean).includes(props.route.conversationId)) {
        try { __customFloatingAssert(scope, identity); await navigate("/",{replace:true,state:{leavingDeletedChatGptConversation:true}}); }
        catch (_) { setError("Chat deleted. Select another chat from history."); }
      }
    } catch (failure) { setError(failure?.message === "pending"
      ? "This chat is still being created. Wait for it to finish connecting, then retry deletion."
      : "Could not delete this chat. Its tab remains available. Try again."); }
    finally { acting.current = false; setBusy(null); }
  };
  if (!owner) return null;
  const active = current.tabs.find(tab => tab.key === current.selected);
  const deleting = current.tabs.find(tab => tab.key === deleteKey);
  const expanded = hovered || focused || barPosition.dragging;
  const buttonStyle = {
    font: "inherit", color: "inherit",
    WebkitAppRegion: "no-drag", whiteSpace: "nowrap", flexShrink: 0,
  };
  const panel = current.tabs.length ? __JSX__.jsxs("section", {
    ref: panelElement,
    role: "region", "aria-label": "ChatGPT side chat", "data-custom-floating-chat": "lifecycle-v3",
    style: {
      display: current.open && active ? "flex" : "none", flexDirection: "column",
      position: "fixed", right: 20, bottom: 80, zIndex: 60,
      width: "min(440px, calc(100vw - 40px))", height: "min(580px, calc(100dvh - 135px))",
      minHeight: 120, border: active?.temporary === false ? "1px solid #888" : "1px dashed #888", borderRadius: 16,
      background: "var(--bg-primary, #202020)", color: "var(--text-primary, #eee)",
      boxShadow: "0 12px 40px #0006", overflow: "hidden", WebkitAppRegion: "no-drag",
      ...panelPosition.style,
    },
    children: [
      __JSX__.jsxs("header", {
        style: { display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderBottom: "1px solid #7775" },
        children: [
          __JSX__.jsx(__BUTTON__, { ...panelPosition.handle, uniform: false, tabIndex: 0,
            "aria-label": "Move side chat", title: "Drag to move · Arrow keys to move · Home to reset",
            style: { flex: 1, minWidth: 0, fontSize: 13, cursor: panelPosition.dragging ? "grabbing" : "grab", touchAction: "none", userSelect: "none", display: "flex", alignItems: "center", gap: 6,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
            children: [active?.temporary === false ? null : __JSX__.jsx(__TEMP_ICON__, { "aria-hidden": true, style: { width: 16, height: 16, flexShrink: 0 } }),
              __JSX__.jsx("span", { style: { minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
                children: "ChatGPT · " + (active?.title || "Side chat") })] }),
          active?.markFailed ? __JSX__.jsx(__BUTTON__, { type: "button", uniform: false, style: buttonStyle, title: "Retry temporary naming",
            onClick: () => metadata(active.key,{retry:(active.retry || 0)+1}), children: "Retry" }) : null,
          __JSX__.jsx(__BUTTON__, { type: "button", style: buttonStyle, "aria-label": "Keep chat in history",
            title: !active?.serverId ? "Send a message before keeping this chat" : !active?.loaded ? "Loading chat title" : "Keep chat in history",
            disabled: !active?.serverId || !active?.loaded || Boolean(busy), onClick: () => keep(active), children: __customFloatingIcon("save") }),
          __JSX__.jsx(__BUTTON__, { type: "button", style: buttonStyle, "aria-label": "Expand side chat",
            title: "Open in main conversation area", disabled: Boolean(busy), onClick: () => expand(active), children: __customFloatingIcon("maximize") }),
          __JSX__.jsx(__BUTTON__, { type: "button", "aria-label": "Minimize side chat", title: "Minimize side chat",
            style: buttonStyle, onClick: minimize, children: __customFloatingIcon("minimize") }),
          __JSX__.jsx(__BUTTON__, { type: "button", "aria-label": "Close and delete side chat",
            title: "Close and delete chat…", style: buttonStyle, disabled: Boolean(busy),
            onClick: () => setDeleteKey(active.key), children: __customFloatingIcon("close") }),
        ],
      }),
      __JSX__.jsx("div", {
        style: { flex: 1, minHeight: 0, position: "relative", overflow: "hidden" },
        children: current.tabs.map(tab => __JSX__.jsx("div", {
          // Inactive conversations stay mounted, retaining drafts and streams.
          style: { display: tab.key === current.selected ? "block" : "none", height: "100%" },
          children: __JSX__.jsx(__customFloatingBoundary, {
            children: __JSX__.jsx(__PROVIDER__, {
              route: { routeKind: "chatgpt-thread", conversationId: tab.serverId || tab.clientId, __customFloatingSide: true,
                pathname: __PATH__(tab.serverId || tab.clientId), routeTemplate: "/c/:conversationId", search: "" },
              children: __JSX__.jsx(__FRAME__, {
                children: __JSX__.jsx(__customFloatingConversation, {
                  tab, owner, identity, onMetadata: metadata,
                  onError: message => setError(previous => message || (previous.startsWith("Could not mark the side chat") ? "" : previous)),
                }, tab.key),
              }),
            }),
          }, tab.key),
        }, tab.key)),
      }),
    ],
  }) : null;
  return __JSX__.jsxs(__JSX__.Fragment, {
    children: [panel, __JSX__.jsxs("div", {
      ref: barElement,
      "data-custom-floating-bar": "v2",
      onMouseEnter: () => setHovered(true), onMouseLeave: () => setHovered(false),
      onFocusCapture: () => setFocused(true),
      onBlurCapture: event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); },
      style: { position: "fixed", right: 20, bottom: 16, zIndex: 61, maxWidth: "calc(100vw - 40px)",
        display: "flex", alignItems: "center", gap: 6, flexWrap: "nowrap",
        color: "var(--text-primary, #eee)", WebkitAppRegion: "no-drag", ...barPosition.style },
      children: [
        (error || current.warning) ? __JSX__.jsx("div", { role: "alert", style: { position: "absolute", bottom: "100%", right: 0, padding: 8 }, children: error || current.warning }) : null,
        __JSX__.jsx(__BUTTON__, { ...barPosition.handle, type: "button", color: "outlineActive",
          style: { ...buttonStyle, cursor: barPosition.dragging ? "grabbing" : "grab", touchAction: "none" },
          title: "Hover to show chats · Drag to move · Arrow keys to move · Home to reset", "aria-label": "Show side chats",
          "aria-expanded": expanded,
          uniform: false,
          children: [__JSX__.jsx(__TEMP_ICON__, { "aria-hidden": true }),
            current.tabs.length ? __JSX__.jsx("span", { children: current.tabs.length }) : null] }),
        __JSX__.jsxs("div", {
          style: { display: expanded ? "flex" : "none", alignItems: "center", gap: 6, minWidth: 0 },
          children: [
            __JSX__.jsx("div", { role: "tablist", "aria-label": "ChatGPT side chats",
              style: { display: "flex", gap: 6, overflowX: "auto", minWidth: 0 },
              children: current.tabs.map((tab, index) => __JSX__.jsxs("div", {
                className: tab.key === current.selected ? "bg-primary-ghost-hover" : undefined,
                style: { display: "flex", flexShrink: 0,
                  border: tab.temporary !== false ? "1px dashed #aaa" : "1px solid #7775",
                  borderRadius: 9, overflow: "hidden", margin: 2 },
                children: [__JSX__.jsx(__BUTTON__, {
                type: "button", uniform: false, role: "tab", "aria-selected": tab.key === current.selected,
                tabIndex: tab.key === current.selected ? 0 : -1, title: tab.title,
                style: { ...buttonStyle, border: 0, borderRadius: 0,
                  fontWeight: tab.key === current.selected ? 600 : 400,
                  maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis" },
                onClick: () => select(tab.key), onKeyDown: event => onTabKey(event, index), children: tab.title,
              }, tab.key), __JSX__.jsx(__BUTTON__, { type: "button", style: { ...buttonStyle, border: 0, borderRadius: 0 },
                "aria-label": "Delete " + tab.title, title: "Close and delete chat…", disabled: Boolean(busy),
                onClick: () => setDeleteKey(tab.key), children: __customFloatingIcon("close") }, tab.key+":delete")],
              }, tab.key)) }),
            __JSX__.jsx(__BUTTON__, { type: "button", color: "outlineActive", style: buttonStyle, "aria-label": "New ChatGPT side chat",
              title: "New ChatGPT side chat", onClick: create, children: "+" }),
          ],
        }),
      ],
    }), deleting ? __JSX__.jsx(__CONFIRM__, {
      open: true, title: deleting.title, isDeleting: busy?.action === "delete",
      onOpenChange: value => { if (!value && !acting.current) setDeleteKey(null); }, onConfirm: confirmDelete,
    }) : null],
  });
}
