// Every public page whose address is the same on any Techtree, signed out. The
// local walk (pages.spec.ts) and the live check (test/live/live.spec.ts) both
// open these; pages that depend on what a database or a folder of reports holds
// are added by each.
export const publicPages = ["/", "/start", "/docs", "/docs/install", "/docs/test-a-skill", "/docs/api", "/results",
  "/wallet-bench", "/train", "/verify", "/changelog",
  "/examples/tdd", "/repo2rlenv", "/services/verify", "/services/verify/sample-report",
  "/services/cyber-assist", "/services/cyber-assist/sample-report", "/formal", "/services/watchdog", "/account", "/account/agents", "/agents", "/agents/hermes", "/about", "/privacy", "/terms"]
