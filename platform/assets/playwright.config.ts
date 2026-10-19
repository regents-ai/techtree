import {defineConfig, devices} from "@playwright/test"

// The browser tests start their own Techtree in the test environment, on its own
// database (techtree_test<partition>) and port, and stop it afterwards. They read
// pages the way a visitor does; nothing here reaches the live site. Two copies run
// side by side when each sets its own TECHTREE_BROWSER_COPY and TECHTREE_BROWSER_PORT.
// The database each run drops is always named for the browser tests
// (techtree_testbrowser<copy>), so a run never drops another test database.
const copy = process.env.TECHTREE_BROWSER_COPY ?? ""
const partition = `browser${copy}`
const port = Number(process.env.TECHTREE_BROWSER_PORT ?? 4012)
process.env.TECHTREE_BROWSER_PARTITION = partition
process.env.TECHTREE_BROWSER_PORT = String(port)
const baseURL = `http://127.0.0.1:${port}`
const server = `MIX_ENV=test MIX_TEST_PARTITION=${partition} TECHTREE_BROWSER_TEST=1`

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
      // A fresh database each run, so no run depends on what an earlier one left.
      `${server} mix do ash_postgres.drop --quiet + ash_postgres.create --quiet + techtree.setup_local_auth + ash.setup --quiet`,
      `${server} mix do phx.digest.clean --all + assets.deploy`,
      `${server} PORT=${port} mix phx.server`,
    ].join(" && "),
    // Health answers 503 on a database with no release imported, so readiness is the home page.
    url: `${baseURL}/`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
  projects: [{name: "chromium", use: {...devices["Desktop Chrome"]}}],
})
