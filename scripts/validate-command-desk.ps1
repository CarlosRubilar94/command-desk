# End-to-end DevSSD validation — doctor + HTTP probes + web_dist.
#
# Usage: .\scripts\validate-command-desk.ps1

$ErrorActionPreference = "Stop"
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$Cli = Join-Path $env:LOCALAPPDATA "command-desk\bin\command-desk.cmd"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$failed = 0

$env:COMMAND_DESK_HOME = $HomeDir
$env:HERMES_HOME = $HomeDir

function Test-Step {
    param(
        [string]$Name,
        [scriptblock]$Block
    )
    Write-Host ""
    Write-Host "== $Name ==" -ForegroundColor Cyan
    try {
        & $Block
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "exit $LASTEXITCODE"
        }
        Write-Host "OK" -ForegroundColor Green
    } catch {
        Write-Host "FAIL: $_" -ForegroundColor Red
        $script:failed++
    }
}

if (-not (Test-Path $Cli)) {
    Write-Error "CLI ausente. Rode: .\scripts\install-command-desk-dev.ps1"
}

Test-Step "CLI version" { & $Cli --version }
Test-Step "Doctor" { & $Cli doctor }
Test-Step "Dashboard /api/status" {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:9119/api/status" -UseBasicParsing -TimeoutSec 8
    if ($r.StatusCode -ne 200) { throw "HTTP $($r.StatusCode)" }
}
Test-Step "DevSSD /api/devssd/status" {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:9119/api/devssd/status" -UseBasicParsing -TimeoutSec 8
    if ($r.StatusCode -ne 200) { throw "HTTP $($r.StatusCode)" }
    $data = $r.Content | ConvertFrom-Json
    if (-not $data.version) { throw "missing version in payload" }
}
Test-Step "web_dist index.html" {
    $idx = Join-Path $RepoRoot "hermes_cli\web_dist\index.html"
    if (-not (Test-Path -LiteralPath $idx)) {
        throw "missing $idx — run .\scripts\build-command-desk-web.ps1"
    }
}

if ($failed -gt 0) {
    Write-Host ""
    Write-Host "Validation FAILED ($failed step(s))" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Validation OK" -ForegroundColor Green
exit 0
