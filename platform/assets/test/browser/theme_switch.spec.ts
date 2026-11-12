import type {Locator, Page} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The light and dark theme switch (TechtreeWeb.Components.ThemeSwitch). It is a
// real switch, on for the light theme: a press, Space or Enter turns the page's
// theme once, and the choice holds over a reload and a live page change. Signed
// in it is a row of the account menu, which keeps its size whichever way it is
// turned; signed out it sits in the header beside Sign in. There is one on a page.
const toggle = (page: Page) => page.getByRole("switch", {name: "Light theme"})
const menu = (page: Page) => page.locator("#account-menu")

// The theme on screen: the page's own once chosen, otherwise the device's.
const showing = (page: Page) =>
  page.evaluate(() => {
    const theme = document.documentElement.dataset.theme
    if (theme === "light" || theme === "dark") return theme
    return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"
  })

const otherThan = (theme: "light" | "dark") => (theme === "light" ? "dark" : "light")

// The switch says what the page shows: on for light, off for dark.
async function expectTheme(page: Page, theme: "light" | "dark") {
  await expect.poll(() => showing(page)).toBe(theme)
  await expect(toggle(page)).toHaveCount(1)
  await expect(toggle(page)).toHaveAttribute("aria-checked", String(theme === "light"))
}

// The page, with the account control beside it ready to answer a press.
async function open(page: Page, path: string) {
  await page.goto(path, {waitUntil: "networkidle"})
  await expect(page.locator(".masthead__account.phx-connected")).toBeAttached()
}

// Opened, and done dropping in, so what is measured is where it rests.
async function openMenu(page: Page, press: (target: Locator) => Promise<void>) {
  await press(page.locator("#account-chip"))
  await expect(menu(page)).toBeVisible()
  await expect.poll(() => menu(page).evaluate(element => element.getAnimations().length)).toBe(0)
}

const size = async (page: Page) => {
  const box = (await menu(page).boundingBox())!
  return {width: box.width, height: box.height}
}

for (const width of [1280, 320]) {
  test(`at ${width} wide, signed in, the account menu's theme switch turns the theme by press and by key, and the choice holds`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())
    await open(page, "/docs")

    // Opening the menu moves nothing on the page.
    const content = page.locator("main")
    const before = await content.boundingBox()
    await openMenu(page, press)
    expect(await content.boundingBox()).toEqual(before)

    const first = await showing(page)
    const other = otherThan(first)
    await expectTheme(page, first)
    const opened = await size(page)

    await press(toggle(page))
    await expectTheme(page, other)
    await expect(menu(page)).toBeVisible()
    expect(await size(page)).toEqual(opened)

    await toggle(page).focus()
    await page.keyboard.press("Space")
    await expectTheme(page, first)
    await page.keyboard.press("Enter")
    await expectTheme(page, other)
    expect(await size(page)).toEqual(opened)
    expect(await layoutProblems(page)).toEqual([])

    await page.reload({waitUntil: "networkidle"})
    await expect(page.locator(".masthead__account.phx-connected")).toBeAttached()
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(other)
    await openMenu(page, press)
    await expectTheme(page, other)

    // A guide opens as a live page change: the document stays and restates its theme.
    await page.keyboard.press("Escape")
    await press(page.locator("main a.docs-index__link").first())
    await expect(page).toHaveURL(/\/docs\/[a-z0-9-]+$/)
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(other)
    await openMenu(page, press)
    await expectTheme(page, other)

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}

// Signed out there is no account menu, so the switch sits in the header. Each
// press turns it once, from a device set to light and from one set to dark.
for (const [path, colorScheme] of [["/", "dark"], ["/docs", "light"]] as const) {
  test(`signed out on ${path}, on a ${colorScheme}-set device, the header's theme switch turns the theme once a press`, async ({browser}) => {
    const context = await browser.newContext({colorScheme})
    const outside = await keepOffline(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    await open(page, path)

    const other = otherThan(colorScheme)
    await expect(page.locator(".masthead").getByRole("switch")).toHaveCount(1)
    await expectTheme(page, colorScheme)

    await toggle(page).click()
    await expectTheme(page, other)

    await toggle(page).focus()
    await page.keyboard.press("Space")
    await expectTheme(page, colorScheme)
    await page.keyboard.press("Enter")
    await expectTheme(page, other)

    await page.reload({waitUntil: "networkidle"})
    await expect(page.locator(".masthead__account.phx-connected")).toBeAttached()
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(other)
    await expectTheme(page, other)
    expect(await layoutProblems(page)).toEqual([])
    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
