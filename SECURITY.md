# Security and privacy

## What the patcher does locally

The Python code reads Windows package metadata, verifies the installed launcher signature,
copies application files into its own data folder, edits the selected UI components and
checks the results. It uses local PowerShell commands for Windows inspection and shortcuts.
Folder buttons pass a validated directory to Windows Explorer; they do not modify that directory.

There is no telemetry client, analytics, updater, upload endpoint, remote patch fetch, or
application-level HTTP/socket client in the patcher. No conversation text is needed to
construct a patch. Build-time dependency installation uses PyPI and is separate from running
the packaged EXE. Windows Authenticode and reputation checks may make their own network requests.
The copied ChatGPT / Codex application and its bundled tools retain their normal networking behavior.
No packet-capture audit has been performed, so this is a source-level statement about the patcher,
not a claim that all child processes or Windows components are offline.

## Files and account data

The official installation is read-only input. The patcher does not take ownership, change ACLs,
register a replacement MSIX, request elevation, or modify Store updates. Application program files
are copied into `ChatGPT-UI-data/app` (or the preserved path of a previous custom copy).
Only the copied launcher and UI archive are modified.

The custom ChatGPT browser profile is `ChatGPT-UI-data/profile`. It can contain login tokens;
never upload the data directory, even when sharing a bug report. Updating program files keeps it.
With Bug fixes enabled, the launched app uses external `CODEX_HOME` or the user's `.codex`
directory. This is shared live Codex state, not a copied or merged database. With the option
disabled it uses the private `ChatGPT-UI-data/codex-home` instead. Shared data is writable by
the launched app, so the original app can see those changes. Do not confuse untouched installation
files with isolated account data.

The optional floating-chat feature stores account-scoped tab IDs, titles, marker flags and floating-control positions in
the existing custom profile's localStorage. It does not copy message bodies or authentication
data. Side chats are regular server conversations with an internal `---temporary---` title
prefix; this does not enable native Temporary Chat privacy/retention behavior. Renaming and
confirmed deletion use the application's existing authenticated actions. The installed original
remains read-only, but regular server history can reflect these changes in other clients.

No retained backup of the original is made. The official shortcut still opens the original.
Temporary old custom program files are used only for transactional replacement and then removed.

## Checks and limits

- A healthy Store package and a valid source launcher signature are required.
- Structural discovery must identify each required native UI contract uniquely.
- Source hashes, copied file inventory, archive integrity, and syntax changes are checked.
- Destination containment and link checks guard against patching the installation or following linked paths.
- Operations are locked, a running custom app blocks replacement, and a journal supports interrupted-update recovery.

These are consistency checks, not a malware scan or proof of behavioral correctness. The copied
launcher loses its valid OpenAI signature when edited; package-identity integrations may differ.
The patcher is unsigned. Use source builds or a release from a source you trust. A checksum detects
a changed download only when the reference checksum itself is trusted. No independent audit is claimed.

## Reporting problems

Before public hosting is configured, report security concerns privately to the repository owner
through a private channel they provide. Do not attach profiles, authentication files, conversation
databases, full app copies or unredacted logs. No reporting address is embedded in this template.
