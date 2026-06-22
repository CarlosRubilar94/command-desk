# Start Command Desk dashboard in background (:9119)
$ErrorActionPreference = "Stop"
$HomeDir = Join-Path $env:USERPROFILE ".command-desk"
$Cli = Join-Path $env:LOCALAPPDATA "command-desk\bin\command-desk.cmd"
$RepoRoot = if ($env:COMMAND_DESK_REPO) {
    $env:COMMAND_DESK_REPO
} else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}
$WebDist = Join-Path $RepoRoot "hermes_cli\web_dist\index.html"

if (-not (Test-Path $Cli)) {
    Write-Error "CLI ausente. Instale command-desk primeiro."
}

$env:COMMAND_DESK_HOME = $HomeDir
$env:HERMES_HOME = $HomeDir

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:9119/api/status" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) {
        Write-Host "Dashboard ja ativo: http://127.0.0.1:9119"
        exit 0
    }
} catch {}

if (-not (Test-Path $WebDist)) {
    Write-Host "Web UI ausente; tentando build..." -ForegroundColor Yellow
    Push-Location $RepoRoot
    try {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        npm install --workspace web 2>&1 | Out-Host
        npm run build -w web 2>&1 | Out-Host
        $ErrorActionPreference = $prevEap
    } finally {
        Pop-Location
    }
    if (-not (Test-Path $WebDist)) {
        Write-Host "Build falhou; usando stub web_dist (API only)..." -ForegroundColor Yellow
        $stub = Join-Path $RepoRoot "scripts\bootstrap-web-dist-stub.ps1"
        if (Test-Path $stub) { & $stub }
    }
    if (-not (Test-Path $WebDist)) {
        Write-Error "Nao foi possivel preparar web_dist"
    }
}

Start-Process -FilePath $Cli -ArgumentList "dashboard","--port","9119","--no-open","--skip-build" -WindowStyle Hidden
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:9119/api/status" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) {
            Write-Host "Dashboard iniciado: http://127.0.0.1:9119"
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
Write-Host "Dashboard em startup (pode levar mais tempo): http://127.0.0.1:9119" -ForegroundColor Yellow
