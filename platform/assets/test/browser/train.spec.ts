import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The comparisons signed in, at a desktop and a phone width (pages.spec.ts walks
// them signed out): Results lists the newest first, it opens from there with
// every case in its table, and nothing errors or scrolls sideways.
for (const width of [1280, 390]) {
  test(`signed in at ${width} wide, Results lists the newest comparison first and it opens`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)

    await page.goto("/results", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()
    await expect(page.locator("#account-chip")).toBeVisible()
    const first = page.locator("#comparisons li a").first()
    await expect(first).toHaveAttribute("href", "/train/dependabot-nemotron-3-nano-4b")
    expect(await layoutProblems(page)).toEqual([])

    await first.scrollIntoViewIfNeeded()
    await (hasTouch ? first.tap() : first.click())
    await expect(page).toHaveURL("/train/dependabot-nemotron-3-nano-4b")
    await expect(page.locator("main h1")).toBeVisible()
    await expect(page.locator("#cases tbody tr")).toHaveCount(38)
    expect(await layoutProblems(page)).toEqual([])

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
