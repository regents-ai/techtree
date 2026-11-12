import type {Page} from "@playwright/test"
import {expect, test} from "./support/test"

// The value cards row on the home page (TechtreeWeb.Components.ValueCards):
// six cards, each a GPU panel over its still frame. The row's first version crashed
// the browser at phone width (CHANGELOG, 12 Nov 2026), so these open it at 1280 on
// a desktop and at 390 and 320 on a phone with the GPU on, move a pointer over
// every card, and ask that the page lived, every panel drew, the cards fill their
// columns and nothing reaches past the screen's edge. Then the two ways a visitor
// keeps the still frames: less motion asked for, and a browser without WebGPU.
test.use({launchOptions: {args: ["--enable-unsafe-webgpu", "--enable-gpu"]}})

// The page's script heap after the moves: far above what six panels need, far below
// the gigabyte the crash reached.
const HEAP_CEILING = 64 * 1024 * 1024

const cards = (page: Page) => page.locator("#cards-row > li")

async function open(page: Page) {
  await page.goto("/")
  await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
  await expect(cards(page)).toHaveCount(6)
}

// Every still frame arrives, each scrolled to as a visitor would.
async function stillsArrive(page: Page) {
  for (const still of await page.locator("#cards-row .value-cards__still").all()) {
    await still.scrollIntoViewIfNeeded()
    await expect.poll(() => still.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  }
}

async function sweep(page: Page) {
  for (const card of await cards(page).all()) {
    await card.scrollIntoViewIfNeeded()
    const box = (await card.boundingBox())!
    await page.mouse.move(box.x + 4, box.y + 4)
    await page.mouse.move(box.x + box.width - 4, box.y + box.height - 4, {steps: 12})
  }
}

const sideways = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

const columns = (page: Page) =>
  cards(page).evaluateAll(items => new Set(items.map(item => Math.round(item.getBoundingClientRect().left))).size)

test("every card draws its panel, outlasts the pointer and fits the screen", async ({page, isMobile}) => {
  let crashed = false
  page.on("crash", () => { crashed = true })

  for (const {width, wanted} of isMobile ? [{width: 390, wanted: 1}, {width: 320, wanted: 1}] : [{width: 1280, wanted: 3}]) {
    await page.setViewportSize({width, height: 800})
    await open(page)
    await stillsArrive(page)
    for (const card of await cards(page).all()) {
      await card.scrollIntoViewIfNeeded()
      await expect(card).toHaveAttribute("data-value-card-ready", "true")
    }

    await sweep(page)
    await sweep(page)

    expect(crashed).toBe(false)
    await expect(cards(page).first()).toHaveAttribute("data-value-card-ready", "true")
    expect(await columns(page)).toBe(wanted)
    expect(await sideways(page)).toBe(0)
    const cdp = await page.context().newCDPSession(page)
    const {usedSize} = await cdp.send("Runtime.getHeapUsage")
    expect(usedSize).toBeLessThan(HEAP_CEILING)
  }
})

test.describe("with less motion", () => {
  test.use({reducedMotion: "reduce"})

  test("no panel draws and every card keeps its still frame", async ({page}) => {
    await open(page)
    await stillsArrive(page)
    await sweep(page)
    for (const card of await cards(page).all())
      await expect(card).not.toHaveAttribute("data-value-card-ready", "true")
    expect(await sideways(page)).toBe(0)
  })
})

test.describe("without WebGPU", () => {
  test("every card says it will not draw and keeps its still frame", async ({page}) => {
    await page.addInitScript(() => Object.defineProperty(Navigator.prototype, "gpu", {get: () => undefined}))
    await open(page)
    for (const card of await cards(page).all())
      await expect(card).toHaveAttribute("data-value-card-ready", "false")
    await stillsArrive(page)
    expect(await sideways(page)).toBe(0)
  })
})
