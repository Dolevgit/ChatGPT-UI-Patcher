# ChatGPT UI Patcher

A small Windows tool for customizing the combined ChatGPT / Codex desktop app.
Choose your changes and create a separate local copy. The installed original stays untouched.

![Patcher interface](docs/images/patcher.jpg)
*Choose changes and inspect the original and custom app folders from the same window.*

## What can it change?

- **ChatGPT / Codex tabs** — switch products with tabs instead of the dropdown.
- **Hide projects in ChatGPT** — keep recent chats in ChatGPT and projects in Codex.
- **Separate recent chats** — show each product's conversations in its own recent list.
- **Bug fixes** — use your existing Codex history and return to each product's saved
  conversation when switching, or start a new one if there is no saved destination.

Each option can be selected independently.

## How to use it

1. Put `ChatGPT-UI-Patcher.exe` in a writable folder and run it. No installation or administrator rights needed.
2. Choose your changes and click **Create / update ChatGPT**.
3. Click **Open ChatGPT**, or use the `ChatGPT.lnk` shortcut created beside the tool.

The original app must already be installed. Use **Open original folder** to see
where files come from and **Open custom folder** to see the actual edited copy.
New copies live in `ChatGPT-UI-data/app` beside the tool; earlier copies retain their location.

After an official update, close the custom app and click **Create / update ChatGPT** again.
Your custom ChatGPT profile stays in place, so rebuilding does not reset your login.
The first launch or an expired session may still require sign-in.

## Privacy and safety

- The patcher works locally. It contains no telemetry, uploads, remote patch downloads,
  or application-level requests to a server.
- It reads the official installation, copies it, and edits the copy. It does not
  change the original app, its permissions, or its update settings.
- It checks the source signature and rebuilt files before replacing an existing custom copy.
  If a selected change cannot be applied safely, it reports that and keeps the current copy.
- There is no background patcher service. You run it when you want to create or update your copy.

The copied ChatGPT / Codex app still connects to OpenAI normally. Windows signature
validation and reputation checks may also use the network. With **Bug fixes** enabled,
both apps share your existing local Codex data: changes made in one can appear in the other.

This is an unofficial tool. The modified copy no longer has a valid OpenAI executable
signature, and the patcher EXE is unsigned. These safeguards reduce risk; they do not
constitute an independent security audit or a guarantee against every bug.
See [security and privacy](SECURITY.md) for the precise boundaries.

## Compatibility

Designed for Windows x64 and the combined ChatGPT / Codex Store app. The older standalone
ChatGPT Classic app has a different layout. There is no version allowlist: the tool tries
selected changes against the installed code and stops if it cannot identify the required structure.
Future redesigns may need a tool update.

Local integration was tested with version **26.1027.3384.0**. Component tests cover navigation,
sidebar filtering and update recovery; authenticated account rendering still requires user validation.

## For developers

[Build and test](docs/DEVELOPMENT.md) · [How it works](docs/ARCHITECTURE.md) ·
[Validation](docs/VALIDATION.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

This repository contains the patcher source and test fixtures, not the installed application,
modified application, account files or conversation history. Distribute the patcher separately;
users create their own copy locally. This project is not affiliated with OpenAI.
