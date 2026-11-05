# CommerceOps Studio — Incrément 1 : API d'audit de catalogue

Projet portfolio développé à partir d'un cas d'usage : identifier les erreurs de qualité d'un catalogue de boutique en ligne. **Statut : backend d'amorçage fonctionnel, pas encore un produit final.**

## Ce qui fonctionne dans cet incrément

- Import d'un catalogue CSV en UTF-8 avec contrôle des colonnes, de l'unicité des identifiants et des statuts.
- Détection de huit types d'anomalies (SKU manquant/dupliqué, prix invalide, titres ou descriptions manquants, descriptions dupliquées, image manquante, traduction manquante).
- Filtrage par gravité ou type et résumé des anomalies sur les produits **actifs**.
- Persistance SQLite ; import remplace atomiquement le catalogue précédent.
- Jeux de données **100 % fictifs** avant/après de 150 produits.
- Tests API automatisés et CI GitHub Actions.

## Installation Windows (PowerShell) / macOS / Linux

Prérequis : Python 3.12+.

```bash
python -m venv .venv
# Windows PowerShell :
.venv\Scripts\Activate.ps1
# macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
python demo/generate_catalogs.py
python -m pytest -q
uvicorn app.main:app --reload
```

Ouvre **http://127.0.0.1:8000/docs** : l'interface Swagger permet d'envoyer `demo/catalog_before.csv` via `POST /catalog/import`, puis d'inspecter `GET /catalog/summary` et `GET /catalog/issues`. Réimporte `demo/catalog_after.csv` pour constater la correction des anomalies.

Alternative Docker : `docker compose up --build` (l'API est exposée uniquement sur l'interface localhost).

## Routes

| Méthode | Route | Fonction |
|---|---|---|
| GET | `/health` | Vérification simple |
| POST | `/catalog/import` | Import CSV en remplacement du catalogue |
| GET | `/catalog/summary` | Indicateurs de qualité |
| GET | `/catalog/issues` | Liste et filtres `severity` / `code` |

## Limites connues et prochaines étapes

- Pas encore de frontend React, d'authentification, de multi-boutiques, de connecteur Shopify ni d'export.
- Les liens d'images sont des valeurs de démonstration ; l'API **ne télécharge pas** d'images et ne teste pas leur disponibilité.
- Le score métier et le suivi historique seront ajoutés seulement après validation des règles et du modèle de données.
- Le CSV d'entrée est plafonné à 2 Mo / 10 000 produits. L'API est prévue pour un environnement **local de développement**, pas pour une exposition publique sans contrôle d'accès, quotas, durcissement et revue de sécurité.
- Toutes les données de démonstration sont synthétiques ; aucune donnée client réelle n'a été intégrée.

## Prochaine étape

Construire le frontend React/TypeScript, puis un export CSV et un comparatif avant/après reproductible. Voir le cahier des charges global `PORTFOLIO_3_PROJETS_REFERENCE.md` fourni séparément.
