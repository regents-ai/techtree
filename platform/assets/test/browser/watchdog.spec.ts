import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The signed-in Watchdog page at a desktop and a phone width: a site that can't
// be read as one, and one already on the list, are refused under the Site field
// itself and nothing is added; a real one is added and takes its own address
// form, which refuses an address on another site under its own field.
for (const width of [1280, 390]) {
  test(`signed in at ${width} wide, Watchdog refuses a bad site or address under its own field`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    const site = `walk-${width}.example`

    await page.goto("/watchdog", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()

    const origin = page.locator("#watchdog-origin")
    const refused = page.locator("#watchdog-origin-errors p")
    const add = page.getByRole("button", {name: "Add site"})
    // The two widths share one signed-in person, so the list may already hold a site.
    const sites = page.locator(".watchdog-sites > li")
    const before = await sites.count()
    const mine = sites.filter({hasText: site})

    await origin.fill("not a site!")
    await add.click()
    await expect(refused).toHaveCount(1)
    await expect(origin).toHaveAttribute("aria-invalid", "true")
    await expect(origin).toHaveAttribute("aria-describedby", /watchdog-origin-errors/)
    await expect(sites).toHaveCount(before)
    expect(await layoutProblems(page)).toEqual([])

    await origin.fill(site)
    await add.click()
    await expect(sites).toHaveCount(before + 1)
    await expect(refused).toHaveCount(0)
    await expect(origin).toHaveAttribute("aria-invalid", "false")

    await origin.fill(site)
    await add.click()
    await expect(refused).toHaveCount(1)
    await expect(sites).toHaveCount(before + 1)

    const address = mine.locator("input[name='url']")
    await address.fill("https://elsewhere.example/pay")
    await mine.getByRole("button", {name: "Add address"}).click()
    await expect(mine.locator(".rg-field-errors p")).toHaveCount(1)
    await expect(address).toHaveAttribute("aria-invalid", "true")
    await expect(refused).toHaveCount(0)
    expect(await layoutProblems(page)).toEqual([])

    await address.fill(`https://${site}/pay`)
    await mine.getByRole("button", {name: "Add address"}).click()
    await expect(mine.locator(".rg-field-errors p")).toHaveCount(0)
    await expect(mine.getByText(`https://${site}/pay`)).toBeVisible()

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
