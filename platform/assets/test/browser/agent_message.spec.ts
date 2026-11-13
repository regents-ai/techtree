import type {Locator} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The Agent Message button on the Security page at a desktop and a phone width.
// It opens its window: each of the three texts fits the screen and copies exactly
// what it shows, and Escape closes it. A signed-in person leaves a message from
// its form and sees the receipt, after an empty message is refused when the field
// is left, and the team's page then shows it first. A visitor sees the texts and
// no form, and the team's page is not found for them.
for (const width of [1280, 390]) {
  test(`at ${width} wide, an agent's texts copy and a signed-in person leaves a message`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({
      viewport: {width, height: 844},
      isMobile: hasTouch,
      hasTouch,
      permissions: ["clipboard-read", "clipboard-write"],
    })
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())

    await page.goto("/services/security", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()

    const open = page.getByRole("button", {name: "Agent Message"})
    const dialog = page.getByRole("dialog", {name: "Agent Message"})
    await expect(dialog).toBeHidden()
    expect(await layoutProblems(page)).toEqual([])
    await press(open)
    await expect(dialog).toBeVisible()

    const texts = dialog.locator(".agent-message__texts > li")
    await expect(texts).toHaveCount(3)
    for (const text of await texts.all())
      expect(await text.locator("pre").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    expect(await layoutProblems(page)).toEqual([])

    const cli = texts.first()
    // By its id: once pressed, the button's name is its answer, not "Copy".
    const copy = cli.locator("#security-message-copy-cli")
    await expect(copy).toHaveAccessibleName("Copy")
    await press(copy)
    await expect(copy).toHaveAttribute("data-copy-state", "copied")
    const copied = await page.evaluate(() => navigator.clipboard.readText())
    expect(copied).toBe(await cli.locator("code").textContent())
    expect(copied).toContain("regents techtree messages leave watchdog")

    await page.keyboard.press("Escape")
    await expect(dialog).toBeHidden()
    await press(open)
    await expect(dialog).toBeVisible()

    const form = dialog.locator("#security-message-person-form")
    const body = form.getByRole("textbox", {name: "Message", exact: true})
    const replyTo = form.getByRole("textbox", {name: "Reply to"})
    await body.fill("x")
    await body.fill("")
    await replyTo.focus()
    await expect(body).toHaveAttribute("aria-invalid", "true")
    await expect(dialog).toBeVisible()

    await body.fill(`We run three sites and want them watched (${width}).`)
    await replyTo.fill("walk@example.com")
    await press(form.getByRole("button", {name: "Send"}))
    const receipt = dialog.locator("#security-message-person-receipt")
    await expect(receipt).toBeVisible()
    await expect(receipt.locator("code")).toHaveText(/^[0-9a-f-]{36}$/)
    await expect(body).toHaveValue("")
    await expect(dialog).toBeVisible()
    expect(await layoutProblems(page)).toEqual([])

    await press(dialog.getByRole("button", {name: "Close"}))
    await expect(dialog).toBeHidden()

    // The browser tests' person is one of the team (config/test.exs).
    await page.goto("/admin/messages", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()
    const newest = page.locator("#team-messages > li").first()
    await expect(newest.locator(".team-messages__body")).toHaveText(`We run three sites and want them watched (${width}).`)
    await expect(newest.locator("code")).toHaveText("watchdog")
    await expect(newest).toContainText("walk@example.com")
    expect(await layoutProblems(page)).toEqual([])

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}

test("a visitor opens the window and sees the three texts and no form", async ({page}) => {
  const errors = watchErrors(page)
  await page.goto("/services/security", {waitUntil: "networkidle"})
  await expect(page.locator(".phx-connected").first()).toBeAttached()

  await page.getByRole("button", {name: "Agent Message"}).click()
  const dialog = page.getByRole("dialog", {name: "Agent Message"})
  await expect(dialog).toBeVisible()
  await expect(dialog.locator(".agent-message__texts > li")).toHaveCount(3)
  await expect(dialog.locator("form")).toHaveCount(0)

  // A press beside the window closes it.
  await page.mouse.click(5, 5)
  await expect(dialog).toBeHidden()
  expect(errors).toEqual([])

  expect((await page.goto("/admin/messages"))?.status()).toBe(404)
})
