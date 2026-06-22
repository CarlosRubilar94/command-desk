# DevSSD — configure Command Desk default OpenRouter model (non-interactive).
# Loads OPENROUTER_API_KEY via Bitwarden sync then sets config.yaml.
#
# Usage:
#   .\scripts\setup-devssd-model.ps1
#   .\scripts\setup-devssd-model.ps1 -Model "meta-llama/llama-3.3-70b-instruct:free"

param(
    [string]$Model = "google/gemini-2.5-flash"
)

$ErrorActionPreference = "Stop"
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$Cli = Join-Path $env:LOCALAPPDATA "command-desk\bin\command-desk.cmd"
$BwSyncCandidate = Join-Path (Split-Path $PSScriptRoot -Parent) "..\control-center\scripts\bitwarden-env-sync.ps1"
$BwSync = $null
if (Test-Path -LiteralPath $BwSyncCandidate) {
    $BwSync = (Resolve-Path -LiteralPath $BwSyncCandidate).Path
}
if (-not $BwSync) {
    $BwSync = "C:\Users\Vinicius\Documents\Codex\control-center\scripts\bitwarden-env-sync.ps1"
}

$env:COMMAND_DESK_HOME = $HomeDir
$env:HERMES_HOME = $HomeDir

if (-not (Test-Path $Cli)) {
    Write-Error "CLI ausente. Rode: .\scripts\install-command-desk-dev.ps1"
}

if (Test-Path $BwSync) {
    . $BwSync
} else {
    Write-Warning "bitwarden-env-sync.ps1 nao encontrado; usando env existente."
}

if (-not $env:OPENROUTER_API_KEY) {
    Write-Error "OPENROUTER_API_KEY ausente. Complete: command-desk secrets bitwarden setup"
}

& $Cli config set model.provider openrouter | Out-Null
& $Cli config set model.default $Model | Out-Null

Write-Host "Modelo DevSSD: openrouter / $Model" -ForegroundColor Green
Write-Host "Valide: command-desk doctor" -ForegroundColor DarkGray
