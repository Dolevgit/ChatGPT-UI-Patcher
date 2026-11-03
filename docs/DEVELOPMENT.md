# Build and test

Read [AGENTS.md](../AGENTS.md) first for the project map and working rules.

Use Windows x64, Python 3.14 with Tk, and Node.js 22 or newer. The end user needs none of these.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
.\build.ps1
```

The EXE is written to `outputs/ChatGPT-UI-Patcher.exe`; intermediate files go in `build/`.
Both directories are ignored by Git.
The build runs Python and JavaScript tests first. It bundles the pinned parsers, so the EXE
runs without downloading dependencies. Dependency installation requires network access.
PyInstaller packaging is not claimed to be byte-for-byte reproducible.

The combined ChatGPT / Codex Store app must be installed for a full EXE build. The script copies
its existing flat icon locally into ignored `source/assets/`; no official icon or full application
is included in Git. The resulting EXE embeds that icon. Keep OpenAI branding ownership in mind
when preparing a public binary release.

To run tests without the app installed:

```powershell
python -m pip install -r requirements-build.txt
Push-Location source
python -m unittest discover -s tests -v
node tests/tabs.cjs
Pop-Location
```

To run the GUI from source, use `python source/patcher.py`. Its data directory is then beside
the source launcher rather than the release EXE. Tests mock installation inspection and use
temporary folders; they do not patch the installed app. The Windows CI workflow runs the same tests.

## Adding a feature

1. Define the visible result: a patch option, patcher UI action or launch change. Use the
   map in `AGENTS.md` to find the relevant module and existing tests.
2. For a patch option, add a stable key/label in `source/features.py`. Review `normalize()` and
   the GUI's defaults/saved-state loading so older state files work. Connect discovery and required
   contract counts in `engine.plan_changes()` and the relevant rewrite in `selector_patch.py`,
   `sidebar_patch.py` or `patches/mode-tabs.js`. Launch changes belong in `storage.py`;
   ordinary patcher actions usually need no new customization key.
3. For UI actions, reuse `App.run()`, the worker/event queue and `App.widgets` so blocking work,
   disabled controls and error reporting behave consistently. Keep English UI labels consistent.
4. Add focused tests/fixtures. For discovery changes cover missing/ambiguous structures and renamed
   symbols. Check new options independently, disabled and in relevant combinations. Update changes
   must preserve profiles and recovery.
5. Run the checks above. Build the EXE when requested or when frozen/packaging behavior needs
   validation. Keep generated files and local reports in ignored directories.
6. Update README for visible behavior, Architecture for design decisions and Validation for new
   verification evidence/limits. Report actual check results and a suggested conventional commit.

For an AI task, paste this and replace the feature placeholders:

```text
Start by reading AGENTS.md at the repository root and the relevant linked documentation.
Implement X + Y + Z using the project's existing architecture and safety rules.
Preserve unrelated changes, update the relevant docs, and run checks appropriate to the change.
If an EXE is requested, build it into the ignored outputs directory.
Report the result, checks and limitations, and suggest a lowercase conventional commit message.
```

These files are maintained project context, not an automatic transcript of past chats.
Update them when decisions change how future work should be done. Do not include secrets
or machine-specific account data.

## Publishing

Upload this repository folder, not the working output folder that contains your real application
copy. Review `git status --short` and staged files before pushing. `.gitignore` excludes account
folders, databases, application binaries, dependency folders and generated assets. Ignore rules
are defense in depth and do not sanitize files that were already tracked.

Publish only the patcher EXE and its SHA-256 checksum as release assets. Do not publish
`ChatGPT-UI-data`, shortcuts containing local paths, validation reports containing local paths,
or copied application files. A source ZIP can be generated from tracked files with `git archive`
after a commit. No repository has been created remotely and no commit or push is performed here.

Commit style: lowercase conventional commits, e.g. `feat(gui): add application folder buttons`.

## Floating ChatGPT chats

The optional floating-chat feature is disabled by default. `test_floating.py` discovers contracts in authored
ESM fixtures and runs `floating.cjs` against the generated module. It covers renamed symbols and
bundle paths, Unicode byte offsets, missing/ambiguous structures, identity gates, an ordinary
draft, independent route props, both product hosts, lazy loading, nested-host suppression,
tab switching, hover/focus, keyboard navigation, minimize/reopen, host remounts and creation failure. Rendering and state hooks
are mocked; these checks are not an authenticated Electron UI test.

To test the actual app, build the patcher normally, close the custom app, enable
**Temporary floating chat** and click **Create / update ChatGPT**. Existing
customizations can stay selected. Open the custom app in either ChatGPT or Codex, including its
home/new-chat screen. The side chats are regular ChatGPT chats in either product.

1. Hover over the **temporary-chat handle** at the bottom right and click **+**. Expect a small floating panel over the main conversation,
   without shrinking the main area. The panel must show a regular ChatGPT composer.
2. In a disposable test conversation, send an innocuous test message. Verify the panel's response
   and confirm the main conversation did not navigate or receive that message.
3. Type distinct drafts in the main and side composers. Send from each and check independence.
4. Create a second tab with **+**, switch between the two and check their drafts and responses.
   The selected tab must have the native neutral selected background. Hover over header/bar buttons
   and use keyboard focus: feedback must be visible, with unavailable buttons muted.
   While a side response is arriving, minimize the panel and reopen it by selecting its tab.
   Check that tab switching/minimizing did not create another conversation or lose its response.
   Click inside the side chat and its bar: it must stay open. Click the main composer: the
   panel must minimize without losing drafts or streams. Reopen from its tab.
   Moving the pointer away from the bar should collapse only the bar; keyboard focus also opens it.
5. Check native history for the sent side chat: the customized title must hide `---temporary---`
   and show dashed styling/an icon. Native rename UI or another client may reveal the raw prefix.
6. Verify exactly one bar appears when history and a main chat are both visible; it must stay
   at the viewport bottom right, outside the sidebar. Switch to Codex and back. The same bar and tabs should remain available; creating a tab while
   in Codex must still open a regular ChatGPT chat. Also check navigation and native access restrictions.

7. Wait for the real title to appear in the tab, restart the custom app and check that sent-chat
   tabs restore and load their original conversations. Unsent local drafts are not restored.
8. Use the **square (expand)** button: the same chat must open in the main area with its marker and tab retained. Select
   another history chat, then reopen the tab. Test this starting from both products.
9. Use the **disk (keep)** button: after the native rename succeeds, the tab must disappear and the regular chat must
   open in the main area. On failure the tab stays. Check the server title no longer has the marker.
10. Use the **×** on a tab or in the panel header to open the native delete confirmation. Cancel first and verify no deletion.
    Confirm on a disposable test chat, then check history and the tab. A failed deletion must keep
    the tab/dialog. Also test deleting the chat currently expanded in the main area.
11. During first-message submission, try deletion before a server ID arrives. It must retain the
    tab and ask for a retry instead of treating the in-flight chat as an unsent draft.

12. Drag the panel by its title and the bar by the temporary-chat handle. Each must move independently,
    stay inside the viewport and remember its position after restart. Resize the app smaller:
    handles must remain reachable. Try arrow keys, Shift+arrows and Home to reset each handle.
    Cancel a drag and check its previous saved position is retained.
13. On disposable chats, test a failed rename/delete while offline, then reconnect and retry.
    Switch accounts with a delete confirmation open: the other account must not inherit the
    dialog, tabs, error or layout. A request already dispatched can finish on the old account;
    it must not navigate the new account. Never expect a server request to be undone by switching.

The temporary tag is attempted after the native server ID/query data arrive. Failed tagging
shows **Retry** in the panel header. Draft labels become the actual clean title once available.
The current tests use mocked services and hook scheduling, including rename failure/retry,
mark/keep ordering, account changes, deletion failure/cancellation, storage corruption/quota and
restart metadata. They do not establish real server title timing or actual dialog appearance.

Report errors as short descriptions; do not share profiles, credentials or raw account reports.
To turn floating chats off, close the custom app and rebuild its copy with this option unchecked.
The patcher preserves the existing profile and does not remove regular chats from history.
