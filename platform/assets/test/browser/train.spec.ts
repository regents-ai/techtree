import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The Train pages signed in, at a desktop and a phone width (pages.spec.ts walks
// them signed out): they load and join, nothing errors, nothing scrolls sideways,
// the newest comparison leads, and Settings on it opens the comparison's settings.
for (const width of [1280, 390]) {
  test(`signed in at ${width} wide, Train leads with the newest comparison and Settings opens its settings`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)

    await page.goto("/train", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()
    await expect(page.locator("#account-chip")).toBeVisible()
    await expect(page.locator("#train-lead h2 a")).toHaveAttribute("href", "/train/nemotron-lightning-rl")
    expect(await layoutProblems(page)).toEqual([])

    await page.locator("#train-lead a[href='/train/nemotron-lightning-rl#settings']").click()
    await expect(page).toHaveURL("/train/nemotron-lightning-rl#settings")
    await expect(page.locator("#settings")).toBeInViewport()
    expect(await layoutProblems(page)).toEqual([])

    await page.goto("/train/nemotron-nano-skill", {waitUntil: "networkidle"})
    await page.locator("#every-task summary").click()
    await expect(page.locator("#every-task tbody tr")).toHaveCount(64)
    expect(await layoutProblems(page)).toEqual([])

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
