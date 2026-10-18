import {test as base, expect, type BrowserContext} from "@playwright/test"

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

// Every test's own page is kept offline, and fails if it reached outside.
export const test = base.extend<{outside: string[]}>({
  outside: async ({context}, use) => {
    const outside = await keepOffline(context)
    await use(outside)
    expect(outside, "requests that left the test machine").toEqual([])
  },
  page: async ({page, outside: _outside}, use) => use(page),
})

export {expect}
