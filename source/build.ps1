param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..'),
    [string]$WorkDirectory = (Join-Path $PSScriptRoot '../../work')
)
$ErrorActionPreference = 'Stop'
$previousPythonPath = $env:PYTHONPATH
Push-Location $PSScriptRoot
try {
    $OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
    $WorkDirectory = [IO.Path]::GetFullPath($WorkDirectory)
    New-Item -ItemType Directory -Force -Path $OutputDirectory, $WorkDirectory | Out-Null
    $parserDeps = Join-Path $WorkDirectory 'parser-deps'
    $env:PYTHONPATH = $parserDeps + [IO.Path]::PathSeparator + $env:PYTHONPATH
    python -c "import tree_sitter, tree_sitter_javascript"
    if ($LASTEXITCODE -ne 0) {
        python -m pip install --target $parserDeps -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Parser dependencies could not be installed' }
    }
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    node tests/tabs.cjs
    if ($LASTEXITCODE -ne 0) { throw 'Component tests failed' }
    $patchAssets = Join-Path $PSScriptRoot 'patches'
    $iconAssets = Join-Path $PSScriptRoot 'assets'
    $appIcon = Join-Path $iconAssets 'chatgpt.ico'
    # Repository exports omit OpenAI's icon. Obtain it locally for this build.
    if (-not (Test-Path -LiteralPath $appIcon)) {
        $installed = Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1
        if (-not $installed) { throw 'Install the combined ChatGPT / Codex app before building, or supply assets/chatgpt.ico locally.' }
        New-Item -ItemType Directory -Force -Path $iconAssets | Out-Null
        Copy-Item -LiteralPath (Join-Path $installed.InstallLocation 'app/resources/chatgpt-app-dark.ico') -Destination $appIcon
    }
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name ChatGPT-UI-Patcher --icon $appIcon --paths $parserDeps --collect-all tree_sitter --collect-all tree_sitter_javascript --add-data "$patchAssets;patches" --add-data "$iconAssets;assets" --distpath $OutputDirectory --workpath (Join-Path $WorkDirectory 'pyinstaller') --specpath $WorkDirectory patcher.py
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
} finally { $env:PYTHONPATH = $previousPythonPath; Pop-Location }
