# Minimal web_dist stub (API liveness + redirect) when full Vite build fails.
# Usage: .\scripts\bootstrap-web-dist-stub.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $RepoRoot "hermes_cli\web_dist"

New-Item -ItemType Directory -Force -Path $Dist | Out-Null

@'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Command Desk — DevSSD</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: system-ui, sans-serif; background: #070b12; color: #e2e8f0; padding: 2rem; }
    a { color: #7dd3fc; }
  </style>
</head>
<body>
  <h1>Command Desk</h1>
  <p>Stub UI — API only. Use <a href="/api/status">/api/status</a> or run a full build.</p>
</body>
</html>
'@ | Set-Content -Path (Join-Path $Dist "index.html") -Encoding UTF8

Write-Host "Stub web_dist written: $Dist\index.html" -ForegroundColor Yellow
