/**
 * Static edition (SPEC §14 phase 10): the app built with VITE_STATIC_URL and the files of api/static_export.py,
 * with no API running. Skipped unless E2E_STATIC=1:
 *   python -m api.static_export --sites demo,manpura --out data/static
 *   cd web && VITE_STATIC_URL=/static npx vite build --outDir dist-static && cp -r ../data/static dist-static/static
 *   npx vite preview --outDir dist-static --port 4174
 *   E2E_STATIC=1 E2E_BASE_URL=http://localhost:4174 npx playwright test static
 */
import { expect, test } from "@playwright/test";

test.skip(!process.env.E2E_STATIC, "set E2E_STATIC=1 against a static build");

test("static edition: map, point card from the grid, compare, area needs the server", async ({ page }) => {
  const api: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/v1/")) api.push(r.url());
  });
  await page.goto("/?site=demo&lat=22.65&lon=90.663&z=14");
  await expect(page.getByTestId("static-banner")).toBeVisible();
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  await expect(page.getByLabel("Radar image (HH)", { exact: true })).toHaveCount(0); // not pre-rendered

  const canvas = page.locator('[data-testid="map"] canvas.maplibregl-canvas');
  const box = (await canvas.boundingBox())!;
  await page.waitForTimeout(800);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(page.getByTestId("point-score")).toHaveText(/^\d{1,3}$/);
  await expect(page.getByTestId("point-grid-note")).toContainText("100 m");
  await page.screenshot({ path: "test-results/phase10-static-point.png" });
  await page.keyboard.press("Escape");

  await page.getByTestId("tool-compare").click();
  await expect(page.locator('[data-testid="compare-right"] canvas.maplibregl-canvas')).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/phase10-static-compare.png" });
  await page.getByTestId("compare-exit").click();

  await page.getByTestId("tool-draw").click();
  await expect(page.getByTestId("draw-hint")).toBeVisible();
  const { x, y } = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.click(x - 100, y - 100);
  await page.mouse.click(x + 100, y - 100);
  await page.mouse.click(x + 100, y + 100);
  await page.mouse.dblclick(x - 100, y + 100);
  await expect(page.getByTestId("polygon-panel")).toContainText("need the live server");
  await expect(page.getByText("The NISAR scene search needs the live server.")).toBeVisible();

  await page.goto("/method?site=manpura&lang=en");
  await expect(page.getByTestId("validation-s2")).toContainText("Sentinel-2");
  expect(api).toEqual([]); // nothing asked of an API
});

test("static edition: real Manpura point matches the precomputed grid", async ({ page }) => {
  await page.goto("/?site=manpura&lat=22.378&lon=91.0195&z=13&pt=91.0195,22.378");
  await expect(page.getByTestId("point-score")).toHaveText(/^\d{1,3}$/);
  await expect(page.getByText("Not measured at this site")).toBeVisible();
  await page.screenshot({ path: "test-results/phase10-static-manpura.png" });
});
