import type {Page} from "@playwright/test"
import {expect, test} from "./support/test"
import {layoutProblems, layoutShift, lowContrast, watchErrors, watchShifts} from "./support/visitor"

// The home page (TechtreeWeb.HomeLive) at a desktop width and two phone widths,
// with the GPU on: the promise, the four services with their price levels, the
// case study whose figures count up, the process, the credits and the closing.
// Nothing moves the layout as it arrives. A visitor who asked for less motion,
// or whose browser has no WebGPU, keeps every still picture and every figure as
// the server wrote it.
test.use({launchOptions: {args: ["--enable-unsafe-webgpu", "--enable-gpu"]}})

// Each service's price level, in the order the cards show them.
const levels = [["skills", 1], ["evals", 2], ["environments", 3], ["models", 4]] as const

async function open(page: Page) {
  await page.goto("/", {waitUntil: "networkidle"})
  await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
}

// The case study's figures as the page shows them now.
const figures = (page: Page) => page.locator("#case-study-figures dd").allTextContents()

// Every block of words on the page, and every button in them.
const wordBlocks = (page: Page) =>
  page.locator(["#hero :is(h1, .mk-hero__lede, .rg-button)", "#services :is(.mk-section__head, .mk-service__words)",
    "#case-study :is(.mk-section__head, .mk-tallies > div, .mk-section__note, .mk-links)", "#process :is(.mk-section__head, li)",
    "#stack :is(.mk-section__head, .mk-maker__projects)", "#begin :is(h2, .mk-closing__line, .rg-button)"].join(", "))

for (const width of [1280, 390, 320]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    test("the promise, then four services each with its price level, and a card opens its page", async ({page}) => {
      const errors = watchErrors(page)
      await watchShifts(page)
      await open(page)
      await expect(page.locator("h1")).toHaveCount(1)
      await expect(page.locator("h1")).toHaveText("Better agents for your business.")
      await expect(page.locator("#hero-field")).toHaveAttribute("data-field-ready", "true")
      await expect(page.locator("#hero-field")).toHaveAttribute("aria-hidden", "true")

      for (const [id, level] of levels) {
        const card = page.locator(`#service-${id}`)
        await card.scrollIntoViewIfNeeded()
        const price = card.getByRole("img", {name: `Price level ${level} of 4`})
        await expect(price).toBeVisible()
        await expect(price.locator(".mk-price__mark")).toHaveCount(4)
        await expect(price.locator(".mk-price__mark--on")).toHaveCount(level)
      }

      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
      expect(await layoutShift(page)).toBeLessThan(0.1)
      expect(await layoutProblems(page)).toEqual([])

      // The whole card is its link.
      const card = page.locator("#service-environments")
      await card.scrollIntoViewIfNeeded()
      const box = (await card.boundingBox())!
      await (width < 768 ? page.touchscreen.tap(box.x + box.width / 2, box.y + box.height - 24) : page.mouse.click(box.x + box.width / 2, box.y + box.height - 24))
      await expect(page).toHaveURL("/services/environments")
      expect(errors).toEqual([])
    })

    test("the case study's figures count up to what the server wrote, and keep their place", async ({page}) => {
      const errors = watchErrors(page)
      await open(page)
      const tallies = page.locator("#case-study-figures")
      const written = await figures(page)
      expect(written.every(figure => /\d/.test(figure))).toBe(true)
      const before = (await tallies.boundingBox())!.height

      await tallies.scrollIntoViewIfNeeded()
      await expect.poll(() => figures(page)).not.toEqual(written)
      await expect.poll(() => figures(page), {timeout: 4000}).toEqual(written)
      expect((await tallies.boundingBox())!.height).toBe(before)
      expect(errors).toEqual([])
    })

    test("every part reads clearly in both themes, each logo on one plate", async ({page}) => {
      const plates: string[] = []
      for (const theme of ["light", "dark"] as const) {
        await page.emulateMedia({colorScheme: theme})
        await open(page)
        for (const block of await wordBlocks(page).all()) {
          await block.scrollIntoViewIfNeeded()
          expect(await lowContrast(block), `${await block.evaluate(el => el.className)} in ${theme}`).toEqual([])
        }
        const logos = page.locator("#stack .mk-maker__plate > img")
        await expect(logos).toHaveCount(3)
        for (const logo of await logos.all()) {
          await logo.scrollIntoViewIfNeeded()
          await expect(logo).toBeVisible()
          expect(await logo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
        }
        plates.push(...await page.locator("#stack .mk-maker__plate").evaluateAll(all => all.map(plate => getComputedStyle(plate).backgroundColor)))
      }
      // The logos are never recoloured, so every plate is the same in both themes.
      expect(new Set(plates).size).toBe(1)
    })

    test.describe("with less motion", () => {
      test.use({reducedMotion: "reduce"})

      test("every picture stays still and every figure stays as written", async ({page}) => {
        const errors = watchErrors(page)
        await open(page)
        const written = await figures(page)
        await expect(page.locator("#hero-field .mk-field__still")).toBeVisible()
        await page.locator("#case-study-figures").scrollIntoViewIfNeeded()
        await page.waitForTimeout(500)
        expect(await figures(page)).toEqual(written)
        for (const field of await page.locator("[data-field]").all())
          await expect(field).not.toHaveAttribute("data-field-ready", "true")
        expect(await layoutProblems(page)).toEqual([])
        expect(errors).toEqual([])
      })
    })

    test.describe("without WebGPU", () => {
      test("every picture says it will not draw and keeps its still", async ({page}) => {
        await page.addInitScript(() => Object.defineProperty(Navigator.prototype, "gpu", {get: () => undefined}))
        const errors = watchErrors(page)
        await open(page)
        await expect(page.locator("#hero-field")).toHaveAttribute("data-field-ready", "false")
        await expect(page.locator("#hero-field .mk-field__still")).toBeVisible()
        for (const field of await page.locator("[data-field]").all()) {
          await field.scrollIntoViewIfNeeded()
          await expect(field).toHaveAttribute("data-field-ready", "false")
        }
        expect(await layoutProblems(page)).toEqual([])
        expect(errors).toEqual([])
      })
    })
  })
}
