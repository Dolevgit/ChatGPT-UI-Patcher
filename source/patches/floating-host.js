// Attach within the outermost native route scope in either product. Loading the
// ChatGPT renderer lazily avoids an eager page <-> route-provider import cycle.
var __customFloatingOwner, __customFloatingLazy, __customFloatingLoadBoundary;
const __customFloatingHosts = new Map();
function __customFloatingElect() {
  const first = __customFloatingHosts.keys().next().value;
  for (const [key, notify] of __customFloatingHosts) notify(key === first);
}
function __HOST__(props) {
  const R = __REACT_FACTORY__(), J = __JSX_FACTORY__();
  if (!__customFloatingOwner) __customFloatingOwner = R.createContext(false);
  if (!__customFloatingLoadBoundary) __customFloatingLoadBoundary = class extends R.Component {
    constructor(props) { super(props); this.state = { failed: false }; }
    static getDerivedStateFromError() { return { failed: true }; }
    render() {
      return this.state.failed ? J.jsx("div", { role: "alert",
        style: { position: "fixed", right: 20, bottom: 16, zIndex: 61, padding: 8 },
        children: "Side chats are unavailable. Restart the app to retry." }) : this.props.children;
    }
  };
  const nested = R.useContext(__customFloatingOwner);
  const supported = ["home", "chatgpt-thread", "local-thread", "client-local-thread", "remote-thread"]
    .includes(props.route?.routeKind);
  const children = !nested && supported && !props.route?.__customFloatingSide
    ? J.jsxs(J.Fragment, { children: [props.children, J.jsx(__customFloatingLoadBoundary,
        { children: J.jsx(__customFloatingLoader, { route: props.route }) })] })
    : props.children;
  return J.jsx(__customFloatingOwner.Provider, { value: true,
    children: J.jsx(__customFloatingNativeHost, { ...props, children }) });
}

function __customFloatingLoader(props) {
  const R = __REACT_FACTORY__(), J = __JSX_FACTORY__();
  const token = R.useRef({});
  const [ownsPanel, setOwnsPanel] = R.useState(false);
  R.useEffect(() => {
    __customFloatingHosts.set(token.current, setOwnsPanel);
    __customFloatingElect();
    return () => { __customFloatingHosts.delete(token.current); __customFloatingElect(); };
  }, []);
  if (!__customFloatingLazy) __customFloatingLazy = R.lazy(() =>
    import("__PAGE_PATH__").then(module => ({ default: module.__customFloatingPanel })));
  if (!ownsPanel) return null;
  return __PORTAL_FACTORY__().createPortal(
    J.jsx(R.Suspense, { fallback: null, children: J.jsx(__customFloatingLazy, { route: props.route }) }), document.body);
}

function __customFloatingHistoryText(value) {
  return typeof value === "string" && value.startsWith(__MARKER__) ? value.slice(__MARKER__.length).trim() : value;
}
function __customFloatingTemporaryIcon(props) {
  __NATIVE_UI_INIT__();
  return __JSX_FACTORY__().jsx(__NATIVE_ICON__, { ...props, asset: __NATIVE_ASSET__ });
}
function __customFloatingButton(props) {
  __NATIVE_UI_INIT__();
  return __JSX_FACTORY__().jsx(__NATIVE_BUTTON__, { color: "ghostActive", size: "toolbar", uniform: true, ...props });
}
function __customFloatingHistoryTitle(value) {
  const text = __customFloatingHistoryText(value);
  if (text === value) return value;
  const J = __JSX_FACTORY__();
  return J.jsxs("span", { style: { display: "flex", alignItems: "center", gap: 5,
    border: "1px dashed currentColor", borderRadius: 6, padding: "1px 5px", minWidth: 0 },
    children: [J.jsx(__customFloatingTemporaryIcon, { "aria-hidden": true, style: { width: 16, height: 16, flexShrink: 0 } }),
      J.jsx("span", { style: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: text })] });
}
export { __customFloatingTemporaryIcon, __customFloatingButton };
