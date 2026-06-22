# Command Desk — doctor smoke (Command Deck runbook)
$ErrorActionPreference = "Continue"
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$Cli = Join-Path $env:LOCALAPPDATA "command-desk\bin\command-desk.cmd"

$env:COMMAND_DESK_HOME = $HomeDir
$env:HERMES_HOME = $HomeDir

if (-not (Test-Path $Cli)) {
    Write-Host "CLI ausente. Instale command-desk (ver README.md)." -ForegroundColor Yellow
    exit 1
}

& $Cli doctor 2>&1
exit $LASTEXITCODE
