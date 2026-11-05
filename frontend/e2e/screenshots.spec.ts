import { test } from "@playwright/test";
import { loadDemo, resetAudits } from "./helpers";

// Captures de la documentation : `npx playwright test --project=screenshots`.
const OUT = "../docs/screenshots";

for (const scheme of ["light", "dark"] as const) {
  test(`captures ${scheme}`, async ({ page, request }) => {
    await resetAudits(request);
    const demo = await loadDemo(request);
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    const shots: [string, string][] = [
      ["dashboard", `/?audit=${demo.before.id}`],
      ["issues", `/issues?audit=${demo.before.id}&severity=high`],
      ["compare", `/compare?base=${demo.before.id}&target=${demo.after.id}`],
      ["import", "/import"],
      ["products", `/products?audit=${demo.before.id}`],
      ["rules", "/rules"],
    ];
    for (const [name, path] of shots) {
      await page.goto(path);
      await page.getByRole("heading", { level: 1 }).waitFor();
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: `${OUT}/${name}-${scheme}.png`, fullPage: name !== "products" && name !== "rules" });
    }
    await page.goto(`/?audit=${demo.before.id}`);
    await page.getByRole("region", { name: "À corriger en premier" }).getByRole("button").first().click();
    await page.getByRole("dialog").getByText("Correction suggérée").first().waitFor();
    await page.screenshot({ path: `${OUT}/product-${scheme}.png` });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/?audit=${demo.before.id}`);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.screenshot({ path: `${OUT}/mobile-${scheme}.png` });
  });
}
