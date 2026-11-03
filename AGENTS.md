# Start here

This is the shared entry point for developers and coding agents. Read this file first,
then the linked docs relevant to the task. Store durable decisions in these files;
do not rely on previous chats for project context.

## Project and reading order

This portable Windows x64 patcher customizes a separate copy of the combined ChatGPT / Codex
Store app. The installed original is read-only input.

1. [README](README.md): user-visible behavior and options.
2. [Architecture](docs/ARCHITECTURE.md): modules, discovery and update transactions.
3. [Security](SECURITY.md): installation, account-data and validation boundaries.
4. [Development](docs/DEVELOPMENT.md): setup, feature workflow, tests and EXE build.
5. [Validation](docs/VALIDATION.md): actual verification evidence and limits.

## Code map

| Task | Starting points |
| --- | --- |
| GUI, worker/events, folders, shortcuts | `source/patcher.py`, `source/tests/test_gui.py` |
| Option keys, labels and normalization | `source/features.py`; saved-state defaults in `source/patcher.py` |
| Product selector and tabs | `source/selector_patch.py`, `source/patches/mode-tabs.js`, `source/tests/test_selector.py`, `source/tests/tabs.cjs` |
| Sidebar filtering and navigation | `source/sidebar_patch.py`, `source/tests/test_sidebar.py`, `source/tests/sidebar.cjs` |
| Floating ChatGPT chats | `source/floating_patch.py`, `source/patches/floating-state.js`, `source/patches/floating-chat.js`, `source/patches/floating-host.js`, `source/tests/test_floating.py`, `source/tests/floating.cjs` |
| Patch planning, signatures and ASAR integrity | `source/engine.py`, `source/tests/test_engine.py` |
| Launch, profiles, updates, recovery, cleanup | `source/storage.py`, `source/tests/test_updates.py` |
| Copied executable icon | `source/app_icon.py` |
| Packaging | `build.ps1`, `source/build.ps1`, `requirements-build.txt`, `source/requirements.txt` |

`engine.Store` is the existing entry point for the store implemented in `storage.py`.

## Rules to preserve

- Modify only the owned custom copy. Never write to WindowsApps, change installation ACLs,
  replace Store registration, alter official updates or require elevation for normal use.
- Preserve profiles, authentication and conversations across updates. Never delete, copy,
  merge or reset account databases as a patching shortcut. Bug fixes intentionally uses existing
  external Codex data when launching; keep that shared-state behavior explicit.
- Preserve signature checks, hashes, inventory validation, path/link checks, locks and
  transaction recovery. Fix failures at their cause rather than bypassing safeguards.
- Discover required UI structures unambiguously. Missing or ambiguous contracts must fail
  safely before activation. Do not depend on a specific minified symbol, bundle filename or
  version allowlist. Preserve native access gating and navigation fallback.
- Keep **Bug fixes** last in the customization list; insert new options before it.
- Keep options independent, including when disabled. Preserve older saved states and existing
  custom app paths; handle migrations deliberately.
- Access Tk widgets on the GUI thread. Use the existing worker/event mechanism for blocking work.
- Keep the patcher local: no telemetry, uploads, runtime dependency downloads or remote patches.
- Pass machine paths to PowerShell through environment values or structured arguments rather
  than interpolating them into shell source. Support spaces and apostrophes in paths.
- Start menu integration is opt-in and per-user. The entry is **ChatGPT C** and launches the
  patcher with `--launch` to retain store validation and profile handling.
- Never track generated binaries, app copies, profiles, credentials or raw local reports.
  `outputs/`, `build/` and `source/assets/` are ignored. Inspect Git changes before sharing.

## Completing work

- Inspect `git status` first and preserve unrelated changes. Follow existing code conventions;
  avoid unrelated refactors or dependencies.
- For behavior changes, run the Python and Node checks in Development and add focused regression
  coverage where needed. Documentation-only changes need link/command review and `git diff --check`.
- When an updated EXE is requested, run the root `build.ps1` and deliver
  `outputs/ChatGPT-UI-Patcher.exe`. Do not commit generated artifacts.
- Update relevant docs when behavior or design changes. Keep durable design reasons near the code
  or in Architecture. Keep Validation explicit about mocks, component tests and actual app checks;
  process startup alone does not prove authenticated UI behavior.
- Report changes, checks and unresolved limitations. Always provide a concise suggested commit
  message in lowercase conventional format, such as `feat(patcher): add Start menu shortcut`.
  Do not perform the commit unless asked.
