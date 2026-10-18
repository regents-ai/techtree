import {defineConfig, devices} from "@playwright/test"

// The browser tests start their own Techtree in the test environment, on its own
// database (techtree_testbrowser) and port, and stop it afterwards. They read
// pages the way a visitor does; nothing here reaches the live site.
const port = 4012
const baseURL = `http://127.0.0.1:${port}`
const server = "MIX_ENV=test MIX_TEST_PARTITION=browser TECHTREE_BROWSER_TEST=1"

export default defineConfig({
  testDir: "./test/browser",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  reporter: "line",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    cwd: "..",
    // The assets are built as production builds them, compressed copies included:
    // the server sends a compressed copy when there is one, so a stale one would
    // stand in for the change under test.
    command: [
      `${server} mix do ash_postgres.create --quiet + techtree.setup_local_auth + ash.setup --quiet`,
      `${server} mix assets.deploy`,
      `${server} PORT=${port} mix phx.server`,
    ].join(" && "),
    // Health answers 503 on a database with no release imported, so readiness is the home page.
    url: `${baseURL}/`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
  projects: [{name: "chromium", use: {...devices["Desktop Chrome"]}}],
})
