import fs from "node:fs";
import path from "node:path";
import { expect, type Page } from "@playwright/test";

export const ARTIFACTS = path.join(process.cwd(), "e2e", "artifacts");

export function ensureArtifacts() {
  fs.mkdirSync(ARTIFACTS, { recursive: true });
}

export async function shot(page: Page, name: string) {
  ensureArtifacts();
  const safe = name.replace(/[^a-z0-9-_]+/gi, "_").toLowerCase();
  await page.screenshot({
    path: path.join(ARTIFACTS, `${safe}.png`),
    fullPage: true,
  });
}

export async function completeWizard(
  page: Page,
  opts: { username?: string; password?: string } = {},
) {
  const username = opts.username || "e2eadmin";
  const password = opts.password || "password123";
  await page.goto("/setup");
  await expect(page.getByText("Welcome to FinAgent")).toBeVisible();
  const inputs = page.locator("input");
  await inputs.nth(0).fill(username);
  await inputs.nth(1).fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/Pick Demo|AI Studio|Demo/i).first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: /Continue/i }).click();
  await page.getByRole("button", { name: /Continue/i }).click();
  await page.getByRole("button", { name: /Continue/i }).click();
  await page.locator('input[type="checkbox"]').last().check();
  await page.getByRole("button", { name: "Launch FinAgent" }).click();
  await expect(page.getByRole("heading", { name: "Agent" })).toBeVisible({ timeout: 30_000 });
}

export async function login(page: Page, username = "e2eadmin", password = "password123") {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Agent" }).or(page.getByText("Welcome to FinAgent"))).toBeVisible({
    timeout: 20_000,
  });
}
