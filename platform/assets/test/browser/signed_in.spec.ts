import type {Page} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

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

test("signed in, the name opens the side panel with sign out, the account and pairing", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})

  await page.locator("#account-chip").click()
  await expect(page.locator("#shell-aside")).toBeVisible()
  await expect(page.locator("#shell-aside [data-account-target='sign-out']")).toBeVisible()
  await expect(page.locator("#shell-aside a[href='/account']")).toBeVisible()
  await expect(page.locator("#shell-pairing-box")).toBeAttached()
  expect(await layoutProblems(page)).toEqual([])

  await page.keyboard.press("Escape")
  await expect(page.locator("#shell-aside")).toBeHidden()
  await expect(page.locator("#account-chip")).toBeFocused()
  expect(errors).toEqual([])
})

test("signed in on a phone, the panel opens over the page and fits it", async ({browser}) => {
  const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true})
  const outside = await keepOffline(context)
  await signIn(context)
  const page = await context.newPage()
  const errors = watchErrors(page)
  await page.goto("/results", {waitUntil: "networkidle"})
  await page.locator("#account-chip").click()
  await expect(page.locator("#shell-aside")).toBeVisible()
  expect(await layoutProblems(page)).toEqual([])
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
// submit can come before a choice. Neither may crash the side panel (Sentinel,
// 23 Oct 2026, from Patchbay's error mail; ash-template 13379ab). Each agent then
// keeps its own code until it expires.
test("the pairing form with nothing chosen leaves the box as it is", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  const crashes: string[] = []
  page.on("websocket", socket =>
    socket.on("framereceived", frame => {
      if (String(frame.payload).includes('"phx_error"')) crashes.push(String(frame.payload).slice(0, 120))
    }),
  )
  await page.goto("/docs", {waitUntil: "networkidle"})
  await page.locator("#account-chip").click()
  const form = page.locator("form#shell-pairing-box")
  const message = page.locator("#shell-pairing-box pre")
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
