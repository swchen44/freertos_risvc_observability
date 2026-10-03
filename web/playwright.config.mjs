import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("..", import.meta.url));
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: [
    ["list"],
    ["json", { outputFile: "../artifacts/browser/results.json" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:8766",
    viewport: { width: 1600, height: 1000 },
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: ".venv/bin/python tools/browser_server.py",
    cwd: root,
    url: "http://127.0.0.1:8766/api/traces",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
