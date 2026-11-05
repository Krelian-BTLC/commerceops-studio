# Scénario de démonstration (5 minutes)

Données : boutique **imaginaire** « Maison Ardoise », 150 produits générés de façon déterministe par `demo/generate_catalogs.py`. Aucune donnée réelle.

## Préparation

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Pour partir d'un état vierge, arrêtez le serveur et supprimez `data\catalog.db` (cela efface l'historique local).

## Déroulé

| # | Action | Ce qu'on montre | Résultat attendu |
|---|---|---|---|
| 1 | Ouvrir http://127.0.0.1:8000 | état vide qui invite à agir | « Aucun audit pour l'instant » |
| 2 | **Importer → Charger la démonstration** | deux imports, puis ouverture de la comparaison | « 84 % d'anomalies en moins entre les deux audits. » |
| 3 | Onglets Résolues / Nouvelles / Toujours présentes | suivi par produit et par règle | 49 / 3 / 6 |
| 4 | Sélecteur « Audit affiché » → *Démo — catalogue initial*, puis **Tableau de bord** | constat en une phrase, étiquette « Fiches sans anomalie » | 51 produits actifs sur 144 concernés, 65 %, « Fragile » |
| 5 | Encadré « Ajustements faits à l'import » | la normalisation est transparente | 144 prix « 34,90 » convertis |
| 6 | Cliquer le premier produit de « À corriger en premier » | fiche expliquée, calcul de l'indice | `100 − 50 − 5 = 45`, SKU partagé par 4 produits |
| 7 | **Anomalies** → Priorité : Haute | filtre conservé dans l'URL | 11 anomalies |
| 8 | Rechercher `MA-0041` | règle heuristique « À vérifier » | 10 590 € pour un prix médian de 47,95 € |
| 9 | Famille : Médias → **Exporter la sélection en CSV** | l'export respecte les filtres | 13 lignes |
| 10 | **Historique → PDF** | rapport à transmettre | PDF de synthèse, puis détail |
| 11 | **Importer** un CSV avec un `product_id` en double | rejet explicite, rien n'est modifié | « Ligne 3 (colonne product_id) : … dupliqué » |
| 12 | **Règles** | transparence de la méthode | 19 règles, barème 50 / 20 / 5 |

## Pièges volontaires du catalogue initial

| Anomalie | Produits |
|---|---|
| SKU recopié | MA-0018, 0019, 0038, 0057 |
| SKU vide | MA-0044, 0088 |
| Prix à 0 | MA-0029, 0058, 0087, 0116 |
| Prix ×100 (virgule oubliée) | MA-0041 |
| Description générique répétée | un produit sur 23 (MA-0023, 0046…) |
| Lorem ipsum, « À compléter » | MA-0066, 0120 |
| Balises HTML | MA-0075 |
| URL d'image relative, en HTTP | MA-0052 ; MA-0097, 0133 |
| Titre anglais = titre français | MA-0061, 0102 |
| Titre français vide | MA-0140 |
| Brouillons (non audités) | MA-0145 à 0150 |

Le catalogue « après » corrige tout sauf quatre traductions et une photo, et ajoute deux produits, dont un incomplet (MA-0152). La comparaison montre ainsi les trois cas : anomalies résolues, persistantes et nouvelles.

## Reproductibilité

`tests/test_api_v2.py::test_demo_scenario_is_reproducible` vérifie 150/152 produits, 55 → 9 anomalies, 11 → 0 hautes et la présence de nouvelles anomalies. Les parcours 1 à 12 sont automatisés dans `frontend/e2e/journey.spec.ts`.
