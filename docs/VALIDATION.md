# Validation

On 2026-11-04, the installed 26.1029.7803.0 archive resolved the product selector
inside a module factory. Bundle rewrites passed syntax validation for tabs alone
and for tabs with Separate recent chats and Bug fixes. Hide projects in ChatGPT
still hits a structural mismatch on this archive.
These read-only checks did not exercise an authenticated UI.
The GUI regression test checks that a failed project-grouping contract names
Hide projects in ChatGPT and leaves the selection available for the user to change.

The Rspack floating-chat planner resolved the native dependencies in the installed
26.1029.7803.0 archive. The combined tabs, Separate recent chats, Temporary
floating chat and Bug fixes plan rebuilt an isolated archive, passed JavaScript
syntax checks and verified the new archive hash against the copied launcher.
Factory fixture tests cover duplicate route-provider registration, runtime
loading, history edits and failure when an identity check is missing. An isolated
Create / update also completed through activation with those four options.
These checks do not exercise an authenticated floating chat.

Local verification on 2026-11-01 used Windows x64 and combined app version 26.1027.3384.0.
Earlier full-copy integration confirmed preservation of the existing executable path and saved
ChatGPT authentication files, no copied/merged Codex database, rebuilt bundle syntax checks,
and successful process startup. The installed application was not modified.

The Python suite on 2026-11-01 had 30 tests, including folder-opening and Start menu action tests.
It covers archive integrity/tampering, structural discovery, selector symbol changes, independent
sidebar options, navigation fallback, Codex data paths, locks, interrupted update recovery,
profile preservation, startup behavior and resolving original/current-copy folders. Node harnesses
cover tab behavior and native sidebar/navigation fixtures.

The new folder-button tests mock Explorer and check exact paths, including the preserved legacy
copy path and the missing-copy case. They do not claim a visual Explorer inspection. A frozen
GUI self-test checks that the current executable includes both buttons and fits its version row.

Authenticated rendered sidebar behavior is not independently visually verified by these tests.
Passing structural/component tests and launching a process do not establish support for every
account state or future version. No independent security audit or packet capture was performed.

The Start menu action tests cover the missing-copy case, successful creation and error reporting
using a mocked shortcut writer. A separate local Windows COM check created a shortcut in a temporary
Programs folder and verified its target, `--launch` argument, icon and repeat creation with spaces
and an apostrophe in the path. This does not establish Start search indexing or actual app launch
from Start. The entry was subsequently renamed to **ChatGPT C**; the Python and Node suites and
EXE rebuild passed after that rename.

The README screenshot predates the Start menu button and shows both folder buttons. It contains
no account data. Raw local reports and machine-specific paths are intentionally excluded from Git.

## Temporary floating chat (2026-11-03)

The feature is opt-in and named **Temporary floating chat**, immediately before **Bug fixes**,
which remains last. Existing preference keys, defaults and custom-copy paths are preserved.

| Verification | Evidence and limits |
| --- | --- |
| Root EXE build | All 42 Python tests and the Node tabs harness passed. Python tests also invoke the generated floating-module and sidebar Node harnesses. The latest EXE and matching SHA-256 file are in ignored outputs. |
| Structural discovery and integrity | Authored ESM fixtures cover renamed symbols/paths, Unicode offsets, missing/ambiguous contracts, shadowed imports, ASAR round-trip and dependency tampering. Frozen all-options planning resolved the native contracts on installed combined-app version 26.1027.3384.0. |
| Shared hosts and tabs | Mocked React/DOM checks cover both products and home routes, one bar across sibling/nested hosts, lazy loading, body portals, owner handoff, tab selection, keyboard navigation, minimization and independent route props. |
| Titles and persistence | Mocked native state/query services cover the exact `---temporary---` marker, title masking, generated/local versus provisional titles, stable subscription order, expired client aliases, metadata-only restart and corrupt/unavailable localStorage. Unsent drafts are not restored across app restarts. |
| Keep, expand and delete | Generated-module tests cover native action forwarding, confirmation cancellation, service failures/retries, serialized tagging/Keep, expansion failure, first submission before a server ID, identity changes before/after dispatch and prevention of navigation in another account. These are not real network/account-switch tests. |
| Drag and layout | Mocked pointer/DOM tests cover independent panel/bar positions, persistence only on drop, cancel/capture cleanup, keyboard movement/reset, resize clamping, reachable restored handles and legacy metadata without positions. Actual drag behavior still needs live user confirmation. |
| Native appearance | Discovery resolves the original temporary-chat asset/renderer, toolbar button and UI initializer. Generated components forward the native icon and button styles and use a horizontal bar. The handle/add button use the native `outlineActive` variant for persistent contrast. |
| User-reported live acceptance | The user reported all seven core checks passed: one bar in both products, independent main/side conversations and tabs, minimization, marked titles, expand/Keep, deletion from both controls, and restart restoration. This is reported manual evidence, not an automated UI run. |

The user subsequently confirmed the native styling looked better but requested a persistent
border/background for the bar handle and add button. That final visibility adjustment passed
the build checks; its appearance has not yet been confirmed by the user. Real offline recovery,
identity switching during requests, continuous streaming across every navigation transition,
small-window/theme appearance and drag controls are not established by the mocked tests.

No authenticated conversation was created, renamed or deleted by the automated tests. Process
startup and structural preparation do not establish authenticated rendering. Native account
data and the installed original remain outside the cleanup/patching scope.

## Completed-feature cleanup (2026-11-03)

The superseded floating-chat plan and feasibility documents were removed after their durable
design decisions and verification limits were consolidated into Architecture, Development and
this file. Version-specific extracted bundles, diagnostic reports, an older staged EXE and
rebuildable packaging/cache files (about 148 MiB total) were identified for deletion. Automated
command review rejected their removal with `blocked by policy`, so they remain ignored locally. The current release EXE/checksum,
custom app/profile, original idea material and parser dependencies were retained. Portable authored regression fixtures remain part of the repository.
The ignored investigation files are no longer referenced by the maintained documentation.
