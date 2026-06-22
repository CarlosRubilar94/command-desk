# Dev install — Command Desk (editable fork, no admin)
# Usage: .\scripts\install-command-desk-dev.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$VenvDir = Join-Path $env:LOCALAPPDATA "command-desk\venv"

Write-Host "=== Command Desk dev install ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host "Home: $HomeDir"
Write-Host "Venv: $VenvDir"

New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $VenvDir) | Out-Null

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $uv = Get-Command uv -ErrorAction SilentlyContinue
}
if (-not $uv) { throw "uv not found after install" }

if (-not (Test-Path $VenvDir)) {
    & uv venv $VenvDir --python 3.12
}

$python = Join-Path $VenvDir "Scripts\python.exe"

& uv pip install --python $python -e "${RepoRoot}[all]" 2>&1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$BinDir = Join-Path $env:LOCALAPPDATA "command-desk\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

@(
    "@echo off",
    "set COMMAND_DESK_HOME=$HomeDir",
    "set HERMES_HOME=$HomeDir",
    "`"$python`" -m hermes_cli.main %*"
) | Set-Content -Path (Join-Path $BinDir "command-desk.cmd") -Encoding ASCII

@(
    "@echo off",
    "set COMMAND_DESK_HOME=$HomeDir",
    "set HERMES_HOME=$HomeDir",
    "`"$python`" -m hermes_cli.main %*"
) | Set-Content -Path (Join-Path $BinDir "hermes.cmd") -Encoding ASCII

Write-Host ""
Write-Host "Installed. Add to PATH (optional):" -ForegroundColor Green
Write-Host "  $BinDir"
Write-Host ""
Write-Host "Run:" -ForegroundColor Green
Write-Host "  `$env:COMMAND_DESK_HOME = `"$HomeDir`""
Write-Host "  & `"$BinDir\command-desk.cmd`" doctor"
