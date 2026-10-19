import {expect, test} from "./support/test"
import {type RecordedTest, layoutProblems, seedWalletBench, watchErrors} from "./support/visitor"

// Wallet Bench with recorded tests: the list and each test's own page, at a desktop
// and two phone widths. Seeded once; the records are the same for every width.
let tests: {passed: RecordedTest; failed: RecordedTest; running: RecordedTest}
test.beforeAll(() => {
  tests = seedWalletBench()
})

for (const width of [1280, 390, 320]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    test("the list shows each recorded test and links to it", async ({page}) => {
      const errors = watchErrors(page)
      await page.goto("/wallet-bench", {waitUntil: "networkidle"})
      for (const {id, name} of Object.values(tests))
        await expect(page.getByRole("link", {name, exact: true})).toHaveAttribute("href", `/wallet-bench/${id}`)
      expect(await layoutProblems(page)).toEqual([])
      expect(errors).toEqual([])
    })

    for (const outcome of ["passed", "failed", "running"] as const) {
      test(`a ${outcome} test's own page`, async ({page}) => {
        const errors = watchErrors(page)
        const response = await page.goto(`/wallet-bench/${tests[outcome].id}`, {waitUntil: "networkidle"})
        expect(response?.status()).toBe(200)
        await expect(page.getByRole("heading", {level: 1, name: tests[outcome].name})).toBeVisible()
        await expect(page.getByRole("link", {name: "Wallet tests"})).toHaveAttribute("href", "/wallet-bench")
        expect(await layoutProblems(page)).toEqual([])
        expect(errors).toEqual([])
      })
    }
  })
}
