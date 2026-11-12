import {defineConfig} from "vitest/config"

// The script tests beside the browser tests (test/browser) and the live check
// (test/live), which Playwright runs.
export default defineConfig({
  test: {
    include: ["test/*.test.ts"],
  },
})
