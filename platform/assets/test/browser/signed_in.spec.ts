import {expect, test} from "@playwright/test"
import {layoutProblems, signIn, watchErrors} from "./support/visitor"

test("signed in, the name opens the side panel with sign out, the account and pairing", async ({context, page}) => {
  await signIn(context)
  const errors = watchErrors(page)
  await page.goto("/docs", {waitUntil: "networkidle"})

  await page.locator("#account-chip").click()
  await expect(page.locator("#shell-aside")).toBeVisible()
  await expect(page.locator("#shell-aside [data-account-target='sign-out']")).toBeVisible()
  await expect(page.locator("#shell-aside a[href='/account']")).toBeVisible()
  await expect(page.locator("#shell-pairing-box")).toBeAttached()

  await page.keyboard.press("Escape")
  await expect(page.locator("#shell-aside")).toBeHidden()
  await expect(page.locator("#account-chip")).toBeFocused()
  expect(errors).toEqual([])
})

test("signed in on a phone, the panel opens over the page without sideways scroll", async ({browser}) => {
  const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true})
  await signIn(context)
  const page = await context.newPage()
  await page.goto("/results", {waitUntil: "networkidle"})
  await page.locator("#account-chip").click()
  await expect(page.locator("#shell-aside")).toBeVisible()
  expect((await layoutProblems(page)).filter(p => p.startsWith("scrolls"))).toEqual([])
  await context.close()
})

test("the wallet code loads on the account pages and nowhere else", async ({context, page}) => {
  await signIn(context)
  const wallet: string[] = []
  page.on("request", request => {
    if (/onchain_steps/.test(request.url())) wallet.push(new URL(request.url()).pathname)
  })

  await page.goto("/docs", {waitUntil: "networkidle"})
  expect(wallet).toEqual([])

  await page.goto("/account", {waitUntil: "networkidle"})
  expect(wallet.length).toBeGreaterThan(0)
  await expect(page.locator("#credits-panel[phx-hook='OnchainSteps']")).toBeAttached()
  await expect(page.locator("[data-onchain-step='approve']")).toBeAttached()
  await expect(page.locator("[data-onchain-step='buy']")).toBeAttached()
})
