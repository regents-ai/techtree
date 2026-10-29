import type {Locator, Page} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, pairAgent, signIn, watchErrors} from "./support/visitor"

// Whether any script the page loaded carries the wallet library, whatever file it
// was bundled into. Every build of it names its own version as "viem@".
function watchWalletCode(page: Page): () => boolean {
  let seen = false
  page.on("response", async response => {
    if (response.request().resourceType() !== "script") return
    try {
      if ((await response.text()).includes("viem@")) seen = true
    } catch {}
  })
  return () => seen
}

const menu = (page: Page) => page.locator("#account-menu")

// Opened, and done dropping in, so what is measured is where it rests.
async function openMenu(page: Page, press: (target: Locator) => Promise<void> = target => target.click()) {
  await press(page.locator("#account-chip"))
  await expect(menu(page)).toBeVisible()
  await expect.poll(() => menu(page).evaluate(element => element.getAnimations().length)).toBe(0)
}

// The account menu the account's button opens on every page (TechtreeWeb.AccountMenuLive),
// at 1280, 390 and 320 wide: the person's name, their agents with Manage, Pair New
// Agent, Manage Account and Sign out; it hangs under its button inside the screen, the
// page still fits, and Escape closes it with focus back on the button. Techtree's
// header has no Credits balance, so the menu has no balance row at any width.
for (const width of [1280, 390, 320]) {
  test(`at ${width} wide, the account menu hangs under its button with the agents, Pair New Agent, Manage Account and Sign out`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    await page.goto("/docs", {waitUntil: "networkidle"})
    await openMenu(page, target => (hasTouch ? target.tap() : target.click()))

    await expect(menu(page)).toHaveAccessibleName(await page.locator("#account-chip .account-name").innerText())
    await expect(menu(page).locator("#shell-agents").getByRole("heading", {name: "Your agents"})).toBeVisible()
    await expect(menu(page).getByRole("link", {name: "Manage your agents"})).toHaveAttribute("href", "/account#account-agents")
    await expect(menu(page).getByRole("link", {name: "Pair New Agent"})).toHaveAttribute("href", "/account#account-pairing")
    await expect(menu(page).getByRole("link", {name: "Manage Account"})).toHaveAttribute("href", "/account")
    await expect(menu(page).getByRole("button", {name: "Sign out"})).toBeVisible()
    await expect(menu(page).locator(".rg-account-menu__balance")).toHaveCount(0)

    const chip = (await page.locator("#account-chip").boundingBox())!
    const box = (await menu(page).boundingBox())!
    expect(box.y).toBeGreaterThanOrEqual(chip.y + chip.height)
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(width)
    if (!hasTouch) expect(Math.abs(box.x + box.width - (chip.x + chip.width))).toBeLessThan(2)
    expect(await layoutProblems(page)).toEqual([])

    await menu(page).getByRole("link", {name: "Manage Account"}).focus()
    await page.keyboard.press("Escape")
    await expect(menu(page)).toBeHidden()
    await expect(page.locator("#account-chip")).toBeFocused()
    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}

test("a press outside the account menu closes it, and asked for less motion it appears at once", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.emulateMedia({reducedMotion: "reduce"})
  await page.goto("/results", {waitUntil: "networkidle"})
  await page.locator("#account-chip").focus()
  await page.keyboard.press("Enter")
  await expect(menu(page)).toBeVisible()
  expect(await menu(page).evaluate(element => element.getAnimations().length)).toBe(0)
  const box = (await menu(page).boundingBox())!
  await page.mouse.click(box.x / 2, box.y + box.height + 20)
  await expect(menu(page)).toBeHidden()
  expect(errors).toEqual([])
})

test("Manage Account in the account menu opens the Account page and the menu closes", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})
  await openMenu(page)
  await menu(page).getByRole("link", {name: "Manage Account"}).click()
  await expect(page).toHaveURL(/\/account$/)
  await expect(page.locator("#account-agents")).toBeVisible()
  await expect(menu(page)).toBeHidden()
  expect(errors).toEqual([])
})

