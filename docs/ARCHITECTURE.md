# Architecture — CommerceOps Studio v0.2

## Vue d'ensemble

```
┌──────────────────────── Navigateur ────────────────────────┐
│ React 19 + TypeScript (frontend/src)                        │
│  pages/      Dashboard, Issues, Products, Compare, History,  │
│              Import, Rules                                   │
│  lib/api.ts  client typé, erreurs {detail, code, errors}     │
│  état des filtres dans l'URL (?audit=&severity=&page=...)    │
└──────────────┬──────────────────────────────────────────────┘
               │ fetch /api/*  (même origine en production)
┌──────────────▼──────────────── FastAPI (app/) ──────────────┐
│ main.py      routes, middleware (en-têtes, journal),         │
│              gestion d'erreurs homogène, service de la SPA   │
│ importer.py  décodage, structure, validation, normalisation  │
│ rules.py     registre de règles, contexte catalogue, indice  │
│ storage.py   SQLite : audits, produits, anomalies, requêtes  │
│ exports.py   CSV (anti-injection), PDF (fpdf2)               │
│ schemas.py   modèles Pydantic publiés dans OpenAPI           │
└──────────────┬──────────────────────────────────────────────┘
               ▼
          SQLite (fichier local, COMMERCEOPS_DB)
```

En production locale, un seul processus `uvicorn` sert l'API et l'interface compilée sur `127.0.0.1:8000`. Il n'y a donc pas d'appel cross-origin. En développement, Vite relaie `/api` vers FastAPI.

## Flux d'un import

