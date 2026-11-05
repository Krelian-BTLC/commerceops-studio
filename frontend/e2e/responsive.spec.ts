import { expect, test } from "@playwright/test";
import { expectNoHorizontalScroll, loadDemo, resetAudits } from "./helpers";

test("mobile : toutes les pages tiennent dans la largeur de l'écran", async ({ page, request }) => {
  await resetAudits(request);
  const demo = await loadDemo(request);
  for (const path of [
    `/?audit=${demo.before.id}`,
    `/issues?audit=${demo.before.id}`,
    `/products?audit=${demo.before.id}`,
    `/compare?base=${demo.before.id}&target=${demo.after.id}`,
    "/history",
    "/import",
    "/rules",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalScroll(page);
  }
  // La fiche produit occupe l'écran et reste fermable au doigt.
  await page.goto(`/?audit=${demo.before.id}`);
  await page.getByRole("region", { name: "À corriger en premier" }).getByRole("button").first().click();
  await page.getByRole("button", { name: "Fermer la fiche produit" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
});
