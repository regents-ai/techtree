import type {Page} from "@playwright/test"
import {expect, test} from "./support/test"
import {publicPages} from "./support/pages"
import {layoutProblems, lowContrast, watchErrors} from "./support/visitor"

// Every public page, signed out, at a desktop and a phone width: it loads, its
// live connection joins where it has one, nothing errors, nothing scrolls
// sideways and every press target is big enough to hit.
// The test server's own Train comparison and the blog's posts join the pages
// every Techtree has.
const pages = [...publicPages, "/train/nemotron-nano-skill", "/blog"]

// The inner pages that open on the dark band.
const openings = ["/start", "/results", "/verify", "/wallet-bench", "/train", "/formal", "/repo2rlenv",
  "/services/verify", "/services/cyber-assist", "/services/watchdog", "/docs", "/agents", "/agents/hermes",
  "/changelog", "/blog", "/account"]

for (const theme of ["light", "dark"] as const) {
  test(`in ${theme}, every inner page opens on one band with one title, its words and buttons readable`, async ({page}) => {
    test.slow()
    await page.emulateMedia({colorScheme: theme})
    const errors = watchErrors(page)
    for (const path of openings) {
      await page.goto(path, {waitUntil: "networkidle"})
      const band = page.locator(".mk-opening")
      await expect(band, path).toHaveCount(1)
      await expect(page.locator("h1"), path).toHaveCount(1)
      await expect(band.locator("h1"), path).toBeVisible()
      // The title's words rise apart and are joined back once they have risen.
      await expect(band.locator("h1 [data-word]"), path).toHaveCount(0)
      expect(await lowContrast(band), `${path} in ${theme}`).toEqual([])
    }
    expect(errors).toEqual([])
  })
}

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

// Whether the browser tells a screen reader that the named header button's menu
// is open, read from the page's accessibility tree.
async function expanded(page: Page, name: string): Promise<boolean | undefined> {
  const cdp = await page.context().newCDPSession(page)
  const {nodes} = await cdp.send("Accessibility.getFullAXTree")
  await cdp.detach()
  const node = nodes.find(node => node.role?.value === "button" && node.name?.value === name)
  return node?.properties?.find(property => property.name === "expanded")?.value.value
}

for (const width of [390, 320]) {
  test(`at ${width} wide, Menu opens every page in one sheet over the page, and one of them opens`, async ({browser}) => {
    const context = await browser.newContext({viewport: {width, height: 700}, isMobile: true, hasTouch: true})
    const page = await context.newPage()
    const errors = watchErrors(page)
    await page.goto("/docs", {waitUntil: "networkidle"})
    const sheet = page.locator("#site-menu")
    const results = sheet.locator("a[href='/results']")
    await expect(sheet).toBeHidden()
    await expect(page.locator(".masthead__trigger").first()).toBeHidden()
    // The header is one row: the name, theme switch, Sign in and Menu side by side.
    const boxes = await page.locator(".masthead__name, #site-theme-switch, [data-account-target='sign-in'], .masthead__menu-button")
      .evaluateAll(els => els.map(e => e.getBoundingClientRect()).map(r => ({left: r.left, right: r.right, top: r.top, bottom: r.bottom})))
    expect(boxes).toHaveLength(4)
    for (const [a, b] of boxes.slice(1).map((box, i) => [boxes[i], box])) {
      expect(b.left).toBeGreaterThanOrEqual(a.right)
      expect(b.top).toBeLessThan(a.bottom)
    }
    expect(boxes.at(-1)!.right).toBeLessThanOrEqual(width)

    await page.getByRole("button", {name: "Menu"}).tap()
    await expect(sheet).toBeVisible()
    expect(await expanded(page, "Menu")).toBe(true)
    for (const group of ["Products", "Agents", "Resources"]) {
      await expect(sheet.locator(".sheet__title", {hasText: group})).toBeVisible()
    }
    const box = (await sheet.boundingBox())!
    expect(box.x).toBe(0)
    expect(box.width).toBe(width)
    expect(await layoutProblems(page)).toEqual([])
    await results.scrollIntoViewIfNeeded()
    await results.tap()
    await expect(page).toHaveURL("/results")
    await expect(sheet).toBeHidden()
    expect(errors).toEqual([])
    await context.close()
  })
}

test("on a wide screen, each menu opens by key, Tab walks into it, Escape closes it and gives focus back", async ({page}) => {
  await page.setViewportSize({width: 1280, height: 844})
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})
  await expect(page.getByRole("button", {name: "Menu"})).toBeHidden()

  for (const [name, id, first] of [["Products", "menu-products", "/start"], ["Agents", "menu-agents", "/agents"], ["Resources", "menu-resources", "/docs"]]) {
    const trigger = page.locator(".masthead__trigger", {hasText: name})
    const panel = page.locator(`#${id}`)
    await trigger.focus()
    await page.keyboard.press("Enter")
    await expect(panel).toBeVisible()
    expect(await expanded(page, name)).toBe(true)
    await page.keyboard.press("Tab")
    await expect(panel.locator(`a[href='${first}']`)).toBeFocused()
    await page.keyboard.press("Escape")
    await expect(panel).toBeHidden()
    await expect(trigger).toBeFocused()
    expect(await expanded(page, name)).toBe(false)
  }
  expect(errors).toEqual([])
})

test("on a wide screen, a menu follows the pointer to the next menu, closes on a press outside, and its pages open", async ({page}) => {
  await page.setViewportSize({width: 1280, height: 844})
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})
  const products = page.locator("#menu-products")
  const agents = page.locator("#menu-agents")

  await page.locator(".masthead__trigger", {hasText: "Products"}).click()
  await expect(products).toBeVisible()
  // Once it has dropped in, the menu hangs from the header's lower edge, give or
  // take the frame's top rule above an unscrolled header.
  const header = (await page.locator(".masthead").boundingBox())!
  await expect.poll(async () => Math.abs((await products.boundingBox())!.y - (header.y + header.height))).toBeLessThanOrEqual(1)
  expect(await layoutProblems(page)).toEqual([])

  await page.locator(".masthead__trigger", {hasText: "Agents"}).hover()
  await expect(agents).toBeVisible()
  await expect(products).toBeHidden()

  await page.mouse.click(640, 800)
  await expect(agents).toBeHidden()

  await page.locator(".masthead__trigger", {hasText: "Products"}).click()
  await products.locator("a[href='/wallet-bench']").click()
  await expect(page).toHaveURL("/wallet-bench")
  await expect(page.locator("#menu-products")).toBeHidden()
  await expect(page.locator("#menu-products a[href='/wallet-bench']")).toHaveAttribute("aria-current", "page")
  expect(errors).toEqual([])
})

test("an address that names nothing answers 404 with a way home", async ({page}) => {
  const response = await page.goto("/climbs/does-not-exist")
  expect(response?.status()).toBe(404)
  await expect(page.locator("main a[href='/']").first()).toBeVisible()
})
