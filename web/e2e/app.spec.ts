/**
 * SPEC §11 web e2e flow on the demo site, plus the report and about pages.
 * Needs the API on :8000 with the demo site (see playwright.config.ts).
 */
import { expect, test, type Page } from "@playwright/test";

// a high-score land point near the eroding east bank of the synthetic river
const VIEW = "/?site=demo&lat=22.65&lon=90.663&z=14";

async function mapCentre(page: Page) {
  const canvas = page.locator('[data-testid="map"] canvas.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  const box = (await canvas.boundingBox())!;
  return { canvas, x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

test("full flow: banner, layers, point card, polygon, slider, Bangla, compare, method", async ({ page }) => {
  await page.goto(VIEW);

  // app loads → demo banner visible
  await expect(page.getByTestId("demo-banner")).toHaveText("DEMO DATA — not real measurements");
  const { x, y } = await mapCentre(page);

  // toggle the score layer off and on
  const score = page.getByLabel("Home Risk Score", { exact: true });
  await expect(score).toBeChecked();
  await score.uncheck();
  await expect(score).not.toBeChecked();
  await score.check();
  await expect(score).toBeChecked();

  // click a land point → card shows a number and a years range
  await page.waitForTimeout(500); // let the map settle on the requested view
  await page.mouse.click(x, y);
  const card = page.getByTestId("point-card");
  await expect(card).toBeVisible();
  await expect(page.getByTestId("point-score")).toHaveText(/^\d{1,3}$/);
  await expect(page.getByTestId("point-outlook")).toHaveText(/The river may arrive in \d+(–\d+\+?)? years/);
  await expect(page).toHaveURL(/pt=90\.6\d+,22\.6\d+/);

  // draw a polygon → panel shows building counts
  await page.getByTestId("tool-draw").click();
  await expect(page.getByTestId("draw-hint")).toBeVisible(); // the drawing library loads on demand
  await page.mouse.click(x - 150, y - 150);
  await page.mouse.click(x + 150, y - 150);
  await page.mouse.click(x + 150, y + 150);
  await page.mouse.dblclick(x - 150, y + 150);
  await expect(page.getByTestId("polygon-panel")).toBeVisible();
  await expect(page.getByTestId("buildings-total")).toHaveText(/^\d[\d,]*$/);
  await expect(page.getByTestId("people-bar")).toBeVisible();

  // move the time slider → date label changes
  const label = page.getByTestId("slider-date");
  await expect(label).toHaveText("15 Oct 2026");
  await page.getByRole("slider", { name: "NISAR pass date" }).press("ArrowLeft");
  await expect(label).toHaveText("3 Oct 2026");
  await expect(page).toHaveURL(/date=2026-10-03/);

  // switch to বাংলা → Bangla labels appear
  await page.getByTestId("lang-toggle").click();
  await expect(page.getByTestId("demo-banner")).toHaveText("ডেমো তথ্য — আসল পরিমাপ নয়");
  await expect(page.getByText("ঘরের ঝুঁকি স্কোর", { exact: true }).first()).toBeVisible();
  await expect(label).toContainText("২০২৬");
  await expect(page).toHaveURL(/lang=bn/);
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");

  await page.screenshot({ path: "test-results/phase4-bn.png" });

  // open compare mode → two maps visible
  await page.getByTestId("tool-compare").click();
  await expect(page).toHaveURL(/mode=compare/);
  await expect(page.locator('[data-testid="compare-left"] canvas.maplibregl-canvas')).toBeVisible();
  await expect(page.locator('[data-testid="compare-right"] canvas.maplibregl-canvas')).toBeVisible();
  // both panes fill the map area (a stylesheet-order bug once collapsed them to zero height)
  for (const side of ["compare-left", "compare-right"]) {
    expect((await page.getByTestId(side).boundingBox())!.height).toBeGreaterThan(300);
  }
  await expect(page.locator(".maplibregl-compare")).toBeVisible();
  await expect(page.getByTestId("compare-label-left")).toContainText("১৯৮৮");
  await expect(page.getByTestId("compare-label-right")).toContainText("২০২৬");
  await page.screenshot({ path: "test-results/phase7-compare.png" });
  await page.getByTestId("compare-exit").click();
  await expect(page.getByTestId("compare")).toBeHidden();
  await expect(page).not.toHaveURL(/mode=compare/);

  // open /method → validation section renders (still in Bangla)
  await page.getByRole("link", { name: "পদ্ধতি" }).click();
  await expect(page).toHaveURL(/\/method\?.*lang=bn/);
  await expect(page.getByTestId("validation-section")).toBeVisible();
  await expect(page.getByTestId("validation-status")).toContainText("ডেমো এলাকা");
  await expect(page.getByTestId("limitations")).toBeVisible();
  await expect(page.getByTestId("credits")).toContainText("NISAR data courtesy of NASA/JPL-Caltech and ISRO");
  await page.screenshot({ path: "test-results/phase7-method-bn.png", fullPage: true });

  // back to the map keeps the view
  await page.getByRole("link", { name: "মানচিত্রে ফিরে যান" }).click();
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  await expect(page).toHaveURL(/site=demo.*lat=22\.6/);
});

test("point report prints the same numbers as the card", async ({ page, context }) => {
  await page.goto("/?site=demo&lat=22.65&lon=90.663&z=14&pt=90.663,22.65");
  await expect(page.getByTestId("point-card")).toBeVisible();
  const score = await page.getByTestId("point-score").textContent();
  const [report] = await Promise.all([context.waitForEvent("page"), page.getByTestId("point-report").click()]);
  await report.waitForLoadState();
  await expect(report).toHaveURL(/\/report\?site=demo&lon=90\.66300&lat=22\.65000/);
  await expect(report.getByTestId("report")).toBeVisible();
  await expect(report.getByTestId("point-score")).toHaveText(score!);
  await expect(report.getByText("DEMO DATA — not real measurements")).toBeVisible();
  await expect(report.getByText(/Estimate from satellite data, not an engineering survey/)).toBeVisible();
  // the map is turned into an image once its tiles have loaded
  await expect(report.getByTestId("report-map-image")).toBeVisible({ timeout: 25_000 });
  await report.emulateMedia({ media: "print" });
  await expect(report.getByTestId("report-print")).toBeHidden();
  await report.screenshot({ path: "test-results/phase7-report-point.png", fullPage: true });
});

test("polygon report and about page", async ({ page }) => {
  const ring = "[[90.665,22.63],[90.69,22.63],[90.69,22.65],[90.665,22.65]]";
  await page.goto(`/report?site=demo&polygon=${encodeURIComponent(ring)}&lang=bn`);
  await expect(page.getByTestId("report-polygon")).toBeVisible();
  await expect(page.getByTestId("buildings-total")).toHaveText(/^[১-৯][০-৯,]*$/); // non-zero, Bangla digits
  await expect(page.getByTestId("people-bar")).toBeVisible();
  await expect(page.getByTestId("report-map-image")).toBeVisible({ timeout: 25_000 });
  await page.screenshot({ path: "test-results/phase7-report-polygon-bn.png", fullPage: true });

  await page.goto("/about?lang=en");
  await expect(page.getByRole("heading", { name: "Data credits" })).toBeVisible();
  await expect(page.getByTestId("team-name")).toContainText("Nova Logits");
  await expect(page.getByTestId("team")).toContainText("Enam E Elahi");
  await expect(page.getByRole("link", { name: /github\.com/ })).toBeVisible();
  await expect(page.getByText("Landsat data courtesy of the U.S. Geological Survey.")).toBeVisible();
});

test("outside the study area and in the river", async ({ page }) => {
  await page.goto("/?site=demo&lat=22.65&lon=90.55&z=12");
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  const { x, y } = await mapCentre(page);
  await page.waitForTimeout(500);
  await page.mouse.click(x, y);
  await expect(page.getByTestId("point-error")).toHaveText(/outside the study area/);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("drawer")).toBeHidden();

  await page.goto("/?site=demo&lat=22.65&lon=90.652&z=14");
  const c = await mapCentre(page);
  await page.waitForTimeout(500);
  await page.mouse.click(c.x, c.y + 80); // clear of the union label at the centre
  await expect(page.getByTestId("point-outlook")).toHaveText("This point is in the river today");
  await expect(page.getByTestId("point-score")).toHaveCount(0);

  // the union label opens the union's statistics
  await page.getByRole("button", { name: "Demo Union Middle" }).click();
  await expect(page.getByTestId("union-panel")).toContainText("Demo Union Middle");
});

test("shared link reopens the view, layers and point", async ({ page }) => {
  await page.goto("/?site=demo&lat=22.65&lon=90.663&z=14&layers=score,transects&date=2026-09-09&pt=90.663,22.65");
  await expect(page.getByTestId("point-card")).toBeVisible();
  await expect(page.getByTestId("slider-date")).toHaveText("9 Sept 2026");
  await expect(page.getByLabel("Transects", { exact: true })).toBeChecked();
  await expect(page.getByLabel("Water (selected date)", { exact: true })).not.toBeChecked();
  await page.screenshot({ path: "test-results/phase4-en.png" });
});
