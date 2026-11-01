$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'source/build.ps1') -OutputDirectory (Join-Path $PSScriptRoot 'dist') -WorkDirectory (Join-Path $PSScriptRoot 'build')
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
