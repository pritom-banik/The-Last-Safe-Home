/**
 * Screenshots of every feature for the README (docs/screenshots/). Skipped unless SCREENSHOTS=1; needs the API
 * with real data (SITES=manpura,koyra,demo) and the built app:
 *   SCREENSHOTS=1 E2E_BASE_URL=http://localhost:4173 npx playwright test screenshots
 */
import { expect, test, type Page } from "@playwright/test";

test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to refresh docs/screenshots");
test.setTimeout(180_000);
test.use({ viewport: { width: 1440, height: 900 } });

const OUT = "../docs/screenshots";
const PT = { lon: 91.0195, lat: 22.378 }; // high-score point, north-east shore of Manpura
const shot = (page: Page, name: string) => page.screenshot({ path: `${OUT}/${name}.png` });

/** Wait until the map has drawn its tiles (no more tile requests for a moment). */
async function settle(page: Page, ms = 2500) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(ms);
}

async function mapBox(page: Page) {
  const canvas = page.locator('[data-testid="map"] canvas.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  return (await canvas.boundingBox())!;
}

test("desktop features", async ({ page, context }) => {
  // 1 overview: Home Risk Score, water, bank lines, unions
  await page.goto("/?site=manpura&lat=22.27&lon=90.97&z=11.3&lang=en");
  await expect(page.getByTestId("sidebar")).toContainText("NISAR passes used");
  await settle(page, 4000);
  await shot(page, "01-overview");

  // 2 point card
  await page.goto(`/?site=manpura&lat=${PT.lat}&lon=${PT.lon}&z=13.5&lang=en&pt=${PT.lon},${PT.lat}`);
  await expect(page.getByTestId("point-score")).toHaveText(/^\d+$/);
  await page.getByText("How is this calculated?").click();
  await settle(page);
  await shot(page, "02-point-card");

  // 3 drawn area: statistics + NISAR scenes
  await page.goto(`/?site=manpura&lat=22.37&lon=91.0&z=12.5&lang=en`);
  await settle(page);
  const b = await mapBox(page);
  const cx = b.x + b.width / 2 - 150;
  const cy = b.y + b.height / 2;
  await page.getByTestId("tool-draw").click();
  await expect(page.getByTestId("draw-hint")).toBeVisible();
  await page.mouse.click(cx - 120, cy - 110);
  await page.mouse.click(cx + 130, cy - 90);
  await page.mouse.click(cx + 110, cy + 120);
  await page.mouse.dblclick(cx - 130, cy + 100);
  await expect(page.getByTestId("polygon-stats")).toBeVisible();
  await expect(page.getByTestId("scene-list").locator("li").first()).toBeVisible({ timeout: 60_000 });
  await settle(page, 1500);
  await shot(page, "03-area-statistics");

  // 4 time slider + radar image on an earlier date
  await page.goto("/?site=manpura&lat=22.3&lon=90.98&z=12&lang=en&layers=sar_hh,water,banklines&date=2026-08-17");
  await expect(page.getByTestId("slider-date")).toHaveText("17 Aug 2026");
  await settle(page, 4000);
  await shot(page, "04-radar-time-slider");

  // 5 flood frequency
  await page.goto("/?site=manpura&lat=22.27&lon=90.97&z=11.3&lang=en&layers=floodfreq,banklines,unions");
  await settle(page, 4000);
  await shot(page, "05-flood-frequency");

  // 6 transects (bank retreat rates)
  await page.goto("/?site=manpura&lat=22.30&lon=90.975&z=12.2&lang=en&layers=water,transects,banklines");
  await expect(page.getByLabel("Transects", { exact: true })).toBeChecked();
  await settle(page, 4000);
  await shot(page, "06-transects");

  // 7 compare 1988 vs 2026
  await page.goto("/?site=manpura&lat=22.33&lon=90.99&z=12&lang=en&mode=compare");
  await expect(page.getByTestId("compare")).toBeVisible();
  await settle(page, 5000);
  await shot(page, "07-compare-1988-2026");

  // 8 union statistics
  await page.goto("/?site=manpura&lat=22.27&lon=90.97&z=11.3&lang=en");
  await settle(page, 3000);
  await page.getByRole("button", { name: "Manpura", exact: true }).click();
  await expect(page.getByTestId("union-panel")).toBeVisible();
  await settle(page, 1000);
  await shot(page, "08-union-statistics");

  // 9 Bangla
  await page.goto(`/?site=manpura&lat=${PT.lat}&lon=${PT.lon}&z=13&lang=bn&pt=${PT.lon},${PT.lat}`);
  await expect(page.getByTestId("point-score")).toBeVisible();
  await settle(page);
  await shot(page, "09-bangla");

  // 10 printable report
  await page.goto(`/?site=manpura&lat=${PT.lat}&lon=${PT.lon}&z=13&lang=en&pt=${PT.lon},${PT.lat}`);
  const [report] = await Promise.all([context.waitForEvent("page"), page.getByTestId("point-report").click()]);
  await report.setViewportSize({ width: 1100, height: 1400 });
  await expect(report.getByTestId("report-map-image")).toBeVisible({ timeout: 30_000 });
  await report.screenshot({ path: `${OUT}/10-report.png`, fullPage: true });
  await report.close();

  // 11 method page + live validation
  await page.goto("/method?site=manpura&lang=en");
  await expect(page.getByTestId("validation-s2")).toBeVisible();
  await page.getByTestId("validation-section").scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await shot(page, "11-method-validation");

  // 12 about
  await page.goto("/about?lang=en");
  await expect(page.getByTestId("team-name")).toBeVisible();
  await shot(page, "12-about");

  // 13 second site: Koyra
  await page.goto("/?site=koyra&lat=22.35&lon=89.3&z=11&lang=en");
  await expect(page.getByTestId("sidebar")).toContainText("NISAR passes used");
  await settle(page, 5000);
  await shot(page, "13-koyra");

  // 14 demo site (no downloads needed)
  await page.goto("/?site=demo&lat=22.65&lon=90.66&z=13&lang=en&pt=90.663,22.65");
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  await settle(page);
  await shot(page, "14-demo-site");
});

test("phone layout", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto("/?site=manpura&lat=22.33&lon=90.99&z=11.5&lang=en");
  await page.getByTestId("sheet-tab-layers").click();
  await settle(page, 3000);
  await page.screenshot({ path: `${OUT}/15-phone-layers.png` });
  await page.getByTestId("sheet-tab-layers").click();
  await page.goto(`/?site=manpura&lat=${PT.lat}&lon=${PT.lon}&z=13&lang=en&pt=${PT.lon},${PT.lat}`);
  await expect(page.getByTestId("point-score")).toBeVisible();
  await settle(page, 1000);
  await page.screenshot({ path: `${OUT}/16-phone-point-card.png` });
  await ctx.close();
});
