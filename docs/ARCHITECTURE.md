# Architecture

`source/patcher.py` is the Tk GUI and short-lived launcher. `engine.py` reads package metadata,
checks signatures, scans UI bundles and verifies/rebuilds ASAR archives. `selector_patch.py`
finds the native product-selector contract using tree-sitter in both flat bundles and module
factory bodies. `sidebar_patch.py` discovers
sidebar and navigation structures. `features.py` defines independent options. `storage.py`
handles locks, validation, staging, activation, cleanup and launch environment. `app_icon.py`
updates resources only in the copied executable.

There is no version catalog. Selected options must resolve unambiguously in the actual installed
code. Unsupported contracts fail before the current custom app is replaced. This is conservative
structural matching, not a promise that all future versions work.

Project hiding resolves the sidebar grouping selector from the configuration's native read.
When the selector is imported through a factory namespace, discovery follows that import and
its export within the same chunk. ChatGPT's list override then applies to all native consumers.

## Update transaction

1. Validate source package and plan selected patches.
2. Inventory and copy into a temporary `.build-*` directory.
3. Recheck source/copy hashes, rewrite selected bundles, rebuild archive integrity and update the copied launcher reference/icon.
4. Verify archive and file inventory; only the launcher and archive may differ.
5. Journal the switch, temporarily rename the prior custom program directory and activate the verified copy at the same path.
6. Publish state, delete temporary old program files and finish cleanup.

An interrupted switch is recovered on the next operation. Profiles are outside replaced program
files. Earlier release-directory layouts migrate without changing the existing executable path.
There is no original backup or user-facing restore mode.

The Bug fixes launch environment points `CODEX_HOME` to existing external Codex data and keeps
`CODEX_ELECTRON_USER_DATA_PATH` / `--user-data-dir` on the custom ChatGPT profile. Native product
navigation restores a saved destination for each mode and retains access gating and new-chat fallback.

Original package signatures cannot be preserved after changing signed content. The tool does not
re-sign a package or bypass source signature checks. Archive hash regeneration is integrity bookkeeping,
not restoration of publisher trust. Runtime DLLs and validation settings are left unchanged.

## Floating ChatGPT chats

`floating_patch.py` follows named native exports and relative ESM imports to discover the
regular ChatGPT page, panel renderer/frame/route provider, identity gates and ordinary draft
initializer. For Rspack archives, `floating_chunks.py` follows factory exports (getters or direct
values), namespace dependencies and the native side-chat loader. It recognizes both single
chunk IDs and ID arrays. It wraps every archived copy of the route
provider because separate chunks can register the same module ID. Both paths resolve compiled
symbols from syntax and module relationships. Missing or ambiguous contracts fail preparation.
Additional imported dependencies are read through the engine's archive integrity checks.

The patch preserves the native ChatGPT page and wraps the shared native route provider. A React
context admits the bar only in the outermost conversation/home host, including Codex routes,
and suppresses duplicate bars in nested native panes and the floating chats themselves.
Independent sibling roots also share a module-local mount lease: only one loader renders the
panel, and ownership transfers on unmount. The native portal runtime is structurally resolved
from its createPortal usage and imported factory assignment. Rendering into document.body
keeps fixed positioning outside transformed or clipped sidebar ancestors.
`patches/floating-host.js` lazily loads the panel export. The ESM path uses a relative import
of the native ChatGPT page module. The Rspack path loads the side-chat factory through the native
loader and mounts the portal there. It uses the native page's existing renderer export so any
registered copy of the page factory can render the panel. An error boundary
isolates lazy-loading failures from the main app. Original host props and children are retained.

`patches/floating-chat.js` supplies the tab bar and single visible panel. Each tab uses a separate
native conversation route and frame with
an ordinary ChatGPT draft. It does not supply the native `workSideChat` adapter, parent history,
Codex execution context, hidden-history flags or the native Temporary Chat flag. Native access
checks inside the renderer remain in place. No custom requests or account database changes
are introduced. Inactive tabs and minimization hide mounted children instead of unmounting them.
The bar opens on hover or keyboard focus; collapsing it does not minimize the conversation.
A captured document pointerdown outside both panel and bar minimizes it without intercepting
the main click. The listener is disabled during delete confirmation and removed on cleanup.
SVG controls show a disk for Keep, a Windows-style square for Expand, and a close cross on
both the tab and header; both crosses invoke the same native confirmation.

