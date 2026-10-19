import {expect, test} from "./support/test"
import {layoutProblems, seedWalletBench, watchErrors} from "./support/visitor"

// Wallet Bench with recorded tests: the list and each test's own page, at a desktop
// and two phone widths. Seeded once; the records are the same for every width.
let tests: {passed: string; failed: string; running: string}
test.beforeAll(() => {
  tests = seedWalletBench()
})

for (const width of [1280, 390, 320]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    test("the list shows each recorded test and links to it", async ({page}) => {
      const errors = watchErrors(page)
      await page.goto("/wallet-bench", {waitUntil: "networkidle"})
      for (const id of Object.values(tests)) await expect(page.locator(`a[href="/wallet-bench/${id}"]`).first()).toBeAttached()
      expect(await layoutProblems(page)).toEqual([])
      expect(errors).toEqual([])
    })

    for (const outcome of ["passed", "failed", "running"] as const) {
      test(`a ${outcome} test's own page`, async ({page}) => {
        const errors = watchErrors(page)
        const response = await page.goto(`/wallet-bench/${tests[outcome]}`, {waitUntil: "networkidle"})
        expect(response?.status()).toBe(200)
        await expect(page.locator("main h1")).toBeVisible()
        await expect(page.locator("main a[href='/wallet-bench']").first()).toBeVisible()
        expect(await layoutProblems(page)).toEqual([])
        expect(errors).toEqual([])
      })
    }
  })
}
