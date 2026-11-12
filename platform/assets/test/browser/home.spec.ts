import type {Locator, Page} from "@playwright/test"
import {expect, test} from "./support/test"
import {layoutProblems, lowContrast, publishResult, watchErrors} from "./support/visitor"

// The home page (TechtreeWeb.HomeLive) at a desktop width and two phone widths,
// with three published Results and the GPU on. The hero's newest Results turn by
// themselves, from the dots and by a swipe, and hold for Pause and for the
// keyboard. The first group of products opens one item at a time from the
// keyboard, and its picture follows the open item. A visitor who asked for less
// motion, or whose browser has no WebGPU, keeps every still picture, and for
// less motion the Results turn only by hand.
test.use({launchOptions: {args: ["--enable-unsafe-webgpu", "--enable-gpu"]}})

/** How long a Result stays in the middle (TURN_MS in carousel.ts), and a margin. */
const TURN = 5600 + 2500

// A failed test starts a new worker, which publishes three more; the carousel
// shows the newest five, so each test reads the Results it was shown.
test.beforeAll(() => {
  for (let i = 0; i < 3; i++) publishResult()
})

async function open(page: Page) {
  await page.goto("/", {waitUntil: "networkidle"})
  await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
  await page.locator("#hero-results").scrollIntoViewIfNeeded()
}

const middle = (page: Page) => page.locator("#hero-results [data-slot='centre'] .mk-result__link")
const dots = (page: Page) => page.locator("#hero-results [data-carousel-dot]")
// The carousel's Results, newest first, as the server drew them.
const shown = (page: Page) =>
  page.locator("#hero-results [data-carousel-card] .mk-result__link").evaluateAll(links => links.map(link => link.getAttribute("href")!))

// How far the active dot has filled, 0 to 1: the clock to the next turn.
const filled = (dot: Locator) =>
  dot.evaluate(el => {
    const fill = el.querySelector("[data-fill]")!.getBoundingClientRect()
    return fill.width / el.querySelector("[data-fill]")!.parentElement!.getBoundingClientRect().width
  })

// The active dot's clock over one second, held or running.
async function clockMoves(page: Page): Promise<boolean> {
  const dot = page.locator("#hero-results [data-carousel-dot][aria-current='true']")
  const before = await filled(dot)
  await page.waitForTimeout(1000)
  return (await filled(dot)) > before + 0.05
}

// A finger drawn sideways across the middle Result, as a phone reports it.
async function swipe(page: Page, by: number) {
  const box = (await page.locator("#hero-results [data-carousel-stage]").boundingBox())!
  const y = box.y + box.height / 2
  const x = box.x + box.width / 2
  const cdp = await page.context().newCDPSession(page)
  await cdp.send("Input.dispatchTouchEvent", {type: "touchStart", touchPoints: [{x, y}]})
  for (const step of [0.25, 0.5, 0.75, 1])
    await cdp.send("Input.dispatchTouchEvent", {type: "touchMove", touchPoints: [{x: x + by * step, y}]})
  await cdp.send("Input.dispatchTouchEvent", {type: "touchEnd", touchPoints: []})
  await cdp.detach()
}

// How many parts of the Evaluate & Climb cards are mid-move, placed by the loop rather than the stylesheet.
const moving = (page: Page) => page.locator("#evaluate [data-loop] [style*='transform']").count()

// The glyphs the still picture shows: only the open item's is drawn.
const shownGlyphs = (picture: Locator) =>
  picture.locator("[data-glyph]").evaluateAll(glyphs =>
    glyphs.filter(glyph => getComputedStyle(glyph).opacity === "1").map(glyph => glyph.getAttribute("data-glyph")),
  )

// Every block of words in the hero, the Stack and the On-ramp, and every button
// in them, the last Start's included.
const wordBlocks = (page: Page) =>
  page.locator(["#hero :is(.mk-pill, h1, .mk-hero__display, .mk-hero__lede, .mk-hero__built, .mk-hero__prompt, .mk-result, .rg-button)",
    "#stack :is(header, .mk-tile)", "#onramp :is(h2, .mk-band__line, .mk-band__more, .mk-path__stop, .rg-button)",
    "#begin .rg-button"].join(", "))

