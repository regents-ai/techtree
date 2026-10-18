import {expect, test} from "@playwright/test"

const shown = ".hero-outcome__phrase[data-shown]"

test("the headline's ending turns while it is on screen", async ({page}) => {
  await page.goto("/", {waitUntil: "networkidle"})
  const first = await page.locator(shown).textContent()
  await expect.poll(() => page.locator(shown).textContent(), {timeout: 6_000}).not.toBe(first)
  await expect(page.locator(shown)).toHaveCount(1)
  // A finished turn leaves no inline style behind.
  await page.waitForTimeout(400)
  await expect(page.locator("#hero-outcome [style]")).toHaveCount(0)
})

test("with less motion asked for, the headline keeps its first ending", async ({browser}) => {
  const context = await browser.newContext({reducedMotion: "reduce"})
  const page = await context.newPage()
  await page.goto("/", {waitUntil: "networkidle"})
  const first = await page.locator(shown).textContent()
  await page.waitForTimeout(4_000)
  await expect(page.locator(shown)).toHaveText(first as string)
  await context.close()
})
