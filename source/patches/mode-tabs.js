// onModeSelect('work') is the official ChatGPT product callback: Chat/Work
// remains controlled by the original inner ChatGPT experience selector.
function __SELECTOR__(props) {
  const fixNavigation = __BUG_FIXES__;
  const {
    codexAvailable,
    disabled,
    mode,
    onModeSelect,
    onNewChat,
    "aria-describedby": describedBy,
  } = props;
  const makeTab = (label, target, unavailable) => {
    const selected = target === "codex" ? mode === "codex" : mode !== "codex";
    const blocked = Boolean(disabled || unavailable || (!fixNavigation && onNewChat && !selected));
    return __JSX__.jsx("button", {
      type: "button",
      role: "tab",
      "aria-selected": selected,
      "aria-describedby": describedBy,
      "data-custom-mode": target,
      disabled: blocked,
      title: unavailable ? "Codex is unavailable for this account or workspace" : label,
      onClick: () => {
        if (blocked) return;
        if (onNewChat && (selected || !fixNavigation)) onNewChat();
        else if (!selected) onModeSelect(target);
      },
      onKeyDown: (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        const buttons = [...event.currentTarget.parentElement.querySelectorAll('[role="tab"]')]
          .filter(button => !button.disabled);
        if (!buttons.length) return;
        event.preventDefault();
        const index = buttons.indexOf(event.currentTarget);
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus();
        buttons[next].click();
      },
      style: {
        flex: "1 1 0",
        minWidth: 0,
        padding: "7px 10px",
        border: selected ? "1px solid color-mix(in srgb, currentColor 15%, transparent)" : "1px solid transparent",
        borderRadius: "9px",
        background: selected ? "color-mix(in srgb, currentColor 10%, transparent)" : "transparent",
        color: "inherit",
        font: "inherit",
        fontSize: "13px",
        fontWeight: selected ? 650 : 500,
        lineHeight: "20px",
        cursor: blocked ? "default" : "pointer",
        opacity: blocked ? 0.45 : 1,
        WebkitAppRegion: "no-drag",
      },
      children: label,
    }, target);
  };
  return __JSX__.jsxs("div", {
    role: "tablist",
    "aria-label": "ChatGPT and Codex",
    "data-custom-product-tabs": "v1",
    style: {
      display: "flex",
      gap: "3px",
      padding: "3px",
      width: "100%",
      maxWidth: "240px",
      minWidth: "170px",
      boxSizing: "border-box",
      borderRadius: "12px",
      background: "color-mix(in srgb, currentColor 4%, transparent)",
      color: "inherit",
      WebkitAppRegion: "no-drag",
    },
    children: [makeTab("ChatGPT", "work", false), makeTab("Codex", "codex", !codexAvailable)],
  });
}
