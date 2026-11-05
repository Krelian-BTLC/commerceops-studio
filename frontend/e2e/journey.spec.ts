import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { HEADER, expectNoA11yViolations, loadDemo, resetAudits } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetAudits(request);
});

test("premier lancement : invitation à importer, puis démo et comparaison avant / après", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Aucun audit pour l'instant" })).toBeVisible();
  await page.getByRole("link", { name: "Importer un catalogue" }).click();
  await page.getByRole("button", { name: "Charger la démonstration" }).click();

  await expect(page).toHaveURL(/\/compare\?base=\d+&target=\d+/);
  // 55 anomalies avant, 9 après : −84 % (chiffres mesurés, cf. tests backend).
  await expect(page.getByRole("heading", { level: 2, name: "84 % d'anomalies en moins entre les deux audits." })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Résolues \(\d+\)/ })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: /Nouvelles/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("MA-0152");
  await expectNoA11yViolations(page);
});

test("tableau de bord : constat, priorités et fiche produit expliquée", async ({ page, request }) => {
  const demo = await loadDemo(request);
  await page.goto(`/?audit=${demo.before.id}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("51 produits actifs sur 144 ont au moins une anomalie.");
  await expect(page.getByLabel("65 % des fiches actives sans anomalie")).toBeVisible();
  await expect(page.getByRole("note")).toContainText("144 prix convertis");

  // Fiche du produit le plus fragile, ouverte depuis « À corriger en premier ».
  const priority = page.getByRole("region", { name: "À corriger en premier" });
  await priority.getByRole("button").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText("Correction suggérée");
  await expect(drawer).toContainText(/100 − \d+/);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();

  // Un clic sur une règle ouvre la liste filtrée.
  await page.getByRole("link", { name: "SKU utilisé par plusieurs produits" }).click();
  await expect(page).toHaveURL(/code=duplicate_sku/);
  await expect(page.getByText("1–4 sur 4 anomalies")).toBeVisible();
  await expectNoA11yViolations(page);
});

test("anomalies : filtres, recherche, tri, pagination et export CSV cohérent", async ({ page, request }) => {
  const demo = await loadDemo(request);
  await page.goto(`/issues?audit=${demo.before.id}`);
  await expect(page.getByText("1–25 sur 55 anomalies")).toBeVisible();

  await page.getByRole("button", { name: "Suivant" }).click();
  await expect(page.getByText("26–50 sur 55 anomalies")).toBeVisible();

  await page.getByLabel("Priorité").selectOption("high");
  await expect(page.getByText("1–11 sur 11 anomalies")).toBeVisible();
  await expect(page).not.toHaveURL(/page=/); // un nouveau filtre revient en page 1

  await page.getByLabel("Nature").selectOption("heuristic");
  await expect(page.getByText("Aucune anomalie ne correspond à ces filtres")).toBeVisible();
  await page.getByRole("button", { name: "Effacer les filtres" }).click();

  await page.getByLabel("Rechercher un produit").fill("MA-0041");
  await expect(page.getByText("1–1 sur 1 anomalie")).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Prix atypique par rapport au catalogue");
  await expect(page.getByRole("table")).toContainText("À vérifier");

  await page.getByLabel("Rechercher un produit").fill("");
  await page.getByLabel("Famille").selectOption("media");
  await expect(page.getByText(/sur 13 anomalies/)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Exporter la sélection en CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`audit-${demo.before.id}-anomalies.csv`);
  const csv = (await readFile((await download.path())!)).toString("utf-8").replace(/^﻿/, "");
  const lines = csv.trim().split(/\r?\n/);
  expect(lines).toHaveLength(1 + 13);
  expect(lines.slice(1).every((l) => l.includes(";Médias;"))).toBe(true);

  // Tri par produit décroissant.
  await page.getByRole("button", { name: "Produit" }).click();
  await page.getByRole("button", { name: "Produit" }).click();
  await expect(page.getByRole("columnheader", { name: "Produit" })).toHaveAttribute("aria-sort", "descending");
});

test("produits : tri, filtres et brouillons non audités", async ({ page, request }) => {
  const demo = await loadDemo(request);
  await page.goto(`/products?audit=${demo.before.id}`);
  await expect(page.getByText("1–25 sur 150 produits")).toBeVisible();
  await page.getByLabel("Statut").selectOption("draft");
  await expect(page.getByText("1–6 sur 6 produits")).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Non audité");
  await page.getByLabel("Statut").selectOption("");
  await page.getByLabel("Anomalies").selectOption("false");
  await expect(page.getByText(/sur 93 produits/)).toBeVisible();
  await page.getByRole("button", { name: "Prix" }).click();
  await expect(page.getByRole("columnheader", { name: "Prix" })).toHaveAttribute("aria-sort", "ascending");
  await expectNoA11yViolations(page);
});

test("import : refus côté client, rejet serveur ligne par ligne, puis import réussi", async ({ page }) => {
  await page.goto("/import");
  const input = page.getByTestId("file-input");

  await input.setInputFiles({ name: "catalogue.xlsx", mimeType: "application/octet-stream", buffer: Buffer.from("x") });
  await expect(page.getByRole("alert")).toContainText("n'est pas un .csv");
  await expect(page.getByRole("button", { name: "Lancer l'audit" })).toBeDisabled();

  const invalid = HEADER + "p1,A,Vase en grès,Desc,10,,Vase,active\np1,B,Vase en grès,Desc,10,,Vase,active\np3,C,Vase,Desc,10,,Vase,archived\n";
  await input.setInputFiles({ name: "invalide.csv", mimeType: "text/csv", buffer: Buffer.from(invalid) });
  await page.getByRole("button", { name: "Lancer l'audit" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Le fichier a été rejeté, aucun audit créé");
  await expect(alert).toContainText("Ligne 3 (colonne product_id)");
  await expect(alert).toContainText("Ligne 4 (colonne status)");

  const valid = HEADER.replaceAll(",", ";") + "p1;A-1;Vase en grès sauge;Vase en grès émaillé pour bouquets et branches;34,90;;Sage vase;active\n";
  await input.setInputFiles({ name: "boutique.csv", mimeType: "text/csv", buffer: Buffer.from(valid) });
  await page.getByLabel("Nom de l'audit (facultatif)").fill("Boutique test");
  await page.getByRole("button", { name: "Lancer l'audit" }).click();
  const status = page.getByRole("status").filter({ hasText: "créé" });
  await expect(status).toContainText(/Audit #\d+ créé/);
  await expect(status).toContainText("1 produit importé, 1 anomalie détectée");
  await expect(status).toContainText("1 prix convertis");
  await status.getByRole("link", { name: "Voir le tableau de bord" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("1 produits actifs sur 1 ont au moins une anomalie.");
  await expect(page.getByLabel("Audit affiché")).toContainText("Boutique test");
});

test("historique : rapport PDF et suppression confirmée", async ({ page, request }) => {
  await loadDemo(request);
  await page.goto("/history");
  await expect(page.getByRole("row")).toHaveCount(3);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /Télécharger le rapport PDF de l'audit/ }).first().click();
  const pdf = await readFile((await (await downloadPromise).path())!);
  expect(pdf.subarray(0, 4).toString()).toBe("%PDF");

  await page.getByRole("button", { name: /Supprimer l'audit/ }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("irréversible");
  await dialog.getByRole("button", { name: "Annuler" }).click();
  await expect(page.getByRole("row")).toHaveCount(3);

  await page.getByRole("button", { name: /Supprimer l'audit/ }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Supprimer définitivement" }).click();
  await expect(page.getByText(/Audit #\d+ supprimé/)).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(2);
  await expectNoA11yViolations(page);
});

test("règles : catalogue documenté et page introuvable", async ({ page }) => {
  await page.goto("/rules");
  await expect(page.getByRole("heading", { name: "Règles d'audit" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Prix atypique par rapport au catalogue" })).toBeVisible();
  await expectNoA11yViolations(page);
  await page.goto("/nimporte-quoi");
  await expect(page.getByRole("heading", { name: "Cette page n'existe pas" })).toBeVisible();
});

test("API indisponible : message d'erreur exploitable", async ({ page }) => {
  await page.route("**/api/audits", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Le serveur ne répond pas");
  await expect(page.getByRole("button", { name: "Réessayer" })).toBeVisible();
});

test("mode sombre : contrastes conformes WCAG AA", async ({ page, request }) => {
  const demo = await loadDemo(request);
  await page.emulateMedia({ colorScheme: "dark" });
  for (const path of [`/?audit=${demo.before.id}`, `/issues?audit=${demo.before.id}`, `/compare?base=${demo.before.id}&target=${demo.after.id}`]) {
    await page.goto(path);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await expectNoA11yViolations(page);
  }
});
