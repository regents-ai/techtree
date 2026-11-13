// Every public page whose address is the same on any Techtree, signed out. The
// local walk (pages.spec.ts) and the live check (test/live/live.spec.ts) both
// open these; pages that depend on what a database or a folder of reports holds
// are added by each.
export const publicPages = ["/", "/docs", "/docs/run-locally", "/docs/install", "/docs/test-a-skill", "/docs/api",
  "/docs/verify", "/results", "/wallet-bench", "/changelog", "/examples/tdd",
  "/services/skills", "/services/evals", "/services/environments", "/services/models", "/services/security",
  "/services/security/sample-report", "/formal", "/account", "/account/agents", "/agents", "/agents/hermes",
  "/about", "/privacy", "/terms"]
