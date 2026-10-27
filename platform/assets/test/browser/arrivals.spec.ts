import type {Locator} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {visitLines, watchErrors, type VisitLine} from "./support/visitor"

// Where a visit came from and where it stopped (TechtreeWeb.VisitLog): a
// stranger who follows a link from an AI answer writes one `arrival` line naming
// that source before its first page line, and a press on Sign in writes the
// journey's first step. Opening another page in the same visit adds no arrival,
// and the home page, which reads no address of its own, still writes its page line.

const told = (line: VisitLine) =>
  [line.metadata.event!.name, line.metadata.event!.where, line.metadata.event!.outcome].filter(Boolean).join(" ")

for (const width of ["desktop", "phone"] as const) {
  test(`on a ${width}, a visit from an AI answer arrives once, then presses Sign in`, async ({browser}) => {
    const hasTouch = width === "phone"
    const context = await browser.newContext(
      hasTouch ? {viewport: {width: 390, height: 844}, isMobile: true, hasTouch} : {},
    )
    const outside = await keepOffline(context)
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())

    await page.goto("/docs", {referer: "https://chatgpt.com/c/a-private-chat"})
    await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
    const visit = (await context.cookies()).find(cookie => cookie.name === "_visit")!.value

    await expect.poll(() => visitLines(visit).map(told)).toContain("page /docs")
    const first = visitLines(visit).map(told)
    expect(first.filter(line => line.startsWith("arrival"))).toEqual(["arrival /docs chatgpt"])
    expect(first.indexOf("arrival /docs chatgpt")).toBeLessThan(first.indexOf("page /docs"))

    await press(page.locator("#account-control [data-account-target='sign-in']"))
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pagehide")))
    await expect.poll(() => visitLines(visit).map(told)).toContain("step sign_in_opened")

    await page.goto("/", {referer: "https://www.google.com/"})
    await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
    await expect.poll(() => visitLines(visit).map(told)).toContain("page /")

    const all = visitLines(visit).map(told)
    expect(all.filter(line => line.startsWith("arrival"))).toHaveLength(1)
    expect(JSON.stringify(visitLines(visit))).not.toContain("a-private-chat")
    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}

// A browser that sends Global Privacy Control is counted like any other page
// view, but its visit writes no arrival and no step, on the page or in its reports.
test("a visit that asks not to be tracked writes no arrival or step", async ({browser}) => {
  const context = await browser.newContext()
  const outside = await keepOffline(context)
  const page = await context.newPage()
  const errors = watchErrors(page)

  await page.setExtraHTTPHeaders({"Sec-GPC": "1"})
  await page.goto("/docs", {referer: "https://chatgpt.com/c/a-private-chat"})
  await expect(page.locator("[data-phx-main].phx-connected")).toBeAttached()
  const visit = (await context.cookies()).find(cookie => cookie.name === "_visit")!.value

  await expect.poll(() => visitLines(visit).map(told)).toContain("page /docs")

  const reported = page.waitForResponse(response => new URL(response.url()).pathname === "/visit-log")
  await page.locator("#account-control [data-account-target='sign-in']").click()
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pagehide")))
  expect((await reported).status()).toBe(204)

  const all = visitLines(visit).map(told)
  expect(all.filter(line => line.startsWith("arrival") || line.startsWith("step"))).toEqual([])
  expect(errors).toEqual([])
  expect(outside).toEqual([])
  await context.close()
})
