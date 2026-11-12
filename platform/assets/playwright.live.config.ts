import {defineConfig, devices} from "@playwright/test"

// The live check (make live-check, scripts/live-check.sh): the live site read the
// way a visitor's and an agent's browser read it, in headless Chromium at 1280 and
// 390 wide, signed out (test/live/live.spec.ts). It starts no server and writes
// nothing: no form is sent and no signed tool is called. Chromium only: WebKit is
// not run on the Mac.
const baseURL = process.env.LIVE_URL
if (!baseURL) throw new Error("Set LIVE_URL to the live site's address. Run it through make live-check.")

export default defineConfig({
  testDir: "./test/live",
  fullyParallel: true,
  workers: 2,
  forbidOnly: true,
  retries: 0,
  reporter: "line",
  // Global Privacy Control, so the check's pages start no visit in the site's log
  // (TechtreeWeb.VisitLog).
  use: {baseURL, extraHTTPHeaders: {"sec-gpc": "1"}, trace: "off"},
  projects: [
    {name: "desktop", use: {...devices["Desktop Chrome"], viewport: {width: 1280, height: 900}}},
    {name: "phone", use: {...devices["Pixel 7"], viewport: {width: 390, height: 844}}},
  ],
})
