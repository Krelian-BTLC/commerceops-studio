# Journal des modifications

## [0.2.0] — 2026-11-05

### Ajouté
- Interface React + TypeScript : tableau de bord, anomalies, produits, avant / après, historique, import, règles.
- Historique des audits (SQLite) et comparaison avant / après.
- 11 nouvelles règles (19 au total) : prix atypique, titre court, long ou dupliqué, description courte, texte provisoire, HTML brut, description identique au titre, URL d'image invalide, image en HTTP, titre anglais non traduit.
- Explication, correction suggérée, preuve et nature (constat ou heuristique) pour chaque anomalie ; indice par fiche.
- Exports CSV (anomalies filtrées, produits) protégés contre l'injection de formules ; rapport PDF.
- API `/api/*` documentée et typée (OpenAPI), format d'erreur homogène.
- CORS sur liste blanche, CSP et en-têtes de sécurité, journalisation sans contenu.
- Mode démonstration et catalogues fictifs réalistes (Maison Ardoise).
- Scripts Windows `setup.ps1`, `start.ps1`, `check.ps1` ; Dockerfile multi-étapes ; CI en 3 jobs.
- Tests : 97 backend, 19 frontend, 10 E2E Playwright avec axe-core.

### Modifié
- Import : séparateur `;`, prix `29,95`, statut et en-têtes insensibles à la casse ; toutes les erreurs de lignes sont rapportées.
- Un import crée un audit au lieu de remplacer le catalogue.
- Dépendances figées ; dépendances de développement séparées (`requirements-dev.txt`).

### Corrigé
- Faux positif « prix invalide » sur les prix au format français.

### Compatibilité
- Routes v0.1 (`/health`, `/catalog/import`, `/catalog/summary`, `/catalog/issues`) conservées et marquées dépréciées ; elles portent sur le dernier audit.

## [0.1.0] — 2026-11-05
- Starter : import CSV, 8 règles, résumé, API FastAPI, 6 tests.
