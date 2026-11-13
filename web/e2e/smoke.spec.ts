import { expect, test } from "@playwright/test";

test("home page renders and Start opens the map", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("home-title")).toHaveText("The Last Safe Home");
  await expect(page.getByTestId("home-team")).toHaveText("Team Nova Logits");
  await page.getByTestId("home-start").first().click();
  await expect(page).toHaveURL(/\/map\?.*site=manpura/);
  const canvas = page.locator('[data-testid="map"] canvas.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box!.width).toBeGreaterThan(300);
  expect(box!.height).toBeGreaterThan(300);
  await expect(page.getByText("OpenStreetMap")).toBeVisible();
  await page.screenshot({ path: "test-results/phase1-map.png" });
});

test("old map links at / still open the map", async ({ page }) => {
  await page.goto("/?site=demo&lat=22.65&lon=90.663&z=14");
  await expect(page).toHaveURL(/\/map\?site=demo/);
  await expect(page.getByTestId("demo-banner")).toBeVisible();
});
