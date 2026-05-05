import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config — codifies the QA-only sweep we did manually on 2026-05-04.
 *
 * Scope: tests run against the Next.js frontend ONLY. Routes that depend
 * on the FastAPI backend (live agent_chat round-trip, real test
 * generation) are deliberately excluded — they cost OpenRouter API time
 * and are flaky to assert against. Frontend-only assertions are enough
 * to catch the regressions that hit us in QA: brand leaks, breadcrumb
 * dedup, sidebar persistence, scope-dropdown labels.
 *
 * Server: Playwright auto-starts `next dev` on port 3010 to avoid
 * stomping on the manual dev server (3001). Test base URL flows from
 * webServer.url so the spec doesn't hardcode it.
 */
export default defineConfig({
  testDir: "./e2e",
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3010",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev -- -p 3010",
    url: "http://localhost:3010",
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
    stdout: "pipe",
    stderr: "pipe",
  },
});
