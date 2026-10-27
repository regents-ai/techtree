import {randomUUID} from "node:crypto"
import type {Locator} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {pairAgent, signIn, visitLines, watchErrors, type VisitLine} from "./support/visitor"

// A visit can be told again from its lines alone (TechtreeWeb.VisitLog). The
// signed-in visitor opens their account and renames an agent, and the lines the
// server wrote for that visit (config/runtime.exs) say so in order: the request,
// the page, the rename the site made and the press that asked for it. Every line
// carries the same visit and the same one-way code for the person, holds only the
// visit fields, and holds nothing the person wrote.

// The signed-in visitor (support/sign_in.exs).
const wallet = `0x${"b".repeat(40)}`

const fields = ["actor", "event", "request_id", "surface", "visit"]

const step = (line: VisitLine) => `${line.metadata.event!.name} ${line.metadata.event!.where}`

for (const width of ["desktop", "phone"] as const) {
  test(`on a ${width}, renaming an agent replays in order from the visit's lines`, async ({browser}) => {
    const hasTouch = width === "phone"
    const context = await browser.newContext(
      hasTouch ? {viewport: {width: 390, height: 844}, isMobile: true, hasTouch} : {},
    )
    const outside = await keepOffline(context)
    await signIn(context)
    const agent = pairAgent()
    const renamed = `Replay ${width} ${randomUUID().slice(0, 8)}`
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())

    await page.goto("/account")
    await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
    await press(page.getByRole("button", {name: `See ${agent}’s actions`}))
    const agentWindow = page.getByRole("dialog", {name: agent})
    await agentWindow.getByRole("textbox", {name: "Name"}).fill(renamed)
    await press(agentWindow.getByRole("button", {name: "Save", exact: true}))
    await expect(page.getByRole("button", {name: `See ${renamed}’s actions`})).toBeAttached()

    const visit = (await context.cookies()).find(cookie => cookie.name === "_visit")!.value
    await expect.poll(() => visitLines(visit).map(step)).toContain("press AgentsPanel:rename_agent")
    const told = visitLines(visit)
    const steps = told.map(step)

    expect(steps[0]).toBe("request /account")
    const order = [
      "request /account",
      "page /account",
      "action paired_agent.rename",
      "press AgentsPanel:rename_agent",
    ].map(wanted => steps.indexOf(wanted))
    expect(order.every(index => index >= 0)).toBe(true)
    expect([...order].sort((a, b) => a - b)).toEqual(order)
    expect(told.find(line => step(line) === "press AgentsPanel:rename_agent")!.metadata.event!.outcome).toBe("ok")

    const actors = [...new Set(told.map(line => line.metadata.actor))]
    expect(actors).toHaveLength(1)
    expect(actors[0]).toMatch(/^person:[0-9a-f]{16}$/)

    for (const line of told) {
      expect(Object.keys(line).sort()).toEqual(["message", "metadata", "severity", "time"])
      expect(Object.keys(line.metadata).every(key => fields.includes(key))).toBe(true)
      expect(
        Object.keys(line.metadata.event!).every(key => ["name", "where", "outcome", "ms", "client"].includes(key)),
      ).toBe(true)
      const text = JSON.stringify(line)
      for (const written of [renamed, agent, wallet, "did:privy"]) expect(text).not.toContain(written)
    }
    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
