# Exécute toutes les vérifications qualité. Usage : powershell -ExecutionPolicy Bypass -File scripts\check.ps1 [-SkipE2E]
param([switch]$SkipE2E)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = ".venv\Scripts\python.exe"

function Run($label, [scriptblock]$block) {
    Write-Host "`n==> $label" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) { throw "Échec : $label" }
}

Run "Lint Python (ruff)" { & $py -m ruff check . }
Run "Tests backend (pytest)" { & $py -m pytest -q }
Run "Vulnérabilités Python connues (pip-audit)" { & $py -m pip_audit -r requirements.txt }
Push-Location frontend
try {
    Run "Typage TypeScript" { npx tsc -b }
    Run "Tests unitaires frontend (vitest)" { npx vitest run }
    Run "Vulnérabilités npm connues (npm audit)" { npm audit --omit=dev }
    Run "Compilation" { npx vite build }
    if (-not $SkipE2E) { Run "Tests E2E navigateur (Playwright + Edge)" { npx playwright test --project=desktop --project=mobile } }
} finally { Pop-Location }
Write-Host "`nToutes les vérifications sont passées." -ForegroundColor Green
