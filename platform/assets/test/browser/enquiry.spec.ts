import type {Locator} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

// The enquiry form in a service page's Contact section, signed out, at a desktop
// and a phone width. The page's own service is chosen. Send with the rest empty
// marks each empty field and puts the keyboard on the first; filled in, the form
// gives way to the note, which takes the keyboard. Signed in as one of the team,
// the enquiry is first under Enquiries on the team's page.
for (const [width, service, name] of [
  [1280, "evals", "Grace Hopper"],
  [390, "models", "Ada Lovelace"],
] as const) {
  test(`at ${width} wide, a visitor sends an enquiry from a service page and the team reads it`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())

    await page.goto(`/services/${service}`, {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()

    const form = page.locator("#enquiry-form")
    const fields = {
      name: form.getByRole("textbox", {name: "Name"}),
      email: form.getByRole("textbox", {name: "Work email"}),
      company: form.getByRole("textbox", {name: "Company"}),
      goal: form.getByRole("textbox", {name: "Goal"}),
    }
    const choice = form.getByRole("combobox", {name: "Service"})
    await expect(choice).toHaveValue(service)
    await expect(form.getByRole("textbox", {name: "Website"})).toHaveCount(0)
    await expect(page.locator("#contact").getByRole("link", {name: "Email build@regents.sh"})).toBeVisible()
    expect(await layoutProblems(page)).toEqual([])

    await press(form.getByRole("button", {name: "Send"}))
    for (const field of Object.values(fields)) await expect(field).toHaveAttribute("aria-invalid", "true")
    await expect(choice).not.toHaveAttribute("aria-invalid", "true")
    await expect(fields.name).toBeFocused()
    expect(await layoutProblems(page)).toEqual([])

    const goal = `We want our support agent to send refunds to the right team (${width}).`
    await fields.name.fill(name)
    await fields.email.fill("team@example.com")
    await fields.company.fill("Analytical Engines")
    await fields.goal.fill(goal)
    await press(form.getByRole("button", {name: "Send"}))

    const sent = page.locator("#enquiry-sent")
    await expect(sent).toBeVisible()
    await expect(sent).toBeFocused()
    await expect(form).toHaveCount(0)
    expect(await layoutProblems(page)).toEqual([])

    // The browser tests' person is one of the team (config/test.exs).
    await signIn(context)
    await page.goto("/admin/messages?show=enquiries", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()
    const newest = page.locator("#team-enquiries > li").first()
    await expect(newest.locator(".team-messages__body")).toHaveText(goal)
    await expect(newest).toContainText(name)
    await expect(newest.getByRole("link", {name: "team@example.com"})).toHaveAttribute("href", "mailto:team@example.com")
    expect(await layoutProblems(page)).toEqual([])

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
