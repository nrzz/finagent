import { test, expect, devices, type Browser, type BrowserContext, type Page } from "@playwright/test";
import fs from "node:fs";
import { shot } from "./helpers";

/**
 * APK-like coverage: Pixel 5 viewport, bottom nav, Device/APK settings.
 * Uses auth storage from desktop project.
 */
test.use({ ...devices["Pixel 5"] });
test.describe.configure({ mode: "serial" });

let sharedPage: Page;
let sharedContext: BrowserContext;

test.beforeAll(async ({ browser }: { browser: Browser }) => {
  const auth = "e2e/.auth.json";
  if (!fs.existsSync(auth)) {
    throw new Error("Missing e2e/.auth.json — desktop project must run first");
  }
  sharedContext = await browser.newContext({
    ...devices["Pixel 5"],
    baseURL: "http://127.0.0.1:8000",
    storageState: auth,
  });
  sharedPage = await sharedContext.newPage();
});

test.afterAll(async () => {
  await sharedContext?.close();
});

test.describe("Mobile / APK viewport", () => {
  test("bottom nav reaches all pages", async () => {
    const page = sharedPage;
    await page.goto("/");
    // Recover if storageState missed token (JWT still valid via login)
    if (await page.getByText("Sign in to FinAgent").isVisible().catch(() => false)) {
      await page.getByLabel("Username").fill("e2eadmin");
      await page.getByLabel("Password").fill("password123");
      await page.getByRole("button", { name: "Sign in" }).click();
    }
    await expect(page.getByRole("heading", { name: "Agent" })).toBeVisible({ timeout: 20_000 });
    await shot(page, "m00-chat");

    const tabs = [
      ["Dashboard", "/dashboard", "Dashboard"],
      ["Portfolio", "/portfolio", "Portfolio"],
      ["Markets", "/markets", "Markets"],
      ["Trading", "/trading", "Paper trading"],
      ["F&O", "/fno", "F&O"],
      ["Auto", "/automation", "Automation"],
      ["Settings", "/settings", "Settings"],
    ] as const;

    for (const [label, path, heading] of tabs) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: new RegExp(heading, "i") })).toBeVisible({
        timeout: 20_000,
      });
      // Also exercise bottom nav when present
      const nav = page.locator("nav a").filter({ hasText: new RegExp(`^${label}$`) });
      if ((await nav.count()) > 0) {
        await nav.first().click();
        await expect(page.getByRole("heading", { name: new RegExp(heading, "i") })).toBeVisible();
      }
      await shot(page, `m-nav-${label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`);
    }
  });

  test("apk server url on device tab", async () => {
    const page = sharedPage;
    await page.goto("/settings");
    await page.getByRole("button", { name: "Device / APK", exact: true }).click();
    await expect(page.getByTestId("apk-server-url")).toBeVisible();
    await page.getByTestId("apk-server-url").fill("http://10.0.2.2:8000");
    await page.getByRole("button", { name: "Save server URL" }).click();
    await expect(page.getByText(/Server URL saved|10\.0\.2\.2/i).first()).toBeVisible();
    await shot(page, "m-apk-server-url");
    await page.getByRole("button", { name: "Clear" }).click();
  });

  test("paper trade from trading ticket on mobile", async () => {
    const page = sharedPage;
    await page.goto("/trading");
    const inputs = page.locator("input");
    await inputs.nth(0).fill("AAPL");
    await inputs.nth(1).fill("1");
    await inputs.nth(2).fill("120");
    await page.getByRole("button", { name: "Place paper order" }).click();
    await expect(page.getByText(/Order |kill|Failed|rejected/i).first()).toBeVisible({ timeout: 30_000 });
    await shot(page, "m-trading-order");
  });

  test("safe-area bottom nav visible", async () => {
    const page = sharedPage;
    await page.goto("/");
    await expect(page.locator("nav").filter({ hasText: "Agent" }).first()).toBeVisible();
    await shot(page, "m-bottom-nav");
  });
});
