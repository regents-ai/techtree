import {expect, test} from "./support/test"
import {layoutProblems, watchErrors} from "./support/visitor"

// Every public page, signed out, at a desktop and a phone width: it loads, its
// live connection joins where it has one, nothing errors, nothing scrolls
// sideways and every press target is big enough to hit.
const pages = ["/", "/start", "/docs", "/docs/install", "/docs/test-a-skill", "/docs/api", "/results",
  "/wallet-bench", "/verify", "/changelog",
  "/examples/tdd", "/repo2rlenv", "/services/verify", "/services/verify/sample-report",
  "/services/cyber-assist", "/services/cyber-assist/sample-report", "/account", "/about", "/privacy", "/terms"]

for (const width of [1280, 390, 320]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    for (const path of pages) {
      test(`${path} works`, async ({page}) => {
        const errors = watchErrors(page)
        const response = await page.goto(path, {waitUntil: "networkidle"})
        expect(response?.status()).toBe(200)
        await expect(page.locator("main")).toBeVisible()
        if (await page.locator("[data-phx-main]").count()) await expect(page.locator(".phx-connected").first()).toBeAttached()
        expect(await layoutProblems(page)).toEqual([])
        expect(errors).toEqual([])
      })
    }
  })
}

test("on a phone, Menu opens the pages and one of them opens", async ({browser}) => {
  const context = await browser.newContext({viewport: {width: 320, height: 700}, isMobile: true, hasTouch: true})
  const page = await context.newPage()
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})
  const results = page.locator("#site-pages a[href='/results']")
  await expect(results).toBeHidden()
  // The header is one row: the name, Menu, theme switch and Sign in side by side.
  const boxes = await page.locator(".masthead__name, .masthead__menu-button, #site-theme-toggle, [data-account-target='sign-in']")
    .evaluateAll(els => els.map(e => e.getBoundingClientRect()).map(r => ({left: r.left, right: r.right, top: r.top, bottom: r.bottom})))
  expect(boxes).toHaveLength(4)
  for (const [a, b] of boxes.slice(1).map((box, i) => [boxes[i], box])) {
    expect(b.left).toBeGreaterThanOrEqual(a.right)
    expect(b.top).toBeLessThan(a.bottom)
  }
  await page.getByRole("button", {name: "Menu"}).tap()
  await expect(results).toBeVisible()
  expect(await layoutProblems(page)).toEqual([])
  await results.tap()
  await expect(page).toHaveURL("/results")
  expect(errors).toEqual([])
  await context.close()
})

test("on a wide screen the pages sit in a row with no Menu button", async ({page}) => {
  await page.setViewportSize({width: 1280, height: 844})
  await page.goto("/docs", {waitUntil: "networkidle"})
  await expect(page.getByRole("button", {name: "Menu"})).toBeHidden()
  await expect(page.locator("#site-pages a[href='/wallet-bench']")).toBeVisible()
})

test("an address that names nothing answers 404 with a way home", async ({page}) => {
  const response = await page.goto("/climbs/does-not-exist")
  expect(response?.status()).toBe(404)
  await expect(page.locator("main a[href='/']").first()).toBeVisible()
})
