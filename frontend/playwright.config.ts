import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 1,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "../.venv/bin/uvicorn main:app --app-dir .. --host 127.0.0.1 --port 8765",
    url: "http://127.0.0.1:8765/api/v2/health",
    reuseExistingServer: true,
    timeout: 120000,
  },
  projects: [
    { name: "chromium-1440", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "chromium-1024", use: { viewport: { width: 1024, height: 768 } } },
  ],
});