test("Pair New Agent in the account menu lands on the Account page's pairing box, every press", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})
  await openMenu(page)
  await menu(page).getByRole("link", {name: "Pair New Agent"}).click()
  await expect(page).toHaveURL(/\/account#account-pairing$/)
  await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
  await expect(menu(page)).toBeHidden()
  const pairing = page.locator("#account-pairing")
  await expect(pairing).toBeInViewport()
  // The keyboard starts on the agent choice.
  await expect(pairing.getByRole("radio").first()).toBeFocused()

  // Pressed again from the same address after scrolling away, it moves there again.
  await page.evaluate(() => window.scrollTo({top: 0}))
  await expect(pairing.getByRole("heading", {name: "Pair New Agent"})).not.toBeInViewport()
  await openMenu(page)
  await menu(page).getByRole("link", {name: "Pair New Agent"}).click()
  await expect(menu(page)).toBeHidden()
  await expect(pairing).toBeInViewport()
  await expect(pairing.getByRole("radio").first()).toBeFocused()

  // The Agents list's own Pair New Agent leads to the same box.
  await page.evaluate(() => window.scrollTo({top: 0}))
  await page.locator("#account-agents").getByRole("link", {name: "Pair New Agent"}).click()
  await expect(pairing).toBeInViewport()
  await expect(pairing.getByRole("radio").first()).toBeFocused()
  expect(errors).toEqual([])
})

// On a phone the open Menu covers the page, and while it is open the page and its
// footer are out of reach until it closes (the account menu rollout, step 4).
// The account menu is a popover the browser lifts above the page, so on a short
// phone screen it ends inside the screen and scrolls to Sign out.
test("on a phone, the open Menu puts the page and footer out of reach, and the account menu reaches Sign out", async ({browser}) => {
  const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true})
  const outside = await keepOffline(context)
  await signIn(context)
  const page = await context.newPage()
  const errors = watchErrors(page)
  await page.goto("/account/wallets", {waitUntil: "networkidle"})
  const behind = page.locator(".techtree-frame > :not(.masthead)")
  const inert = () => behind.evaluateAll(parts => parts.map(part => (part as HTMLElement).inert))
  expect((await inert()).length).toBeGreaterThan(0)

  await page.getByRole("button", {name: "Menu"}).tap()
  const list = page.locator("#site-pages")
  await expect(list).toBeVisible()
  const listBox = (await list.boundingBox())!
  expect(await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.closest("#site-pages") !== null,
    [listBox.x + listBox.width / 2, listBox.y + listBox.height - 8] as const)).toBe(true)
  await expect.poll(async () => [...new Set(await inert())]).toEqual([true])
  await page.keyboard.press("Escape")
  await expect(list).toBeHidden()
  await expect.poll(async () => [...new Set(await inert())]).toEqual([false])

  for (const width of [390, 320]) {
    await page.setViewportSize({width, height: 360})
    await openMenu(page, target => target.tap())
    const box = (await menu(page).boundingBox())!
    expect(box.y + box.height).toBeLessThanOrEqual(360)
    const signOut = menu(page).getByRole("button", {name: "Sign out"})
    await signOut.scrollIntoViewIfNeeded()
    await expect(signOut).toBeInViewport()
    await page.keyboard.press("Escape")
    await expect(menu(page)).toBeHidden()
  }
  expect(errors).toEqual([])
  expect(outside).toEqual([])
  await context.close()
})

test("the wallet code loads on the account pages and nowhere else", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)

  let walletCode = watchWalletCode(page)
  await page.goto("/docs", {waitUntil: "networkidle"})
  expect(walletCode()).toBe(false)

  await page.goto("/", {waitUntil: "networkidle"})
  expect(walletCode()).toBe(false)

  await page.goto("/account", {waitUntil: "networkidle"})
  expect(walletCode()).toBe(true)
  expect(errors).toEqual([])
})

test("signed in, Buy Credits opens with Approve and Buy wired to the wallet", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.goto("/account", {waitUntil: "networkidle"})

  await page.locator("#shell-credits-button").click()
  await expect(page.locator("#shell-credits")).toBeVisible()
  await expect(page.locator("#credits-panel[phx-hook='OnchainSteps']")).toBeVisible()
  await expect(page.locator("[data-onchain-step='approve']")).toBeVisible()
  await expect(page.locator("[data-onchain-step='buy']")).toBeVisible()
  expect(await layoutProblems(page)).toEqual([])
  expect(errors).toEqual([])
})

