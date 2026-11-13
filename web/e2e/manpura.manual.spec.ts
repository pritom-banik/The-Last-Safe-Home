/**
 * Manual check on the real Manpura site (SPEC §14 phase 7). Skipped unless E2E_MANPURA=1, because it needs the
 * processed Manpura data, an API started with SITES=manpura,... and network access (ASF scene search):
 *   SITES=manpura,demo uvicorn api.app.main:app --port 8000
 *   E2E_MANPURA=1 E2E_BASE_URL=http://localhost:4173 npx playwright test manpura
 * It also checks that the numbers on screen match the pipeline outputs.
 */
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

test.skip(!process.env.E2E_MANPURA, "set E2E_MANPURA=1 to run against real Manpura data");
test.setTimeout(120_000);

const PT = [91.0195, 22.378]; // a high-score point on the north-east shore
// read only when the spec is enabled: data/ is not committed, so the file is absent in CI
const stats = process.env.E2E_MANPURA
  ? JSON.parse(
      readFileSync(fileURLToPath(new URL("../../data/processed/manpura/stats.json", import.meta.url)), "utf8"),
    )
  : {};

test("manpura: summary, point, compare, scenes, report, method", async ({ page, context }) => {
  await page.goto(`/?site=manpura&lat=${PT[1]}&lon=${PT[0]}&z=13&pt=${PT[0]},${PT[1]}&lang=en`);
  await expect(page.getByTestId("demo-banner")).toHaveCount(0);

  // the sidebar shows the pipeline's numbers
  const sidebar = page.getByRole("complementary").first();
  await expect(sidebar).toContainText(`${stats.land_lost_km2.eroded.toFixed(1)} km²`);
  await expect(sidebar).toContainText(String(stats.nisar_passes));

  // point card
  await expect(page.getByTestId("point-score")).toHaveText(/^\d{1,3}$/);
  const score = await page.getByTestId("point-score").textContent();
  await expect(page.getByText("Not measured at this site")).toBeVisible(); // motion_usable = false
  await page.screenshot({ path: "test-results/manpura-point.png" });

  // compare
  await page.getByTestId("tool-compare").click();
  await expect(page.getByTestId("compare-label-left")).toContainText("1988");
  await expect(page.getByTestId("compare-label-right")).toContainText("16 Oct 2026");
  await page.waitForTimeout(4000);
  await page.screenshot({ path: "test-results/manpura-compare.png" });
  await page.getByTestId("compare-exit").click();

  // scene search over a drawn area (real ASF)
  const canvas = page.locator('[data-testid="map"] canvas.maplibregl-canvas');
  const box = (await canvas.boundingBox())!;
  const x = box.x + box.width / 2 - 200;
  const y = box.y + box.height / 2;
  await page.getByTestId("tool-draw").click();
  await expect(page.getByTestId("draw-hint")).toBeVisible(); // the drawing library loads on demand
  await page.mouse.click(x - 60, y - 60);
  await page.mouse.click(x + 60, y - 60);
  await page.mouse.click(x + 60, y + 60);
  await page.mouse.dblclick(x - 60, y + 60);
  await expect(page.getByTestId("polygon-stats")).toBeVisible();
  await expect(page.getByTestId("scene-list").locator("li").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("scene-list")).toContainText("GCOV");
  await page.screenshot({ path: "test-results/manpura-polygon.png" });

  // report for the point
  const [report] = await Promise.all([
    context.waitForEvent("page"),
    page.goto(`/?site=manpura&lat=${PT[1]}&lon=${PT[0]}&z=13&pt=${PT[0]},${PT[1]}&lang=en`).then(() =>
      page.getByTestId("point-report").click(),
    ),
  ]);
  await expect(report.getByTestId("point-score")).toHaveText(score!);
  await expect(report.getByTestId("report-map-image")).toBeVisible({ timeout: 30_000 });
  await report.screenshot({ path: "test-results/manpura-report.png", fullPage: true });

  // method page: real validation numbers
  await page.goto("/method?site=manpura&lang=en");
  await expect(page.getByTestId("validation-area")).toBeVisible();
  await expect(page.getByTestId("validation-s2")).toContainText("Sentinel-2");
  await expect(page.getByTestId("limitations")).toContainText("Ground movement is not used at this site");
  await page.locator('[data-testid="validation-section"]').screenshot({ path: "test-results/manpura-validation.png" });
});
