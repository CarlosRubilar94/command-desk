# Start Command Desk gateway (messaging/API :8642)
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$Cli = Join-Path $env:LOCALAPPDATA "command-desk\bin\command-desk.cmd"

if (-not (Test-Path $Cli)) {
    Write-Error "CLI ausente. Instale command-desk primeiro."
}

$env:COMMAND_DESK_HOME = $HomeDir
$env:HERMES_HOME = $HomeDir

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) {
        Write-Host "Gateway API ja ativo: http://127.0.0.1:8642"
        exit 0
    }
} catch {}

Start-Process -FilePath $Cli -ArgumentList "gateway","start" -WindowStyle Hidden
Start-Sleep -Seconds 4
Write-Host "Gateway start solicitado. Verifique: http://127.0.0.1:8642/health"
