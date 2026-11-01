# Architecture

`source/patcher.py` is the Tk GUI and short-lived launcher. `engine.py` reads package metadata,
checks signatures, scans UI bundles and verifies/rebuilds ASAR archives. `selector_patch.py`
finds the native product-selector contract using tree-sitter. `sidebar_patch.py` discovers
sidebar and navigation structures. `features.py` defines independent options. `storage.py`
handles locks, validation, staging, activation, cleanup and launch environment. `app_icon.py`
updates resources only in the copied executable.

There is no version catalog. Selected options must resolve unambiguously in the actual installed
code. Unsupported contracts fail before the current custom app is replaced. This is conservative
structural matching, not a promise that all future versions work.

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