1. `POST /api/audits` (multipart) : contrôle du `Content-Length`, de l'extension, du type MIME, puis lecture plafonnée à `max_file_bytes + 1` octets.
2. `importer.parse_catalog` :
   - rejette : fichier vide, non UTF-8, octets nuls, en-têtes manquants ou répétés, trop de lignes, nombre de champs incorrect, champ trop long, `product_id` vide ou dupliqué, statut inconnu. **Toutes** les erreurs de lignes sont collectées (jusqu'à 50), avec leur numéro de ligne et leur colonne ;
   - normalise, avec avertissement : séparateur `;`, en-têtes en majuscules, espaces multiples, statut en majuscules, prix `1 234,50 €` → `1234.50`, colonnes inconnues ignorées, lignes vides.
   - Les **valeurs manquantes ne sont pas rejetées** : ce sont les anomalies que l'audit doit montrer (décision du Lot 0).
3. `rules.run_rules` : construit un `Context` sur les produits actifs (comptage des SKU, descriptions et titres, prix médian), puis applique chaque règle.
4. `storage.create_audit` : une transaction insère l'audit, ses produits (avec indice et priorité maximale) et ses anomalies. Un rejet à l'étape 2 n'écrit rien.

## Modèle de données (SQLite)

```
audits (id PK, label, source_filename, source_sha256, created_at, rules_version,
        total_products, active_products, affected_products, issue_count,
        high_count, medium_count, low_count, quality_score, warnings_json)
   │1
   ├──< audit_products (audit_id FK ON DELETE CASCADE, product_id, sku, title_fr,
   │                    description_fr, price_eur, image_url, title_en, status,
   │                    score, issue_count, worst_severity)   PK(audit_id, product_id)
   └──< audit_issues   (id PK, audit_id FK ON DELETE CASCADE, product_id, sku, title_fr,
                        code, severity, severity_rank, category, field, message,
                        explanation, suggestion, confidence, evidence)
        index (audit_id, severity_rank, code), (audit_id, product_id)
```

**Pourquoi stocker les résultats plutôt que les recalculer ?** Un audit est un constat daté. Si les règles évoluent (`rules_version`), les audits passés ne doivent pas changer silencieusement ; la comparaison signale d'ailleurs un écart de version. Les agrégats (`high_count`…) sont dénormalisés dans `audits` pour que l'historique s'affiche sans jointure.

## Moteur de règles

```python
@rule("missing_image", severity="medium", category="media", field="image_url",
      title="Image produit manquante",
      explanation="Une fiche sans visuel convertit nettement moins…",
      suggestion="Ajouter au moins une photo du produit (URL HTTPS).")
def _missing_image(p, ctx):
    return "Champ image_url vide" if not p["image_url"] else None
```

- Une règle renvoie une **preuve** (texte court affiché à l'utilisateur) ou `None`.
- `confidence="heuristic"` signale un indice probable et non une certitude ; l'interface l'affiche comme « À vérifier ».
- Ajouter une règle : une fonction, un test positif et un test négatif (`tests/test_rules.py`), et un changement de `RULES_VERSION`. L'API (`/api/rules`), les filtres, l'interface et le PDF la prennent en compte sans autre modification.

| Famille | Règles (★ = heuristique) |
|---|---|
| Identification | SKU manquant, SKU dupliqué |
| Prix | prix invalide ou ≤ 0, ★ prix atypique (≥ 10× ou ≤ 1/10 de la médiane, à partir de 8 prix) |
| Contenu | titre manquant, ★ titre très court, ★ très long, ★ dupliqué ; description manquante, ★ courte, ★ dupliquée, ★ texte provisoire, ★ HTML brut, description = titre |
| Médias | image manquante, URL invalide (schéma, hôte, espaces), image en HTTP |
| Traduction | titre anglais manquant, ★ identique au français |

### Indice qualité

Indice par fiche active = `100 − 50 × hautes − 20 × moyennes − 5 × basses`, borné à 0. Une seule anomalie haute fait donc tomber la fiche à 50 (« Fragile »).

Le tableau de bord met en avant **la part des fiches sans anomalie** plutôt que la moyenne des indices. La moyenne est mécaniquement tirée vers le haut par les fiches saines : 92,4 pour la démo, alors qu'une fiche sur trois présente un problème. Ce constat, fait pendant la revue visuelle de la v0.2, a conduit à changer le barème (`2026.11-1` → `2026.11-2`) et l'indicateur principal.

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | état, version, version des règles |
| GET | `/api/rules` | catalogue des règles et barème |
| POST | `/api/audits` | import CSV et création d'un audit (`file`, `label`) |
| GET | `/api/audits` | historique |
| GET | `/api/audits/{id}` | synthèse et répartitions, produits prioritaires |
| DELETE | `/api/audits/{id}` | suppression (en cascade) |
| GET | `/api/audits/{id}/products` | `q`, `status`, `severity`, `has_issues`, `sort`, `page`, `page_size` |
| GET | `/api/audits/{id}/products/{product_id}` | fiche, anomalies, détail des pénalités |
| GET | `/api/audits/{id}/issues` | `severity`, `code`, `category`, `confidence`, `q`, `sort`, pagination |
| GET | `/api/audits/{id}/exports/issues.csv` | mêmes filtres + `delimiter=semicolon\|comma` |
| GET | `/api/audits/{id}/exports/products.csv` | produits et indices |
| GET | `/api/audits/{id}/exports/report.pdf` | rapport PDF |
| GET | `/api/compare?base=&target=` | avant / après |
| POST | `/api/demo` | importe les deux catalogues fictifs |
| — | `/health`, `/catalog/import`, `/catalog/summary`, `/catalog/issues` | routes v0.1 conservées (dépréciées), sur le dernier audit |

Format d'erreur unique : `{"detail": "message lisible", "code": "invalid_catalog", "errors": [{"line": 3, "column": "product_id", "message": "…"}]}`. Le champ `detail` est conservé pour rester compatible avec la v0.1.

## Frontend

- **Pas de gestionnaire d'état global** : un contexte (`AuditsProvider`) pour la liste des audits et le catalogue de règles, et l'URL pour tout le reste (audit affiché, filtres, tri, page). Les vues sont partageables et le bouton Précédent fonctionne.
- `useAsync` ignore les réponses arrivées après un changement de paramètres, pour éviter d'afficher des résultats obsolètes.
- Graphiques en HTML/CSS (barres, barre empilée) avec des libellés accessibles : pas de dépendance de graphiques, rendu net en mode clair et sombre.
- `<dialog>` natif pour la fiche produit et la confirmation de suppression : focus piégé, Échap et retour du focus gérés par le navigateur.
- Design system : jetons dans `styles/tokens.css` (couleurs, typographie Schibsted Grotesk auto-hébergée, espacements, rayons), mode sombre via `prefers-color-scheme`. Contrastes vérifiés par axe-core.

## Choix techniques et alternatives écartées

| Choix | Raison | Alternative écartée |
|---|---|---|
| SQLite | zéro installation sous Windows, transactions, suffisant pour 10 000 produits par audit | PostgreSQL : utile en multi-utilisateur, superflu pour un outil local |
| SQL paramétré « à la main » | 3 tables, requêtes lisibles et auditables | ORM : complexité non justifiée à cette taille |
| fpdf2 (LGPL) | pur Python, aucun binaire système requis sous Windows | WeasyPrint (dépend de GTK sous Windows), ReportLab (plus lourd) |
| Un seul processus servant l'API et la SPA | un seul port, pas de CORS en production, démonstration simple | Nginx séparé : utile en hébergement, pas en local |
| Vite + React Router | standard, rapide, bien documenté | Next.js : rendu serveur inutile pour un outil local |
| CSS sur mesure avec jetons | identité visuelle propre, aucune dépendance | Tailwind ou bibliothèque de composants : apparence générique |
| Microsoft Edge pour les E2E sous Windows | déjà installé, aucun téléchargement | Chromium de Playwright : utilisé en CI Linux |

## Sécurité (résumé)

Voir la section dédiée du [README](../README.md#sécurité-et-données). Points de conception :
- **Surface réseau** : `127.0.0.1` par défaut ; `compose.yaml` publie le port uniquement sur l'interface locale ; le conteneur tourne sans privilèges avec un système de fichiers en lecture seule.
- **Pas de requêtes sortantes** : l'application n'appelle aucune URL, ce qui écarte les risques de SSRF et de fuite de données. La CSP interdit aussi au navigateur de charger les images du catalogue.
- **Exports** : neutralisation des formules et BOM UTF-8 pour Excel ; noms de fichiers d'import assainis.
- **Journalisation** : méthode, chemin, statut, durée, identifiant de requête et empreinte SHA-256 tronquée ; jamais le contenu.
