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
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "on-first-retry",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: `"${path.join(root, "backend", ".venv", "Scripts", "python.exe")}" "${path.join(root, "backend", "scripts", "playwright_server.py")}"`,
    cwd: path.join(root, "backend"),
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
