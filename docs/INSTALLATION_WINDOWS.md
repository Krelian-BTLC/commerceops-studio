# Installation sous Windows 10 / 11

Procédure testée le 5 novembre 2026 sur Windows 11 Pro, Python 3.14.7, Node.js 24.20, npm 11.19, PowerShell 5.1.

## 1. Prérequis

| Outil | Version | Vérifier |
|---|---|---|
| Python | 3.12 ou plus récent | `python --version` |
| Node.js (avec npm) | 20.19+ ou 22.12+ (LTS recommandée) | `node --version` |
| Microsoft Edge | préinstallé sur Windows ; sert aux tests E2E | — |

- Python : https://www.python.org/downloads/ ; cochez **« Add python.exe to PATH »** à l'installation.
- Node.js : https://nodejs.org/ (version LTS).

Aucun compte, aucune clé d'API, aucun service payant n'est nécessaire.

## 2. Installation (une seule fois)

Ouvrez PowerShell dans le dossier du projet :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

Le script :
1. crée l'environnement virtuel `.venv` et installe les dépendances Python figées (`requirements-dev.txt`) ;
2. génère les catalogues fictifs `demo/catalog_before.csv` et `demo/catalog_after.csv` ;
3. installe les dépendances npm (`npm ci`, versions verrouillées) et compile l'interface dans `frontend/dist` ;
4. copie `.env.example` en `.env` s'il n'existe pas.

`-ExecutionPolicy Bypass` ne s'applique qu'à cette commande : la politique de sécurité de Windows n'est pas modifiée.

## 3. Lancement

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

- Interface : http://127.0.0.1:8000
- Documentation de l'API (OpenAPI / Swagger) : http://127.0.0.1:8000/docs
- Arrêt : `Ctrl+C`

Options : `-Port 8080` pour changer de port, `-NoBrowser` pour ne pas ouvrir le navigateur. Le serveur n'écoute que sur `127.0.0.1` : il n'est pas visible depuis le réseau local. La base SQLite est créée dans `data\catalog.db`.

## 4. Mode développement (rechargement à chaud)

Deux terminaux :

```powershell
# Terminal 1 : API
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

```powershell
# Terminal 2 : interface (http://localhost:5173, /api relayé vers le port 8000)
cd frontend
npm run dev
```

## 5. Vérifications

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1          # tout, E2E compris
powershell -ExecutionPolicy Bypass -File scripts\check.ps1 -SkipE2E # sans navigateur
```

Les tests E2E démarrent leur propre serveur sur le port 8001 avec une base séparée (`data\e2e.db`) et utilisent Microsoft Edge. Pour utiliser Chromium à la place : `npx playwright install chromium`, puis `$env:PW_CHANNEL=""` avant `npx playwright test`.

## 6. Configuration

Variables d'environnement (voir `.env.example`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `COMMERCEOPS_DB` | `./catalog.db` (`data\catalog.db` via `start.ps1`) | fichier SQLite |
| `COMMERCEOPS_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | origines autorisées en développement |
| `COMMERCEOPS_MAX_FILE_BYTES` | `2000000` | taille maximale d'un CSV |
| `COMMERCEOPS_MAX_ROWS` | `10000` | nombre maximal de produits |
| `COMMERCEOPS_DEMO_ENABLED` | `true` | active « Charger la démonstration » |
| `COMMERCEOPS_LOG_LEVEL` | `INFO` | niveau de journalisation |

Dans PowerShell : `$env:COMMERCEOPS_LOG_LEVEL = "DEBUG"` avant le lancement.

## 7. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `python introuvable` | Python absent du PATH | réinstaller en cochant « Add to PATH », ou utiliser `py -3.12` |
| « l'exécution de scripts est désactivée » | politique d'exécution | utiliser la commande complète `powershell -ExecutionPolicy Bypass -File ...` |
| Port 8000 déjà utilisé | autre application | `scripts\start.ps1 -Port 8080` |
| La page affiche « Le serveur ne répond pas » | API arrêtée en mode développement | relancer le terminal 1 |
| « Le CSV doit être encodé en UTF-8 » | export Excel par défaut (ANSI) | Excel : *Enregistrer sous* → **CSV UTF-8 (délimité par des virgules)** |
| Les tests E2E ne trouvent pas `msedge` | Edge absent | `npx playwright install chromium` puis `$env:PW_CHANNEL=""` |
| Réinitialiser les données | — | supprimer `data\catalog.db` (supprime tout l'historique local) |
