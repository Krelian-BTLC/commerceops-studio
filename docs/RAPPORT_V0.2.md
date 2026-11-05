# Rapport de livraison — CommerceOps Studio v0.2

Date : 5 novembre 2026. Environnement : Windows 11 Pro, Python 3.14.7 (CI : 3.12), Node.js 24.20, Microsoft Edge.

## 1. Audit de la v0.1 (point de départ)

Les 6 tests fournis passaient. Constats, tous vérifiés par exécution :

| # | Constat | Gravité | Traitement en v0.2 |
|---|---|---|---|
| 1 | `29,95` (format français standard) signalé « prix invalide » : faux positif sur tout export Excel FR | haute | prix normalisés à l'import, avec avertissement |
| 2 | URL `javascript:alert(1)` ou chemin relatif acceptés sans signalement | moyenne | règles « URL d'image invalide » et « image en HTTP » |
| 3 | Statut `Active` rejeté pour une simple casse | basse | normalisé, avec avertissement |
| 4 | Chaque import écrasait le précédent : pas d'historique ni de comparaison possible | haute | historique SQLite et comparaison |
| 5 | Le rejet s'arrêtait à la première erreur | moyenne | toutes les erreurs collectées (ligne et colonne, 50 au maximum) |
| 6 | Messages d'anomalie sans explication ni correction ; heuristiques non signalées | moyenne | explication, suggestion, preuve, nature |
| 7 | Catalogue « après » à 0 anomalie : démonstration peu crédible | basse | jeu réaliste avec anomalies résolues, persistantes et nouvelles |
| 8 | Dépendances non figées, pas de lint, CI limitée à pytest, conteneur exécuté en root | moyenne | versions figées, Ruff, pip-audit, CI en 3 jobs, utilisateur non privilégié |
| 9 | Ni CORS, ni en-têtes de sécurité, ni journalisation | moyenne | ajoutés et testés |

Aucune fonctionnalité de la v0.1 n'a été retirée : les routes `/health` et `/catalog/*` répondent toujours (marquées dépréciées), et les 6 tests d'origine passent sans modification.

## 2. Fonctionnalités terminées

**Backend**
- [x] Validation stricte des fichiers : taille, lignes, longueur des champs, encodage, octets nuls, extension, type MIME, en-têtes, identifiants, statuts
- [x] Normalisation : séparateur, en-têtes, espaces, statut, prix (formats FR et EN, symbole €, espaces insécables)
- [x] 19 règles extensibles, dont 9 heuristiques, avec explication, priorité et correction
- [x] Indice par fiche, explicable (détail des pénalités)
- [x] Historique des audits et résultats conservés (avec version des règles et empreinte SHA-256)
- [x] Comparaison avant / après (résolues, nouvelles, persistantes, par règle et par priorité)
- [x] Exports : CSV des anomalies (filtres respectés, anti-injection, `;` ou `,`), CSV des produits, rapport PDF
- [x] Format d'erreur homogène, documentation OpenAPI typée (`/docs`)
- [x] Sécurité : CORS sur liste blanche, CSP et en-têtes de sécurité, journalisation sans contenu
- [x] Mode démonstration (`POST /api/demo`), désactivable

**Frontend**
- [x] Tableau de bord, Anomalies, Produits, Avant / après, Historique, Importer, Règles, page 404
- [x] Filtres, recherche (avec temporisation), tri, pagination, conservés dans l'URL
- [x] Fiche produit (dialogue), confirmation de suppression
- [x] États de chargement, d'erreur (API injoignable, rejet), vides
- [x] Responsive (vérifié à 412 px de large), modes clair et sombre, navigation au clavier, mouvements réduits respectés

**Livraison**
- [x] Scripts Windows `setup.ps1`, `start.ps1`, `check.ps1`
- [x] Dockerfile multi-étapes et `compose.yaml` (**non exécutés** : Docker absent du poste)
- [x] CI GitHub Actions (backend, frontend, E2E) — **non exécutée** : aucun dépôt distant n'existe
- [x] README (FR + résumé EN), guide Windows, architecture, démo, étude de cas, changelog, captures

## 3. Tests exécutés

Toutes les commandes ci-dessous ont été exécutées sur ce poste par `scripts\check.ps1` (PowerShell 5.1), le 5 novembre 2026 :

| Suite | Commande | Résultat |
|---|---|---|
| Lint Python | `ruff check .` | 0 erreur |
| Backend | `pytest -q` | **97 réussis**, 0 échec |
| Dépendances Python | `pip-audit -r requirements.txt` | aucune vulnérabilité connue |
| Typage | `tsc -b` (strict, `noUncheckedIndexedAccess`) | 0 erreur |
| Frontend unitaires | `vitest run` | **19 réussis** |
| Dépendances npm | `npm audit` | 0 vulnérabilité |
| Build | `vite build` | OK (JS 96 Ko gzip) |
| E2E | `playwright test --project=desktop --project=mobile` (Edge) | **10 réussis** |

