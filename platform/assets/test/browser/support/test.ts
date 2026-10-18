import {execFileSync} from "node:child_process"
import {test as base, expect, type BrowserContext} from "@playwright/test"

// The open connections the test server holds to anywhere but this machine, read
// from the process listening on the test port. A server-side call to a chain, a
// sign-in service or any other outside address shows up here.
function serverOutsideConnections(): string[] {
  const run = (args: string[]) => {
    try {
      return execFileSync("lsof", args, {encoding: "utf8"})
    } catch {
      return ""
    }
  }
  const pid = run(["-tiTCP:4012", "-sTCP:LISTEN"]).trim().split("\n")[0]
  if (!pid) return []
  return run(["-nP", "-a", "-p", pid, "-iTCP", "-sTCP:ESTABLISHED"])
    .split("\n")
    .map(line => line.trim().split(/\s+/).at(-2) ?? "")
    .filter(name => name.includes("->"))
    .map(name => name.split("->")[1])
    .filter(remote => !/^(127\.0\.0\.1|\[::1\]|localhost):/.test(remote))
}

// Keeps a browser context offline from the world: the one outside service a page
// calls, GitHub's star count, is answered with a fixed count, and every other
// outside address is recorded so the test can fail on it.
export async function keepOffline(context: BrowserContext): Promise<string[]> {
  const outside: string[] = []
  await context.route(url => !["127.0.0.1", "localhost"].includes(url.hostname), route => {
    const url = new URL(route.request().url())
    if (url.hostname === "api.github.com")
      return route.fulfill({json: {stargazers_count: 5}, headers: {"access-control-allow-origin": "*"}})
    outside.push(url.origin + url.pathname)
    return route.fulfill({status: 204})
  })
  return outside
}

// Every test's own page is kept offline, and fails if it reached outside; and
// every test fails if the server it ran against opened a connection outside.
export const test = base.extend<{outside: string[]; serverOffline: void}>({
  outside: async ({context}, use) => {
    const outside = await keepOffline(context)
    await use(outside)
    expect(outside, "requests that left the test machine").toEqual([])
  },
  page: async ({page, outside: _outside}, use) => use(page),
  serverOffline: [
    async ({}, use) => {
      await use()
      expect(serverOutsideConnections(), "server connections that left the test machine").toEqual([])
    },
    {auto: true},
  ],
})

export {expect}
