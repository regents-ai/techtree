import type {Locator, Page} from "@playwright/test"
import {expect, test} from "./support/test"
import {signIn, watchErrors} from "./support/visitor"

// Pairing an agent, the way a person does it, as ash-template's pairing.spec.ts does:
// Pair New Agent on the Agents page opens the pairing window, where they choose their
// agent from the dropdown and copy its message.
const pairingWindow = (page: Page) => page.locator("#shell-pairing")
const box = (page: Page) => page.locator("form#shell-pairing-box")
const message = (page: Page) => page.locator("#shell-pairing-box pre")
const dropdown = (page: Page) => box(page).locator("details")

const pairButton = (page: Page) =>
  page.locator("#account-agents").getByRole("button", {name: "Pair New Agent"})

async function agentsPage(page: Page) {
  await page.goto("/account/agents", {waitUntil: "networkidle"})
  await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
  // The window belongs to the header's account LiveView, which connects on its own.
  await expect(page.locator(".masthead__account.phx-connected")).toBeAttached()
}

async function openWindow(page: Page) {
  await pairButton(page).click()
  await expect(pairingWindow(page)).toBeVisible()
  await expect(pairingWindow(page)).toHaveAttribute("data-settled", "")
}

// A person opens the dropdown, unless it is already open, and presses the agent's
// name; the radio's label carries it. The choice closes the list, so the radio is
// looked for hidden too when its check is read.
async function choose(page: Page, agent: string) {
  const radio = box(page).getByRole("radio", {name: agent, exact: true, includeHidden: true})
  if (!(await dropdown(page).evaluate(details => (details as HTMLDetailsElement).open))) {
    await dropdown(page).locator("summary").click()
  }
  await radio.locator("xpath=ancestor::label").click()
  await expect(radio).toBeChecked()
  await expect(dropdown(page).locator("summary")).toContainText(agent)
}

const height = (locator: Locator) => locator.evaluate(element => element.getBoundingClientRect().height)
const top = (locator: Locator) => locator.evaluate(element => element.getBoundingClientRect().top)
const picture = (page: Page) => box(page).locator(".rg-account__stage")
const agents = (page: Page) => dropdown(page).locator("[data-panel='list']")

// The page's clock, held still so a move in the list can be pressed half way.
async function holdClock(page: Page) {
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000))
}

// Keyfleet, 27 Oct 2026: pressed a second time, Pair New Agent did nothing a person
// could see. Every press opens the window.
test("Pair New Agent on the Agents page opens the pairing window, every press", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await agentsPage(page)
  await openWindow(page)
  await pairingWindow(page).getByRole("button", {name: "Close"}).click()
  await expect(pairingWindow(page)).toBeHidden()
  await expect(pairButton(page)).toBeFocused()

  // With the agents listed, the first Escape closes the list and the next the window.
  await openWindow(page)
  await page.keyboard.press("Escape")
  await expect(dropdown(page)).not.toHaveAttribute("open", "")
  await expect(pairingWindow(page)).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(pairingWindow(page)).toBeHidden()
  expect(errors).toEqual([])
})

// The window opens on the list of agents; a choice closes the list, and the
// keyboard goes back to the dropdown.
test("the window opens on the agents, and a choice closes the list", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await agentsPage(page)
  await openWindow(page)
  await expect(dropdown(page)).toHaveAttribute("open", "")
  await expect(dropdown(page).locator("summary")).toBeFocused()

  await choose(page, "Dots")
  await expect(dropdown(page)).not.toHaveAttribute("open", "")
  await expect(message(page)).toContainText(/Pairing code:\s*\S{12,}/)
  expect(errors).toEqual([])
})

// Choosing never changes the window's height (founder, 2026-10-07).
test("the window keeps one height whatever is chosen", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await agentsPage(page)
  await openWindow(page)
  const before = await height(box(page))
  await choose(page, "Dots")
  await expect(message(page)).toContainText(/Pairing code/)
  expect(await height(box(page))).toBe(before)
  await choose(page, "Hermes")
  await expect(message(page)).toContainText(/Pairing code/)
  expect(await height(box(page))).toBe(before)
  expect(errors).toEqual([])
})

// Sean, 11 Nov 2026: "the image area can be much smaller". The picture sits in a
// band at most half the height of the old 16:9 box, sharp and centred, and choosing
// another agent moves nothing under it.
test("the agent's picture sits in a low band, and choosing moves nothing under it", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await agentsPage(page)
  await openWindow(page)
  const steps = box(page).locator("ol")
  const waiting = await top(steps)

  await choose(page, "Dots")
  await expect(message(page)).toContainText(/Pairing code/)
  const band = await picture(page).evaluate(stage => {
    const outer = stage.getBoundingClientRect()
    const image = stage.querySelector("img")!
    const inner = image.getBoundingClientRect()
    return {
      width: outer.width,
      height: outer.height,
      offCentre: Math.max(
        Math.abs(inner.left + inner.width / 2 - (outer.left + outer.width / 2)),
        Math.abs(inner.top + inner.height / 2 - (outer.top + outer.height / 2)),
      ),
      inside: inner.top >= outer.top && inner.bottom <= outer.bottom,
      sharp: image.naturalWidth >= inner.width * devicePixelRatio,
    }
  })
  expect(band.height).toBeLessThanOrEqual((band.width * 9) / 16 / 2)
  expect(band).toMatchObject({inside: true, sharp: true})
  expect(band.offCentre).toBeLessThan(1)
  expect(await top(steps)).toBe(waiting)

  await choose(page, "Hermes")
  await expect(message(page)).toContainText(/Pairing code/)
  expect(await height(picture(page))).toBe(band.height)
  expect(await top(steps)).toBe(waiting)
  expect(errors).toEqual([])
})

