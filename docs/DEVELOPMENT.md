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
