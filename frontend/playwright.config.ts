import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e/playwright-report" }]],
  outputDir: "e2e/test-results",
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: {
    // Prefer an already-running FinAgent (START.bat / CI uvicorn). Cross-platform
    // bootstrap is used only when nothing is listening on :8000.
    command:
      process.platform === "win32"
        ? `"${path.join(root, "backend", ".venv", "Scripts", "python.exe")}" "${path.join(root, "backend", "scripts", "playwright_server.py")}"`
        : `python "${path.join(root, "backend", "scripts", "playwright_server.py")}"`,
    cwd: path.join(root, "backend"),
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    {
      name: "desktop",
      testMatch: /a-z-desktop\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-apk",
      testMatch: /mobile-apk\.spec\.ts/,
      dependencies: ["desktop"],
      use: { ...devices["Pixel 5"] },
    },
  ],
});
