import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

/** Repart d'une base vide : supprime tous les audits via l'API. */
export async function resetAudits(request: APIRequestContext) {
  const audits = (await (await request.get("/api/audits")).json()) as { id: number }[];
  for (const a of audits) expect((await request.delete(`/api/audits/${a.id}`)).status()).toBe(204);
}

export async function loadDemo(request: APIRequestContext) {
  const response = await request.post("/api/demo");
  expect(response.status()).toBe(201);
  return (await response.json()) as { before: { id: number }; after: { id: number } };
}

export async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
  expect(summary, "violations d'accessibilité WCAG A/AA").toEqual([]);
}

export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "défilement horizontal de la page").toBeLessThanOrEqual(0);
}

export const HEADER = "product_id,sku,title_fr,description_fr,price_eur,image_url,title_en,status\n";