// The list drops in and leaves with a short move, and a press during it always
// counts: on an agent as it comes in, and on what is under the list as it leaves.
// The page's clock is held, so the press lands half way through each move.
test("a press during the list's move always counts", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.clock.install()
  await agentsPage(page)
  await openWindow(page)
  await choose(page, "Dots")
  await expect(message(page)).toContainText(/Pairing code/)
  const first = await message(page).innerText()

  // Held 30 ms into the entrance, an agent still on its way in takes the press.
  await holdClock(page)
  await dropdown(page).locator("summary").click()
  await page.clock.runFor(30)
  const hermes = box(page).locator("label", {hasText: "Hermes"})
  await expect(dropdown(page)).not.toHaveAttribute("data-settled")
  expect(await hermes.evaluate(label => Number(getComputedStyle(label).opacity))).toBeLessThan(1)
  await hermes.click({force: true})
  await expect(box(page).getByRole("radio", {name: "Hermes", includeHidden: true})).toBeChecked()
  await expect(message(page)).not.toHaveText(first)
  const second = await message(page).innerText()

  // Held 30 ms into its exit, the list still covers the new-code button, which
  // takes the press.
  await expect(agents(page)).toHaveAttribute("data-leaving", "")
  await page.clock.runFor(30)
  await expect(agents(page)).toBeVisible()
  expect(await agents(page).evaluate(list => Number(getComputedStyle(list).opacity))).toBeLessThan(1)
  await box(page).getByRole("button", {name: "Make a new code"}).click()
  await expect(message(page)).not.toHaveText(second)
  await expect(message(page)).toContainText(/Pairing code:\s*\S{12,}/)

  // Each move ends within 200 ms and leaves nothing behind.
  await page.clock.runFor(170)
  await expect(agents(page)).not.toHaveAttribute("data-leaving")
  await expect(agents(page)).toBeHidden()
  await dropdown(page).locator("summary").click()
  await page.clock.runFor(200)
  await expect(dropdown(page)).toHaveAttribute("data-settled", "")
  await expect(agents(page)).not.toHaveAttribute("style")
  expect(errors).toEqual([])
})

// With reduced motion asked for, the list opens and closes at once.
test("with reduced motion the list opens and closes at once", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.emulateMedia({reducedMotion: "reduce"})
  await page.clock.install()
  await agentsPage(page)
  await openWindow(page)
  await choose(page, "Dots")
  await expect(message(page)).toContainText(/Pairing code/)

  await holdClock(page)
  await dropdown(page).locator("summary").click()
  await expect(dropdown(page)).toHaveAttribute("data-settled", "")
  await expect(box(page).locator("label", {hasText: "Hermes"})).toHaveCSS("opacity", "1")
  await box(page).locator("label", {hasText: "Hermes"}).click()
  await expect(dropdown(page)).not.toHaveAttribute("open", "")
  await expect(agents(page)).not.toHaveAttribute("data-leaving")
  await expect(agents(page)).toBeHidden()
  expect(errors).toEqual([])
})

// A reconnecting page sends the pairing form back with no agent picked, and a
// submit can come before a choice. Neither may crash the pairing box (Sentinel,
// 23 Oct 2026, from Patchbay's error mail; ash-template 13379ab). Each agent then
// keeps its own code until a new one is asked for.
test("the pairing form with nothing chosen leaves the box as it is", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  const crashes: string[] = []
  page.on("websocket", socket =>
    socket.on("framereceived", frame => {
      if (String(frame.payload).includes('"phx_error"')) crashes.push(String(frame.payload).slice(0, 120))
    }),
  )
  await agentsPage(page)
  await openWindow(page)
  await expect(box(page).getByRole("radio", {checked: true})).toHaveCount(0)

  await box(page).getByRole("radio").first().dispatchEvent("input")
  await box(page).evaluate(element => (element as HTMLFormElement).requestSubmit())

  // The box still answers: choosing an agent shows its code, and coming back to it
  // shows the same code.
  await choose(page, "Dots")
  await expect(message(page)).toContainText(/Pairing code:\s*\S{12,}/)
  expect(crashes).toEqual([])

  const first = await message(page).innerText()
  await choose(page, "Hermes")
  await expect(message(page)).not.toHaveText(first)
  await choose(page, "Dots")
  await expect(message(page)).toHaveText(first)

  await box(page).getByRole("button", {name: "Make a new code"}).click()
  await expect(message(page)).not.toHaveText(first)
  await expect(message(page)).toContainText(/Pairing code:\s*\S{12,}/)
  expect(errors).toEqual([])
})
