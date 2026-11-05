# Installation locale sous Windows (PowerShell 5.1 ou 7).
# Usage : powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Require($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd introuvable. $hint" }
}

Require python "Installez Python 3.12+ depuis https://www.python.org (cochez 'Add python.exe to PATH')."
Require npm "Installez Node.js 20.19+ (LTS) depuis https://nodejs.org."

Step "Environnement Python (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { python -m venv .venv }
& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .venv\Scripts\python.exe -m pip install -r requirements-dev.txt --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install a échoué" }

Step "Catalogues de démonstration fictifs"
& .venv\Scripts\python.exe demo\generate_catalogs.py

Step "Dépendances et compilation de l'interface"
Push-Location frontend
npm ci --no-fund --no-audit
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm ci a échoué" }
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "La compilation du frontend a échoué" }
Pop-Location

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) { Copy-Item .env.example .env }

Write-Host "`nInstallation terminée. Lancez : powershell -ExecutionPolicy Bypass -File scripts\start.ps1" -ForegroundColor Green