for (const width of [1280, 390, 320]) {
  test.describe(`${width} wide`, () => {
    test.use({viewport: {width, height: 844}, isMobile: width < 768, hasTouch: width < 768})

    test("the hero's Results turn, from the dots and by themselves, and hold when asked", async ({page}) => {
      const errors = watchErrors(page)
      await open(page)
      await expect(page.locator("h1")).toHaveCount(1)
      await expect(page.locator("h1")).toHaveText("Techtree")
      await expect(page.locator("#hero-field")).toHaveAttribute("data-field-ready", "true")
      await expect(page.locator("#hero-field")).toHaveAttribute("aria-hidden", "true")

      // The newest in the middle, its neighbours beside it out of reach.
      const results = await shown(page)
      const count = results.length
      expect(count).toBeGreaterThanOrEqual(3)
      await expect(middle(page)).toHaveAttribute("href", results[0])
      await expect(page.locator("#hero-results [data-carousel-card]:not([data-slot='centre'])[inert][aria-hidden='true']")).toHaveCount(count - 1)
      await expect(dots(page)).toHaveCount(count)
      await expect(dots(page).nth(0)).toHaveAttribute("aria-current", "true")

      // By itself, the next one comes in.
      await expect(middle(page)).toHaveAttribute("href", results[1], {timeout: TURN})
      await expect(dots(page).nth(1)).toHaveAttribute("aria-current", "true")

      // A dot brings its Result to the middle at once.
      await dots(page).nth(2).click()
      await expect(middle(page)).toHaveAttribute("href", results[2])
      await expect(page.locator("#hero-results [data-slot='next'] .mk-result__link")).toHaveAttribute("href", results[3 % count])
      await expect(page.locator("#hero-results [data-slot='prev'] .mk-result__link")).toHaveAttribute("href", results[1])

      // Pause holds it, and Play lets it go on.
      const pause = page.locator("#hero-results [data-carousel-pause]")
      await pause.click()
      await expect(pause).toHaveText("Play")
      expect(await clockMoves(page)).toBe(false)
      await pause.click()
      await expect(pause).toHaveText("Pause")
      expect(await clockMoves(page)).toBe(true)

      // Moving onto the dots from the keyboard holds it; Enter on a dot turns it.
      await dots(page).nth(2).focus()
      await page.keyboard.press("Shift+Tab")
      await expect(dots(page).nth(1)).toBeFocused()
      await page.keyboard.press("Enter")
      await expect(middle(page)).toHaveAttribute("href", results[1])
      expect(await clockMoves(page)).toBe(false)

      expect(await layoutProblems(page)).toEqual([])
      expect(errors).toEqual([])
    })

    test("the first group opens one item at a time from the keyboard, and its picture follows", async ({page}) => {
      const errors = watchErrors(page)
      await open(page)
      const group = page.locator("#measure")
      const items = group.locator("details")
      const picture = page.locator("#measure-picture")
      await picture.scrollIntoViewIfNeeded()
      await expect(picture).toHaveAttribute("data-field-ready", "true")
      await expect(items.nth(0)).toHaveAttribute("open", "")
      await expect(items.nth(0).locator("h3")).toHaveText("Evaluate & Climb")

      // Tab reaches the next item's heading past the open item's links; Enter opens it and closes the first.
      const second = items.nth(1)
      await items.nth(0).locator("a").last().focus()
      await page.keyboard.press("Tab")
      await expect(second.locator("summary")).toBeFocused()
      expect(await second.locator("summary").evaluate(el => getComputedStyle(el).outlineStyle)).not.toBe("none")
      await page.keyboard.press("Enter")
      await expect(second).toHaveAttribute("open", "")
      await expect(items.nth(0)).not.toHaveAttribute("open")
      await expect(group.locator("details[open]")).toHaveCount(1)
      await expect(picture).toHaveAttribute("data-field-shape", (await second.getAttribute("data-shape"))!)
      await expect(second.locator("[data-item-body]")).toBeVisible()

      // Space closes it again, and nothing in the group is left open.
      await page.keyboard.press(" ")
      await expect(second).not.toHaveAttribute("open")
      await expect(group.locator("details[open]")).toHaveCount(0)

      expect(await lowContrast(group)).toEqual([])
      expect(await layoutProblems(page)).toEqual([])
      expect(errors).toEqual([])
    })

    test("the Evaluate & Climb cards play while they are on the screen, and rest when they leave", async ({page}) => {
      await open(page)
      await page.locator("#evaluate [data-loop]").first().scrollIntoViewIfNeeded()
      await expect.poll(() => moving(page)).toBeGreaterThan(0)
      await page.evaluate(() => window.scrollTo(0, 0))
      await expect.poll(() => moving(page)).toBe(0)
    })

    test("the hero, the Stack and the On-ramp read clearly in both themes, each logo on one plate", async ({page}) => {
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

      test("every picture stays still, and the Results turn only from the dots", async ({page}) => {
        const errors = watchErrors(page)
        await open(page)
        const results = await shown(page)
        await expect(page.locator("#hero-field .mk-field__still")).toBeVisible()
        await expect(page.locator("#hero-results [data-carousel-pause]")).toBeHidden()
        await page.waitForTimeout(TURN)
        await expect(middle(page)).toHaveAttribute("href", results[0])
        await dots(page).nth(1).click()
        await expect(middle(page)).toHaveAttribute("href", results[1])

        // The Evaluate & Climb cards stay as drawn.
        await page.locator("#evaluate [data-loop]").first().scrollIntoViewIfNeeded()
        await page.waitForTimeout(1000)
        expect(await moving(page)).toBe(0)

        // The still picture beside the first group shows the open item's glyph.
        const items = page.locator("#measure details")
        const picture = page.locator("#measure-picture")
        await picture.scrollIntoViewIfNeeded()
        expect(await shownGlyphs(picture)).toEqual([await items.nth(0).getAttribute("data-shape")])
        await items.nth(2).locator("summary").click()
        expect(await shownGlyphs(picture)).toEqual([await items.nth(2).getAttribute("data-shape")])

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
        const results = await shown(page)
        await expect(middle(page)).toHaveAttribute("href", results[1], {timeout: TURN})
        for (const field of await page.locator("[data-field]").all()) {
          await field.scrollIntoViewIfNeeded()
          await expect(field).toHaveAttribute("data-field-ready", "false")
        }
        expect(await layoutProblems(page)).toEqual([])
        expect(errors).toEqual([])
      })
    })

    if (width < 768)
      test("a swipe turns the Results either way", async ({page}) => {
        await open(page)
        const results = await shown(page)
        await swipe(page, -120)
        await expect(middle(page)).toHaveAttribute("href", results[1])
        await swipe(page, 120)
        await expect(middle(page)).toHaveAttribute("href", results[0])
        await swipe(page, 120)
        await expect(middle(page)).toHaveAttribute("href", results.at(-1)!)
      })
  })
}
