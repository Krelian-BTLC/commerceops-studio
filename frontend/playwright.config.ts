import { defineConfig, devices } from "@playwright/test";

const windows = process.platform === "win32";
// Python de l'environnement virtuel, relatif à la racine du projet (surcharger avec PYTHON=... si besoin).
const python = process.env.PYTHON ?? (windows ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");
// Sous Windows, Microsoft Edge est déjà installé : aucun navigateur à télécharger.
// En CI : `npx playwright install chromium` puis PW_CHANNEL vide.
const channel = process.env.PW_CHANNEL ?? (windows ? "msedge" : undefined);
const PORT = 8001;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel,
    locale: "fr-FR",
    trace: "retain-on-failure",
    acceptDownloads: true,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel, viewport: { width: 1366, height: 900 } }, testIgnore: /screenshots|responsive/ },
    { name: "mobile", use: { ...devices["Pixel 7"], channel }, testMatch: /responsive/ },
    { name: "screenshots", use: { channel, viewport: { width: 1440, height: 900 } }, testMatch: /screenshots/ },
  ],
  // L'API sert l'interface compilée (npm run build) : on teste l'application telle qu'elle est livrée.
  webServer: {
    command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT}`,
    cwd: "..",
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { COMMERCEOPS_DB: "data/e2e.db", COMMERCEOPS_LOG_LEVEL: "WARNING" },
  },
});
