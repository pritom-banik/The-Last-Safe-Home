import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * e2e runs against the demo site. Unless E2E_BASE_URL points at a running app, Playwright starts:
 *   - the API (uvicorn, port 8000) from the repo root, reading data/processed/demo (`make demo` first)
 *   - the built web app (vite preview, port 4173)
 * PYTHON picks the interpreter (default: the repo .venv if present, else `python` from the active conda env).
 * Docker compose replaces this in phase 9 (docs/DECISIONS.md).
 */
const repoRoot = fileURLToPath(new URL("..", import.meta.url));
const venvPython = join(repoRoot, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
const external = !!process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  timeout: 45_000,
  // the real ASF scene search and OSM tiles are network calls: one retry in CI
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:4173", viewport: { width: 1280, height: 720 } },
  webServer: external
    ? undefined
    : [
        {
          command: `"${python}" -m uvicorn api.app.main:app --port 8000`,
          cwd: repoRoot,
          url: "http://localhost:8000/api/v1/health",
          env: { CORS_ORIGINS: "http://localhost:4173,http://localhost:5173", SITES: "demo" },
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
        {
          command: "npm run build && npm run preview -- --port 4173 --strictPort",
          port: 4173,
          reuseExistingServer: !process.env.CI,
          timeout: 180_000,
        },
      ],
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
