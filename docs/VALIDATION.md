# Validation

Local verification on 2026-11-01 used Windows x64 and combined app version 26.1027.3384.0.
Earlier full-copy integration confirmed preservation of the existing executable path and saved
ChatGPT authentication files, no copied/merged Codex database, rebuilt bundle syntax checks,
and successful process startup. The installed application was not modified.

The current Python suite includes two folder-opening tests in addition to the previous 25 tests.
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

The README screenshot shows the current patcher GUI with both folder buttons. It contains
no account data. Raw local reports and machine-specific paths are intentionally excluded from Git.
