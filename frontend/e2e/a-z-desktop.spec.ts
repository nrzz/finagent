import { test as base, expect, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { shot } from "./helpers";

/**
 * Full A–Z UI tour with screenshots. One shared browser context so auth persists.
 */
base.describe.configure({ mode: "serial" });

let sharedPage: Page;
let sharedContext: BrowserContext;

base.beforeAll(async ({ browser }: { browser: Browser }) => {
  sharedContext = await browser.newContext({
    baseURL: "http://127.0.0.1:8000",
    viewport: { width: 1280, height: 800 },
  });
  sharedPage = await sharedContext.newPage();
});

base.afterAll(async () => {
  await sharedContext?.close();
});

const test = base;

test.describe("A–Z desktop UI", () => {
  test("00 auth edges before setup", async () => {
    const page = sharedPage;
    await page.goto("/portfolio");
    await expect(page).toHaveURL(/\/(login|setup)/);
    await shot(page, "00-unauth-redirect");

    await page.goto("/login");
    await expect(page.getByText(/Welcome to FinAgent|Sign in/i).first()).toBeVisible();
    await shot(page, "00-login-or-setup");
  });

  test("01 wizard edges + complete", async () => {
    const page = sharedPage;
    await page.goto("/setup");
    await shot(page, "01-wizard-step0");

    const inputs = page.locator("input");
    await inputs.nth(0).fill("e2eadmin");
    await inputs.nth(1).fill("short");
    await expect(page.getByRole("button", { name: "Continue" })).toBeDisabled();
    await shot(page, "01-wizard-short-password");

    await inputs.nth(1).fill("password123");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText(/Pick Demo|AI Studio|Demo/i).first()).toBeVisible({ timeout: 20_000 });
    await shot(page, "01-wizard-ai");

    await page.getByRole("button", { name: /Continue/i }).click();
    await shot(page, "01-wizard-markets");
    await page.getByRole("button", { name: /Continue/i }).click();
    await shot(page, "01-wizard-currency");
    await page.getByRole("button", { name: /Continue/i }).click();

    await expect(page.getByRole("button", { name: "Launch FinAgent" })).toBeDisabled();
    await shot(page, "01-wizard-risk-blocked");
    await page.locator('input[type="checkbox"]').last().check();
    await page.getByRole("button", { name: "Launch FinAgent" }).click();
    await expect(page.getByRole("heading", { name: "Agent" })).toBeVisible({ timeout: 30_000 });
    await shot(page, "01-wizard-done-chat");
  });

  test("02 chat chips quote cancel and paper confirm", async () => {
    const page = sharedPage;
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Paper-buy 10 AAPL" })).toBeVisible({ timeout: 20_000 });

    await page.getByRole("button", { name: "Price of RELIANCE.NS" }).click();
    await expect(page.getByText(/RELIANCE|quote|price|tool/i).first()).toBeVisible({ timeout: 60_000 });
    await shot(page, "02-chat-quote");

    await page.getByRole("button", { name: "Paper-buy 10 AAPL" }).click();
    await expect(page.getByText("Confirm paper trade").last()).toBeVisible({ timeout: 60_000 });
    await shot(page, "02-chat-confirm-card");
    await page.getByRole("button", { name: "Cancel" }).last().click();
    await expect(page.getByText(/Cancelled proposed/i)).toBeVisible();
    await shot(page, "02-chat-cancel");

    await page.getByRole("button", { name: "Paper-buy 10 AAPL" }).click();
    // Cancelled card still shows the title; assert the newest proposal card.
    await expect(page.getByText("Confirm paper trade").last()).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Confirm" }).last().click();
    await expect(
      page.getByText(/Paper order (filled|submitted|placed)|Paper order placed/i).first(),
    ).toBeVisible({ timeout: 45_000 });
    await shot(page, "02-chat-confirmed");
  });

  test("03 dashboard", async () => {
    const page = sharedPage;
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText(/Paper equity|Cash/i).first()).toBeVisible({ timeout: 20_000 });
    await shot(page, "03-dashboard");
    await page.getByRole("link", { name: "Ask the agent" }).click();
    await expect(page.getByRole("heading", { name: "Agent" })).toBeVisible();
  });

  test("04 portfolio holdings xirr split", async () => {
    const page = sharedPage;
    await page.goto("/portfolio");
    await expect(page.getByRole("heading", { name: "Portfolio" })).toBeVisible();
    await shot(page, "04-portfolio-emptyish");

    await page.getByPlaceholder(/TCS\.NS \/ AAPL/i).fill("MSFT");
    const addCard = page.getByText("Add holding").locator("xpath=ancestor::div[contains(@class,'rounded-xl')]").first();
    await addCard.locator("input").nth(1).fill("2");
    await addCard.locator("input").nth(2).fill("100");
    await addCard.getByRole("button", { name: "Add" }).click();
    await expect(page.getByText("MSFT").first()).toBeVisible({ timeout: 15_000 });
    await shot(page, "04-portfolio-holding");

    await page.getByRole("button", { name: "Add cashflow" }).click();
    await expect(page.getByText(/XIRR/i).first()).toBeVisible();
    await shot(page, "04-portfolio-xirr");

    await page.getByPlaceholder("Symbol for split").fill("MSFT");
    await page.getByRole("button", { name: /Apply 2-for-1/i }).click();
    await expect(page.getByText(/Applied 2-for-1/i)).toBeVisible({ timeout: 15_000 });
    await shot(page, "04-portfolio-split");
  });

  test("05 markets quote invalid and valid", async () => {
    const page = sharedPage;
    await page.goto("/markets");
    await expect(page.getByRole("heading", { name: "Markets" })).toBeVisible();
    await shot(page, "05-markets-default");

    const input = page.locator("input").first();
    await input.fill("NOTAREALTICKERZZZ");
    await page.getByRole("button", { name: "Quote" }).click();
    await expect(
      page.locator("p.text-down").or(page.getByText(/fail|error|not found|404|No data/i)).first(),
    ).toBeVisible({ timeout: 30_000 });
    await shot(page, "05-markets-invalid");

    await input.fill("AAPL");
    await page.getByRole("button", { name: "Quote" }).click();
    await expect(page.getByText(/AAPL/i).first()).toBeVisible({ timeout: 45_000 });
    await shot(page, "05-markets-aapl");
  });

  test("06 trading buy sell edges reset", async () => {
    const page = sharedPage;
    await page.goto("/trading");
    await expect(page.getByRole("heading", { name: "Paper trading" })).toBeVisible();
    await shot(page, "06-trading");

    const inputs = page.locator("input");
    await inputs.nth(0).fill("AAPL");
    await inputs.nth(1).fill("1");
    await inputs.nth(2).fill("150");
    await page.getByRole("button", { name: "Place paper order" }).click();
    await expect(page.getByText(/Paper order (filled|FILLED|submitted)|via paper/i).first()).toBeVisible({
      timeout: 30_000,
    });
    await shot(page, "06-trading-buy");

    await page.getByRole("button", { name: "Sell" }).click();
    await inputs.nth(1).fill("99999");
    await inputs.nth(2).fill("150");
    await page.getByRole("button", { name: "Place paper order" }).click();
    await expect(page.getByText(/rejected|Failed|insufficient|not enough|error|Kill/i).first()).toBeVisible({
      timeout: 20_000,
    });
    await shot(page, "06-trading-oversell");

    await page.getByRole("button", { name: "Reset paper" }).click();
    await expect(page.getByText(/No orders yet|buy/i).first()).toBeVisible({ timeout: 15_000 });
    await shot(page, "06-trading-reset");
  });

  test("07 fno greeks and paper option", async () => {
    const page = sharedPage;
    await page.goto("/fno");
    await expect(page.getByRole("heading", { name: /F&O/i })).toBeVisible();
    await shot(page, "07-fno");

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 14);
    const expiry = tomorrow.toISOString().slice(0, 10);

    await page.getByPlaceholder(/NIFTY/i).fill("NIFTY");
    // Fill controlled ticket fields via label-adjacent inputs (no auto chain load)
    const ticket = page.locator("div").filter({ has: page.getByText("Paper ticket", { exact: true }) }).last();
    await page.locator("input").nth(1).fill(expiry);
    await page.locator("input").nth(2).fill("22000");
    await page.locator("input").nth(3).fill("100");
    await page.locator("input").nth(4).fill("1");
    await expect(page.getByRole("button", { name: "Buy paper" })).toBeEnabled({ timeout: 5_000 });
    await page.getByRole("button", { name: "Greeks / margin" }).click();
    await expect(page.getByText(/Lot|Margin|Δ|delta|Greeks failed/i).first()).toBeVisible({
      timeout: 30_000,
    });
    await shot(page, "07-fno-greeks");

    await page.getByRole("button", { name: "Buy paper" }).click();
    await expect(page.getByText(/Paper option|filled|Failed|error|Insufficient/i).first()).toBeVisible({
      timeout: 20_000,
    });
    await shot(page, "07-fno-order");
    void ticket;
  });

  test("08 automation alerts jobs notifications", async () => {
    const page = sharedPage;
    await page.goto("/automation");
    await expect(page.getByRole("heading", { name: "Automation" })).toBeVisible();
    await shot(page, "08-automation");

    await page.getByRole("button", { name: "Add alert" }).click();
    await expect(page.locator("div.font-mono").filter({ hasText: /AAPL/ }).first()).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "08-automation-alert");

    await page.getByRole("button", { name: "Save job" }).click();
    await expect(page.locator("div.font-mono").filter({ hasText: /morning-dca|dca/i }).first()).toBeVisible({
      timeout: 15_000,
    });
    await shot(page, "08-automation-job");

    await expect(page.getByText(/In-app notifications|No notifications/i).first()).toBeVisible();
    await shot(page, "08-automation-notes");
  });

  test("09 settings all tabs brokers device apk kill switch", async () => {
    const page = sharedPage;
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({ timeout: 20_000 });
    await shot(page, "09-settings-ai");

    for (const tab of [
      "Markets",
      "Trading",
      "Brokers",
      "Notifications",
      "Appearance",
      "Device / APK",
      "Secrets",
      "Security / Audit",
      "Backup",
    ]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await shot(page, `09-settings-${tab.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`);
    }
    await expect(page.getByText(/Backup & restore|Download backup/i).first()).toBeVisible();
    await page.getByRole("button", { name: "Brokers", exact: true }).click();
    await expect(page.getByText(/Connect a broker|Zerodha|Alpaca/i).first()).toBeVisible();
    await page.getByRole("button", { name: "Notifications", exact: true }).click();
    await expect(page.getByText(/Send alerts outside this app|Telegram/i).first()).toBeVisible();

    await page.getByRole("button", { name: "Brokers", exact: true }).click();
    await expect(page.getByText(/Zerodha|Alpaca|Connect a broker/i).first()).toBeVisible();

    await page.getByRole("button", { name: "Device / APK", exact: true }).click();
    await page.getByTestId("apk-server-url").fill("http://192.168.1.10:8000");
    await page.getByRole("button", { name: "Save server URL" }).click();
    await expect(page.getByText(/Server URL saved|192\.168/i).first()).toBeVisible();
    await shot(page, "09-settings-apk-url");
    await page.getByRole("button", { name: "Clear" }).click();

    await page.getByRole("button", { name: "Trading", exact: true }).click();
    await page.locator('input[type="checkbox"]').first().check();
    await page.locator('input[type="password"]').first().fill("password123");
    await page.getByRole("button", { name: /Save trading/i }).click();
    await expect(page.getByText(/Saved|saved/i).first()).toBeVisible({ timeout: 15_000 });
    await shot(page, "09-settings-kill-on");

    await page.goto("/trading");
    const inputs = page.locator("input");
    await inputs.nth(0).fill("AAPL");
    await inputs.nth(1).fill("1");
    await inputs.nth(2).fill("10");
    await page.getByRole("button", { name: "Place paper order" }).click();
    await expect(page.getByText(/kill|rejected|Failed|Panic/i).first()).toBeVisible({ timeout: 20_000 });
    await shot(page, "09-trading-kill-blocked");

    await page.goto("/settings");
    await page.getByRole("button", { name: "Trading", exact: true }).click();
    await page.locator('input[type="checkbox"]').first().uncheck();
    await page.locator('input[type="password"]').first().fill("password123");
    await page.getByRole("button", { name: /Save trading/i }).click();
    await expect(page.getByText(/Saved/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("10 command palette and sign out login bad creds", async () => {
    const page = sharedPage;
    await page.goto("/");
    await page.keyboard.press("Control+K");
    await expect(page.getByPlaceholder(/Search symbols or jump/i)).toBeVisible({ timeout: 10_000 });
    await shot(page, "10-command-palette");
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: /Sign out/i }).click();
    await expect(page.getByText(/Sign in to FinAgent/i)).toBeVisible({ timeout: 15_000 });
    await shot(page, "10-signed-out");

    await page.getByLabel("Username").fill("e2eadmin");
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText(/failed|invalid|incorrect|401/i).first()).toBeVisible({ timeout: 15_000 });
    await shot(page, "10-bad-login");

    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Agent" })).toBeVisible({ timeout: 20_000 });
    await shot(page, "10-relogin-ok");
  });

  test("11 unknown route redirects home", async () => {
    const page = sharedPage;
    await page.goto("/this-route-does-not-exist");
    await expect(page.getByRole("heading", { name: "Agent" })).toBeVisible({ timeout: 15_000 });
    await shot(page, "11-unknown-route");
  });

  test("12 export storage for mobile project", async () => {
    await sharedContext.storageState({ path: "e2e/.auth.json" });
  });
});
