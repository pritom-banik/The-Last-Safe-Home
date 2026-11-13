/** Phone layout (SPEC §10.2): bottom sheet with Layers · Summary tabs, full-screen point card, menu for pages. */
import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("phone: bottom sheet, full-screen card, menu", async ({ page }) => {
  await page.goto("/?site=demo&lat=22.65&lon=90.663&z=14");
  await expect(page.getByTestId("demo-banner")).toBeVisible();
  await expect(page.getByTestId("sidebar")).toHaveCount(0);
  await expect(page.getByTestId("time-slider")).toBeVisible();

  // bottom sheet: Layers tab opens the layer list, tapping it again folds it
  const layersTab = page.getByTestId("sheet-tab-layers");
  await layersTab.click();
  await expect(layersTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByLabel("Home Risk Score", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/phase8-mobile-layers.png" });
  await page.getByTestId("sheet-tab-summary").click();
  await expect(page.getByText("NISAR passes used")).toBeVisible();
  await page.getByTestId("sheet-tab-summary").click();
  await expect(page.getByRole("tabpanel")).toHaveCount(0);

  // tap a land point → the card fills the screen; Close returns to the map
  const canvas = page.locator('[data-testid="map"] canvas.maplibregl-canvas');
  const box = (await canvas.boundingBox())!;
  await page.waitForTimeout(500);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  const drawer = page.getByTestId("drawer");
  await expect(page.getByTestId("point-score")).toHaveText(/^\d{1,3}$/);
  const d = (await drawer.boundingBox())!;
  expect(d.width).toBeGreaterThanOrEqual(389);
  expect(d.height).toBeGreaterThanOrEqual(840);
  await page.screenshot({ path: "test-results/phase8-mobile-card.png" });
  await page.getByRole("button", { name: "Close" }).click();
  await expect(drawer).toBeHidden();

  // the overflow menu reaches the Method page
  await page.getByLabel("Menu").click();
  await page.getByRole("link", { name: "Method" }).click();
  await expect(page.getByTestId("validation-section")).toBeVisible();
});

test("crash-free when the API is down: plain-language banner and retry", async ({ page }) => {
  await page.route("**/api/v1/**", (r) => r.abort());
  await page.goto("/?site=demo");
  await expect(page.getByTestId("server-banner")).toContainText("not answering", { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
