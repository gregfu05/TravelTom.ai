import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:4173";
const serverUrl = new URL(baseURL);
const shouldStartWebServer = process.env.PLAYWRIGHT_SKIP_WEB_SERVER !== "1";

export default defineConfig({
  testDir: "./e2e",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  webServer: shouldStartWebServer
    ? {
        command: `npm run dev -- --host ${serverUrl.hostname} --port ${serverUrl.port}`,
        port: Number(serverUrl.port),
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
});
