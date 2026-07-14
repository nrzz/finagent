import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("wizard → chat paper confirm → portfolio", async ({ page }) => {
  await page.goto("/setup");
  await expect(page.getByText("Welcome to FinAgent")).toBeVisible();

  const inputs = page.locator("input");
  await inputs.nth(0).fill("smokeadmin");
  await inputs.nth(1).fill("password123");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText(/Pick Demo|AI Studio|Demo/i).first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: /Continue/i }).click();

  await page.getByRole("button", { name: /Continue/i }).click();
  await page.getByRole("button", { name: /Continue/i }).click();

  await page.locator('input[type="checkbox"]').last().check();
  await page.getByRole("button", { name: "Launch FinAgent" }).click();

  await expect(page.getByRole("button", { name: "Paper-buy 10 AAPL" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Paper-buy 10 AAPL" }).click();
  await expect(page.getByText("Confirm paper trade")).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(
    page.getByText(/Paper order (filled|submitted|placed)|Paper order placed/i).first(),
  ).toBeVisible({ timeout: 45_000 });

  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Portfolio" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Holdings" })).toBeVisible();
});