Répartition des tests backend : 35 pour l'import et la normalisation, 36 pour les règles (un cas positif et un cas négatif par règle), 20 pour l'API v2 (historique, filtres, exports, comparaison, sécurité, CORS, journaux, démo), 6 tests v0.1 d'origine.

Parcours E2E : premier lancement et démo ; tableau de bord et fiche produit ; anomalies (filtres, pagination, recherche, tri, export CSV vérifié ligne par ligne) ; produits ; import (refus client, rejet serveur ligne par ligne, succès) ; historique (PDF et suppression confirmée) ; règles et 404 ; API indisponible ; accessibilité en mode sombre ; mobile sans défilement horizontal sur les 7 pages.

### Défauts trouvés et corrigés pendant la validation

| Défaut | Détecté par | Correction |
|---|---|---|
| Prix déjà valides (`103.90`) comptés comme « convertis » | vérification des données de démo | conservation des chiffres saisis |
| 13 titres dupliqués involontaires dans la démo | vérification des données de démo | combinaisons uniques |
| Espaces parasites avant `.` et `,` | revue visuelle | chiffres tabulaires limités aux colonnes de nombres |
| Deux `<h1>` sur la page de comparaison | Playwright | titre secondaire en `<h2>` |
| Contraste insuffisant du texte tertiaire (WCAG AA) | axe-core | couleur `#5b6575` |
| Le filtre « sans anomalie » incluait les brouillons non audités | Playwright | correction dans l'API + test de non-régression |
| Moyenne « 95/100 Très bon » contredisant 35 % de fiches défectueuses | revue visuelle | barème 50/20/5, indicateur « fiches sans anomalie » |
| Navigation masquée par le sélecteur d'audit | revue visuelle | barre de contexte séparée |
| Animation du panneau produit malgré `prefers-reduced-motion` | revue visuelle | animation désactivée |
| Accents illisibles dans les scripts sous PowerShell 5.1 | exécution de `check.ps1` | fichiers `.ps1` en UTF-8 avec BOM |

## 4. Outils demandés : disponibilité réelle

| Outil | Statut | Utilisation |
|---|---|---|
| Superpowers | disponible, **non invoqué** | ses skills (brainstorming, plans) imposent une validation interactive à chaque étape, contraire à l'autonomie demandée. Leurs principes ont été suivis : défaillances diagnostiquées par mesure plutôt que par supposition, et aucune affirmation de réussite sans exécution |
| Frontend Design | disponible, **utilisé** | direction visuelle, jetons, revue de la proposition contre les poncifs, autocritique sur captures |
| Playwright MCP | **inutilisable** sur ce poste : configuré pour Google Chrome, non installé | remplacé par `@playwright/test` avec Microsoft Edge (suite reproductible, versionnée et rejouée en CI) |
| Context7 | **non disponible** (authentification requise) | versions vérifiées sur le registre npm, API connues ; aucune documentation consultée via Context7 |
| Security Guidance | aucun outil de ce nom accessible | revue de sécurité manuelle, règles Ruff `S` (bandit), pip-audit, npm audit, tests dédiés |
| GitHub MCP | **non disponible** (authentification requise) ; pas de dépôt distant | dépôt Git **local** initialisé, 4 commits ; aucune publication |

## 5. Limitations

- Pas d'authentification ni d'isolation entre utilisateurs : usage local uniquement.
- Docker et la CI GitHub sont fournis mais **n'ont pas été exécutés** (Docker absent, pas de dépôt distant).
- Validé sous Windows 11 avec Python 3.14 ; la CI cible Python 3.12 sous Linux, non exécutée.
- Schéma CSV fixe à 8 colonnes, sans variantes.
- Heuristiques sujettes à faux positifs (affiché dans l'interface).
- PDF limité au jeu de caractères Latin-1 (translittération du reste).
- La limite de 10 000 produits est appliquée et testée avec une limite réduite ; aucun test de charge ni de performance n'a été mené à 10 000 lignes.
- Les captures d'écran de `docs/screenshots` proviennent des données fictives.

## 6. Décisions qui vous reviennent

1. **Licence** du dépôt public (MIT recommandée pour un portfolio ; non ajoutée sans votre accord).
2. **Création du dépôt GitHub** et premier push (publication publique : votre validation est requise).
3. Hébergement éventuel d'une démo en ligne : nécessiterait authentification ou mode démo isolé en lecture seule.
