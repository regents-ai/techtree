import {expect, test} from "@playwright/test"
import {layoutProblems, watchErrors} from "./support/visitor"

// Every public page, signed out, at a desktop and a phone width: it loads, its
// live connection joins where it has one, nothing errors, nothing scrolls
// sideways and every press target is big enough to hit.
const pages = ["/", "/start", "/docs", "/results", "/wallet-bench", "/verify", "/changelog",
  "/blog", "/examples/tdd", "/repo2rlenv", "/account", "/about", "/privacy", "/terms"]

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

test("an address that names nothing answers 404 with a way home", async ({page}) => {
  const response = await page.goto("/climbs/does-not-exist")
  expect(response?.status()).toBe(404)
  await expect(page.locator("main a[href='/']").first()).toBeVisible()
})