// Regression: Purchase History in Buy Credits was 24 px tall on a phone (Sentinel).
test("on a phone, Buy Credits opens and everything in it fits a finger", async ({browser}) => {
  const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true})
  const outside = await keepOffline(context)
  await signIn(context)
  const page = await context.newPage()
  const errors = watchErrors(page)
  await page.goto("/account", {waitUntil: "networkidle"})
  await page.locator("#shell-credits-button").click()
  await expect(page.locator("#shell-credits")).toBeVisible()
  await expect(page.locator("[data-onchain-step='approve']")).toBeVisible()
  expect(await layoutProblems(page)).toEqual([])
  expect(errors).toEqual([])
  expect(outside).toEqual([])
  await context.close()
})

// A reconnecting page sends the pairing form back with no agent picked, and a
// submit can come before a choice. Neither may crash the Account page's pairing box
// (Sentinel, 23 Oct 2026, from Patchbay's error mail; ash-template 13379ab). Each
// agent then keeps its own code until it expires.
test("the pairing form with nothing chosen leaves the box as it is", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  const crashes: string[] = []
  page.on("websocket", socket =>
    socket.on("framereceived", frame => {
      if (String(frame.payload).includes('"phx_error"')) crashes.push(String(frame.payload).slice(0, 120))
    }),
  )
  await page.goto("/account", {waitUntil: "networkidle"})
  const form = page.locator("form#account-pairing-box")
  const message = page.locator("#account-pairing-box pre")
  await expect(form.getByRole("radio", {checked: true})).toHaveCount(0)

  await form.getByRole("radio").first().dispatchEvent("input")
  await form.evaluate(element => (element as HTMLFormElement).requestSubmit())

  // The box still answers: choosing an agent shows its code, and coming back to it
  // shows the same code.
  const choose = async (agent: string) => {
    const radio = form.getByRole("radio", {name: agent, exact: true})
    await radio.locator("xpath=ancestor::label").click()
    await expect(radio).toBeChecked()
  }
  await choose("Dots")
  await expect(message).toContainText(/Pairing code:\s*\S{12,}/)
  expect(crashes).toEqual([])

  const first = await message.innerText()
  await choose("Hermes")
  await expect(message).not.toHaveText(first)
  await choose("Dots")
  await expect(message).toHaveText(first)
  expect(errors).toEqual([])
})

// An agent's window renames it, as ash-template's does (agents.spec.ts), at desktop
// and phone widths, each with an agent of its own. A name with a hidden character
// is refused beside the field and the agent keeps its name; a name with an emoji
// joined by a zero-width joiner saves, and the window and the list show it.
for (const width of ["desktop", "phone"] as const) {
  test(`on a ${width}, an agent's window renames it`, async ({browser}) => {
    const hasTouch = width === "phone"
    const context = await browser.newContext(
      hasTouch ? {viewport: {width: 390, height: 844}, isMobile: true, hasTouch} : {},
    )
    const outside = await keepOffline(context)
    await signIn(context)
    const agent = pairAgent()
    const renamed = `Ada 👩‍💻 ${width}`
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())
    await page.goto("/account", {waitUntil: "networkidle"})
    await press(page.getByRole("button", {name: `See ${agent}’s actions`}))

    const agentWindow = page.getByRole("dialog", {name: agent})
    const name = agentWindow.getByRole("textbox", {name: "Name"})
    const save = agentWindow.getByRole("button", {name: "Save", exact: true})
    await expect(name).toHaveValue(agent)
    if (hasTouch)
      for (const target of [name, save])
        expect((await target.boundingBox())?.height).toBeGreaterThanOrEqual(44)

    await name.fill("Ada‮gnp.exe")
    await press(save)
    await expect(agentWindow.getByRole("alert")).toHaveText(
      "That name can’t be used. Use 1 to 80 characters with no hidden characters.",
    )
    await expect(name).toHaveAttribute("aria-invalid", "true")
    await expect(agentWindow).toBeVisible()

    await name.fill(renamed)
    await press(save)
    const renamedWindow = page.getByRole("dialog", {name: renamed})
    await expect(
      renamedWindow.getByText(`Saved. This agent is now called ${renamed} on every Regent site.`),
    ).toBeVisible()
    await expect(renamedWindow.getByRole("alert")).toHaveCount(0)
    await expect(page.getByRole("button", {name: `See ${renamed}’s actions`})).toBeAttached()
    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
