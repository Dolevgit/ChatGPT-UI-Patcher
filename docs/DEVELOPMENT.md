# Build and test

Use Windows x64, Python 3.14 with Tk, and Node.js 22 or newer. The end user needs none of these.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
.\build.ps1
```

The EXE is written to `dist/ChatGPT-UI-Patcher.exe`; intermediate files go in `build/`.
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