The option is independent and disabled by default, including for older saved preferences.
`floating-state.js` maintains an account-and-user-keyed registry. A versioned localStorage record
in the existing custom browser profile stores only server IDs, clean titles, marker status and
the selected server ID and optional independent panel/bar positions. Version 1 metadata without
positions remains valid. Invalid geometry is ignored without discarding valid tabs. Content is loaded by the native conversation query. Pending/unsent
client IDs are not persisted as if they were durable server conversations. Restored panels start
minimized. Corrupt/foreign records and unavailable storage produce an error without touching
native conversations. The module-local registry also retains handles through a host remount;
this does not promise uninterrupted streaming through every product/navigation transition.

Discovery follows the existing rename UI to the native server-ID and conversation-query atoms,
then finds their subscription hook in the renderer. The native turn-render contract supplies
the pending-submission atom and streaming-status helper. No timer guesses when a new chat is
ready. Once its server ID and title are available, the native rename action adds the exact
internal marker `---temporary---`. A failed marker rename has an explicit Retry action. Explicit
and automatic operations are serialized per account/conversation; rename passes native expected
identity and checks the live account before and after the request.

The native rename UI's local-title selector and provisional-title predicate prevent stale query
data such as "New chat" from winning over a live generated title. Provisional titles are not
tagged while a turn is still pending; a completed untitled chat may retain its default title.
Native subscriptions are unconditional to preserve React hook order. Once a server ID is known,
the panel route uses it, retaining the tab's stable UI key; this also survives disposal of an old
client/server alias. Live client-state lookups use that alias while it remains available.

History formatting edits target the regular ChatGPT history-row contract, only at its rendered
title/aria-label/hover title expressions. A marked title becomes clean text with a dashed span
and small icon; raw model/cache/server titles and native rename-dialog input remain intact.
Manually removing the prefix stops temporary styling and does not trigger automatic re-tagging
of a chat that was already marked. Manually adding it elsewhere styles that title without
enrolling it into the tab registry or authorizing any automatic deletion.

Keep removes the marker with the original rename action, unregisters the tab after success and
opens the regular chat using the same router hook/path builder as native history navigation.
Expand uses that navigation without renaming or removing the tab. The native delete dialog
controls destructive closure; only the rejecting native delete action's success removes a tab.
A pending first submission without a server ID cannot be discarded as an unsent local draft:
the native pending/status selectors block closure until its server ID is available. A genuinely
unsent draft is discarded locally after confirmation. Deleting the chat currently shown in the
main area returns to the native home route. Native access gates and error handling remain intact.

The user reported successful live checks of both product hosts, independent chats, a single
bar, minimization, title markers, keep/expand/delete and restart restoration. Error recovery
and identity-switch cases retain mocked coverage. Selected tabs use the native neutral selected surface. Bar/header controls reuse the native
temporary-chat toolbar button, including its hover, focus and disabled styles.


The account subscription wrapper keys the interactive panel by account/user so dialogs,
errors, busy state and drag capture unmount when identity changes. Native operations still
check live identity; a delete finishing after an account switch may update the original
account's local tab registry but cannot navigate the new account. Failed expansion reopens
the original panel instead of leaving its chat hidden.

Panel-title and bar-handle pointer capture provide independent dragging. Movement updates
only React state; completion writes validated coordinates through the existing metadata
record. Cancel/unmount releases capture, and cancelled moves preserve the saved position.
Resize and open/close remeasurement clamp saved coordinates to the viewport. Unpositioned
controls retain their default bottom-right anchors. Arrow keys move 10 px (Shift: 50 px), and
Home removes that handle's saved position. No conversation content is read for layout.


Native temporary-chat appearance is resolved from the toggle's semantic props contract
(composerController, conversationId, isIndicator, isTemporaryChat, onToggle). Its imported
asset/renderer and ghostActive toolbar button are reused through exported wrappers, with the
native UI initializer called before rendering. Missing or ambiguous contracts fail preparation.
The same icon replaces the flame in the bar, panel title and marked history rows. No native
temporary-chat privacy flag or action is activated. The bar uses a single nonwrapping flex row;
its error alert is positioned above that row without moving the icon above the tabs.


The floating-chat design is implemented; its original plan and feasibility notes have been
retired. Current behavior is documented in README and Development, and verification evidence
in Validation. The original request remains in [idea](../idea/What%20feature%20would%20you%20like%20to%20see.txt),
[additional information](../idea/Additional%20information.txt) and the [sketch](../idea/סקיצה.png).
Those historical inputs proposed native Temporary Chat; the implemented ordinary-chat marker
and confirmed-delete lifecycle described above is the current design.
