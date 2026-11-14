import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The signed-in Watchdog page at a desktop and a phone width: a site that can't
// be read as one, and one already on the list, are refused under the Site field
// itself and nothing is added; a real one is added and takes its own address
// form, which refuses an address on another site under its own field. The last
// action's notice floats on New site's edge: it shows when a site is added,
// moving nothing, and goes when a typed site is refused. Remove site asks first
// in the site's own window, never the browser's box.
for (const width of [1280, 390]) {
  test(`signed in at ${width} wide, Watchdog refuses a bad site or address under its own field and asks before removing a site`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    const browserBoxes: string[] = []
    page.on("dialog", dialog => {
      browserBoxes.push(dialog.message())
      void dialog.dismiss()
    })
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
    const notice = page.locator(".watchdog-add > [role=status]")
    // Where New site's title sits, and the room under its last line: the notice
    // floats, so showing it changes neither.
    const newSite = () => page.locator(".watchdog-add").evaluate(panel => {
      const last = panel.querySelector(":scope > p")!.getBoundingClientRect()
      return [panel.querySelector("h2")!.getBoundingClientRect().top + scrollY, panel.getBoundingClientRect().bottom - last.bottom]
    })

    await origin.fill("not a site!")
    await add.click()
    await expect(refused).toHaveCount(1)
    await expect(origin).toHaveAttribute("aria-invalid", "true")
    await expect(origin).toHaveAttribute("aria-describedby", /watchdog-origin-errors/)
    await expect(sites).toHaveCount(before)
    await expect(notice).toHaveCount(0)
    expect(await layoutProblems(page)).toEqual([])

    const at = await newSite()
    await origin.fill(site)
    await add.click()
    await expect(sites).toHaveCount(before + 1)
    await expect(refused).toHaveCount(0)
    await expect(origin).toHaveAttribute("aria-invalid", "false")
    await expect(notice).toBeVisible()
    expect(await newSite()).toEqual(at)

    await origin.fill(site)
    await add.click()
    await expect(refused).toHaveCount(1)
    await expect(sites).toHaveCount(before + 1)
    await expect(notice).toBeHidden()

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

    // Cancel keeps the site and hands the keyboard back; the going-ahead button
    // removes it, with its address.
    const remove = mine.getByRole("button", {name: "Remove site"})
    const ask = page.locator("#rg-confirm")
    await remove.click()
    await expect(ask).toBeVisible()
    await expect(ask.locator("#rg-confirm-question")).not.toBeEmpty()
    expect(await ask.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    expect(await layoutProblems(page)).toEqual([])
    await ask.getByRole("button", {name: "Cancel"}).click()
    await expect(ask).toBeHidden()
    await expect(remove).toBeFocused()
    await expect(sites).toHaveCount(before + 1)

    await remove.click()
    await ask.getByRole("button", {name: "Remove", exact: true}).click()
    await expect(ask).toBeHidden()
    await expect(sites).toHaveCount(before)
    await expect(mine).toHaveCount(0)
    expect(browserBoxes).toEqual([])

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
