import type {Page} from "@playwright/test"
import {expect, test} from "./support/test"
import {signIn, watchErrors} from "./support/visitor"

// The Public Display Name on the Account tab saves with the page's own sign-in,
// its session cookie and forms token (hooks/public_name.ts). Each sign-in starts
// with no name (support/sign_in.exs).

const saved = (page: Page) => page.waitForResponse(response =>
  new URL(response.url()).pathname === "/api/v1/profile" && response.request().method() === "PATCH")

async function openAccount(page: Page) {
  await page.goto("/account", {waitUntil: "networkidle"})
  const panel = page.locator("#account-public-name")
  const name = panel.getByRole("textbox", {name: "Public Display Name"})
  const save = panel.getByRole("button", {name: "Save"})
  await expect(name).toBeVisible()
  // Where Save sits in the panel, and how tall the panel is, wherever the page scrolls.
  const place = () => Promise.all([panel.boundingBox(), save.boundingBox()])
    .then(([p, s]) => ({x: s!.x - p!.x, y: s!.y - p!.y, height: p!.height}))
  // Marks this page, so a reload would show.
  await page.evaluate(() => document.documentElement.setAttribute("data-same-page", ""))
  return {panel, name, save, place, header: page.locator("#account-chip .account-name")}
}

for (const width of [1280, 390]) {
  test(`at ${width} wide, Save keeps the name and the header shows it without a reload`, async ({page}) => {
    await page.setViewportSize({width, height: 844})
    await signIn(page.context())
    const errors = watchErrors(page)
    const {panel, name, save, place, header} = await openAccount(page)
    const before = await place()

    await name.fill("Ada Lovelace")
    const change = saved(page)
    await save.click()
    expect((await change).status()).toBe(200)
    await expect(panel.locator("form")).not.toHaveAttribute("aria-busy")
    await expect(panel.getByRole("status")).not.toBeEmpty()
    await expect(name).toHaveValue("Ada Lovelace")
    await expect(header).toHaveText("Ada Lovelace")
    await expect(page.locator("html")).toHaveAttribute("data-same-page")
    // The note sits beside Save without moving it.
    expect(await place()).toEqual(before)
    expect(errors).toEqual([])
  })
}

test("a name that can't be used is refused beside Save, and nothing changes", async ({page}) => {
  await signIn(page.context())
  const errors = watchErrors(page)
  const {panel, name, save, header} = await openAccount(page)
  const shown = await header.innerText()

  // A right-to-left mark is one of the hidden characters a name may not hold.
  await name.fill("Ada‮Lovelace")
  const change = saved(page)
  await save.click()
  expect((await change).status()).toBe(422)
  await expect(panel.locator("form")).not.toHaveAttribute("aria-busy")
  await expect(panel.getByRole("status")).not.toBeEmpty()
  // The name stays in the box to be put right.
  await expect(name).toHaveValue("Ada‮Lovelace")
  await expect(header).toHaveText(shown)
  await expect(page.locator("html")).toHaveAttribute("data-same-page")
  // The browser reports the refused request itself; nothing else may fail.
  expect(errors.filter(error => !error.includes("status of 422"))).toEqual([])
})
