# Build Command Desk web UI → hermes_cli/web_dist
# Windows-friendly: prefers Codex-bundled Node, falls back to node on PATH.
#
# Usage: .\scripts\build-command-desk-web.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$WebDir = Join-Path $RepoRoot "web"
$OutIndex = Join-Path $RepoRoot "hermes_cli\web_dist\index.html"

function Resolve-NodeExe {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".codex\vendor\node-win-x64\node.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\cursor\resources\app\resources\helpers\node.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "node.exe not found (install Node 20+ or use Codex/Cursor bundled runtime)"
}

Write-Host "=== Command Desk web build ===" -ForegroundColor Cyan
$node = Resolve-NodeExe
Write-Host "Node: $node"

Push-Location $RepoRoot
try {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    npm install --workspace web 2>&1 | Out-Host
    $ErrorActionPreference = $prevEap
    if ($LASTEXITCODE -ne 0) {
        throw "npm install --workspace web failed (exit $LASTEXITCODE)"
    }

    Push-Location $WebDir
    try {
        & $node "..\node_modules\vite\bin\vite.js" build --configLoader runner
        if ($LASTEXITCODE -ne 0) {
            throw "vite build failed (exit $LASTEXITCODE)"
        }
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $OutIndex)) {
    throw "Build output missing: $OutIndex"
}

Write-Host "OK: $OutIndex" -ForegroundColor Green
