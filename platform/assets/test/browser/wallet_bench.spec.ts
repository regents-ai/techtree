import {readFileSync} from "node:fs"
import {expect, test} from "./support/test"
import {type RecordedTest, layoutProblems, layoutShift, lowContrast, seedWalletBench, watchErrors, watchShifts, zipEntries} from "./support/visitor"

// Wallet Bench with recorded tests: the score grid and a result opened from it
// with its full results downloaded, the list, and each test's own page, at a
// desktop and two phone widths. Seeded once; the records are the same for every width.
let tests: {passed: RecordedTest; failed: RecordedTest; running: RecordedTest}
test.beforeAll(() => {
  tests = seedWalletBench()
})

// The grid draws once and stays still: nothing moves as the page connects, its
// fonts arrive or it sits open for half a minute.
for (const width of [1280, 390]) {
  test(`the grid holds still while it loads and after, ${width} wide`, async ({page}) => {
    test.setTimeout(90_000)
    await page.setViewportSize({width, height: 844})
    await watchShifts(page)
    await page.goto("/wallet-bench", {waitUntil: "networkidle"})
    await page.waitForTimeout(30_000)
    expect(await layoutShift(page)).toBeLessThan(0.1)
  })
}

for (const width of [1280, 390, 320]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    test("a score opens its result, whose full results download, and closes back to it", async ({page}) => {
      const errors = watchErrors(page)
      await page.goto("/wallet-bench", {waitUntil: "networkidle"})
      expect(await layoutProblems(page)).toEqual([])
      expect(await lowContrast(page.getByRole("region", {name: /^Scores/}))).toEqual([])

      const score = page.getByRole("link", {name: /^Hermes Agent with Bankr: 10.0 out of 10/})
      await score.click()
      const window = page.getByRole("dialog", {name: tests.passed.name})
      await expect(window).toBeVisible()
      await expect(page).toHaveURL(`/wallet-bench?result=${tests.passed.id}`)
      expect(await layoutProblems(page)).toEqual([])
      expect(await lowContrast(window)).toEqual([])

      const [download] = await Promise.all([
        page.waitForEvent("download"),
        window.getByRole("link", {name: "Download full results"}).click(),
      ])
      expect(download.suggestedFilename()).toBe(`wallet-test-${tests.passed.id.slice(0, 8)}.zip`)
      const folder = `wallet-test-${tests.passed.id.slice(0, 8)}`
      expect(zipEntries(readFileSync(await download.path())).sort()).toEqual([
        `${folder}/T1a/install.log`,
        `${folder}/T1a/session.jsonl`,
        `${folder}/T2/session.jsonl`,
        `${folder}/results.json`,
      ])

      await page.keyboard.press("Escape")
      await expect(window).toBeHidden()
      await expect(page).toHaveURL("/wallet-bench")
      await expect(score).toBeFocused()
      expect(errors).toEqual([])
    })

    test("every score reads clearly in both colour schemes, on both grids", async ({page}) => {
      for (const colorScheme of ["light", "dark"] as const) {
        await page.emulateMedia({colorScheme})
        for (const grid of ["/wallet-bench", "/wallet-bench?test=install"]) {
          await page.goto(grid, {waitUntil: "networkidle"})
          expect(await lowContrast(page.getByRole("region", {name: /^Scores/}))).toEqual([])
        }
      }
    })

    test("the list shows each recorded test and links to it", async ({page}) => {
      const errors = watchErrors(page)
      await page.goto("/wallet-bench?view=list", {waitUntil: "networkidle"})
      for (const {id, name} of Object.values(tests))
        await expect(page.getByRole("link", {name, exact: true}).and(page.locator(`[href="/wallet-bench/${id}"]`))).toBeVisible()
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
