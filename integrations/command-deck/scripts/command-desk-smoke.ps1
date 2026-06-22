# Command Desk one-shot smoke — Bitwarden sync + agent reply.
# Never prints full secrets. Exit 0 = OK response from agent.
#
# Usage:
#   .\integrations\command-deck\scripts\command-desk-smoke.ps1
#   .\integrations\command-deck\scripts\command-desk-smoke.ps1 -Model "meta-llama/llama-3.3-70b-instruct:free"

param(
    [string]$Model = "openai/gpt-4o-mini",
    [string]$Provider = "openrouter",
    [string]$Toolsets = "memory"
)

$ErrorActionPreference = "Stop"
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$Cli = Join-Path $env:LOCALAPPDATA "command-desk\bin\command-desk.cmd"
$ControlCenter = if ($env:CONTROL_CENTER_REPO) {
    $env:CONTROL_CENTER_REPO
} else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..\control-center") -ErrorAction SilentlyContinue)
}
$BwSync = if ($ControlCenter) {
    Join-Path $ControlCenter "scripts\bitwarden-env-sync.ps1"
} else {
    $null
}

$env:COMMAND_DESK_HOME = $HomeDir
$env:HERMES_HOME = $HomeDir

if (-not (Test-Path $Cli)) {
    Write-Error "CLI ausente. Instale command-desk primeiro."
}

if ($BwSync -and (Test-Path $BwSync)) {
    . $BwSync
} else {
    Write-Warning "bitwarden-env-sync.ps1 nao encontrado (control-center sibling)."
}

if (-not $env:OPENROUTER_API_KEY -and $Provider -eq "openrouter") {
    Write-Error "OPENROUTER_API_KEY ausente. Rode: command-desk secrets bitwarden setup"
}

Write-Host "Smoke: $Provider / $Model (toolsets=$Toolsets)" -ForegroundColor Cyan

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$raw = cmd /c "`"$Cli`" -z `"Reply with exactly: OK`" --cli --safe-mode -m $Model --provider $Provider -t $Toolsets 2>&1"
$exit = $LASTEXITCODE
$ErrorActionPreference = $prevEap
$text = if ($raw -is [array]) { ($raw | Out-String).Trim() } else { [string]$raw }

if ($exit -ne 0) {
    Write-Host $text -ForegroundColor Red
    Write-Host "Smoke FALHOU (exit $exit). Free models: HTTP 429 comum; use -Model openai/gpt-4o-mini" -ForegroundColor Yellow
    exit $exit
}

$lastLine = ($text -split "`n")[-1].Trim()
if ($lastLine -match '^OK') {
    Write-Host "Smoke OK: agent respondeu '$lastLine'" -ForegroundColor Green
    exit 0
}

Write-Host "Smoke FALHOU: resposta inesperada: $lastLine" -ForegroundColor Red
exit 1
