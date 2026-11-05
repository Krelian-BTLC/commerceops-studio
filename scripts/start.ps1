# Démarre CommerceOps Studio sur http://127.0.0.1:8000 (interface + API + /docs).
# Usage : powershell -ExecutionPolicy Bypass -File scripts\start.ps1 [-Port 8000] [-NoBrowser]
param([int]$Port = 8000, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Environnement absent : lancez d'abord scripts\setup.ps1" }
if (-not (Test-Path "frontend\dist\index.html")) { Write-Warning "Interface non compilée : seule l'API sera disponible (cd frontend; npm run build)." }
if (-not $env:COMMERCEOPS_DB) { $env:COMMERCEOPS_DB = "data\catalog.db" }

$url = "http://127.0.0.1:$Port/"
Write-Host "CommerceOps Studio : $url   (documentation API : ${url}docs)   Ctrl+C pour arrêter" -ForegroundColor Green
if (-not $NoBrowser) { Start-Job -ScriptBlock { param($u) Start-Sleep 2; Start-Process $u } -ArgumentList $url | Out-Null }
# 127.0.0.1 uniquement : l'application n'est pas exposée au réseau local.
& .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port
