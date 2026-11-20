import { defineConfig, devices } from "@playwright/test";

// Requiere el stack levantado (docker compose up) y el frontend en E2E_BASE_URL.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  workers: 1, // los tests comparten datos (cupos); se ejecutan en serie
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
