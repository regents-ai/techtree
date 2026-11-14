import {createHash} from "node:crypto"
import {readFileSync, rmSync} from "node:fs"
import type {Locator} from "@playwright/test"
import {expect, keepOffline, test} from "./support/test"
import {deliverProjects, layoutProblems, lowContrast, signIn, watchErrors} from "./support/visitor"

// The account's Projects and the team's Projects tab, at a desktop and a phone
// width. The person finds the projects the team delivered; a project's page shows
// its verdict, both bars with their figures, every case with the worse ones
// marked, and its report, readable in light and dark; Download saves the exact
// package, whose sha256 is the Checksum shown. On the team's tab, an uploaded
// package is checked and previewed, its customer found by wallet in any case (a
// search that misses stays to be corrected), and Deliver puts it first in the
// person's Projects; Withdraw, once confirmed, takes a project away from them and
// says so beside the list.
for (const width of [1280, 390]) {
  test(`at ${width} wide, a person reads and downloads a delivered project, and the team delivers and withdraws`, async ({browser}) => {
    const hasTouch = width < 768
    const context = await browser.newContext({viewport: {width, height: 844}, isMobile: hasTouch, hasTouch})
    const outside = await keepOffline(context)
    await signIn(context)
    const delivered = deliverProjects()
    const page = await context.newPage()
    const errors = watchErrors(page)
    const press = (target: Locator) => (hasTouch ? target.tap() : target.click())

    await page.goto("/account/projects", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()
    for (const id of [delivered.improved, delivered.inconclusive, delivered.not_improved]) {
      await expect(page.locator(`#project-${id}`)).toBeVisible()
    }
    expect(await layoutProblems(page)).toEqual([])

    await press(page.locator(`#project-${delivered.inconclusive} a`))
    await expect(page).toHaveURL(`/account/projects/${delivered.inconclusive}`)
    await expect(page.locator("#project-title")).toHaveText("Invoice triage")
    await expect(page.locator("#project-before .project-meter__figure")).toContainText("10 of 18")
    await expect(page.locator("#project-after .project-meter__figure")).toContainText("12 of 18")
    await expect(page.locator("#project-cases tbody tr")).toHaveCount(6)
    await expect(page.locator('#project-cases tbody tr[data-change="worse"] th')).toHaveText("invoice-3")
    // The report's headings sit under the page's own, one level down.
    await expect(page.locator("#project-report h2")).toHaveText("Invoice triage")
    await expect(page.locator("#project-report script")).toHaveCount(0)
    expect(await layoutProblems(page)).toEqual([])
    expect(await lowContrast(page.locator("#project-page"))).toEqual([])
    await page.emulateMedia({colorScheme: "dark"})
    expect(await lowContrast(page.locator("#project-page"))).toEqual([])
    await page.emulateMedia({colorScheme: "light"})

    const [download] = await Promise.all([page.waitForEvent("download"), press(page.locator("#project-download"))])
    expect(download.suggestedFilename()).toBe(`invoice-triage-${delivered.inconclusive.slice(0, 8)}.tar.gz`)
    const sha256 = createHash("sha256").update(readFileSync(await download.path())).digest("hex")
    await expect(page.locator("#project-checksum")).toHaveText(sha256)

    // The team's tab: upload, preview, find the customer, deliver.
    await page.goto("/admin/messages?show=projects", {waitUntil: "networkidle"})
    await expect(page.locator(".phx-connected").first()).toBeAttached()
    const deliver = page.locator("#team-deliver")
    await expect(page.locator("#team-deliver-button")).toBeDisabled()
    // The package is read, then its file removed, so no run leaves one behind.
    const upload = readFileSync(delivered.upload)
    rmSync(delivered.upload)
    await deliver
      .getByLabel("Package")
      .setInputFiles({name: "ticket-tagging.tar.gz", mimeType: "application/gzip", buffer: upload})
    await expect(page.locator("#team-package-preview")).toContainText(delivered.upload_title)
    // A search that finds no one stays in its box to be corrected.
    const customer = deliver.getByRole("textbox", {name: "Customer"})
    await customer.fill("did:privy:nobody")
    await press(deliver.getByRole("button", {name: "Find"}))
    await expect(customer).toHaveAttribute("aria-invalid", "true")
    await expect(customer).toHaveValue("did:privy:nobody")
    await expect(page.locator("#team-deliver-button")).toBeDisabled()
    await customer.fill(`0x${"B".repeat(40)}`)
    await press(deliver.getByRole("button", {name: "Find"}))
    await expect(page.locator("#team-customer-found")).toBeVisible()
    expect(await layoutProblems(page)).toEqual([])
    await press(page.locator("#team-deliver-button"))
    await expect(page.locator("#team-deliver-outcome")).toContainText(delivered.upload_title)
    await expect(page.locator("#team-projects > li").first()).toContainText(delivered.upload_title)

    // Withdraw asks first, then the project shows as withdrawn, with nothing left to press.
    const item = page.locator(`#team-project-${delivered.not_improved}`)
    const ask = page.locator("#rg-confirm")
    await press(item.getByRole("button", {name: "Withdraw"}))
    await expect(ask).toBeVisible()
    await press(ask.getByRole("button", {name: "Withdraw"}))
    await expect(ask).toBeHidden()
    await expect(page.locator("#team-withdraw-outcome")).toContainText("Contract clause review")
    await expect(page.locator("#team-deliver-outcome")).toHaveCount(0)
    await expect(item.locator(".team-projects__actions")).toHaveCount(0)
    expect(await layoutProblems(page)).toEqual([])

    await page.goto("/account/projects", {waitUntil: "networkidle"})
    await expect(page.locator("#projects-list > li").first()).toContainText(delivered.upload_title)
    await expect(page.locator(`#project-${delivered.not_improved}`)).toHaveCount(0)
    await expect(page.locator(`#project-${delivered.improved}`)).toBeVisible()

    expect(errors).toEqual([])
    expect(outside).toEqual([])
    await context.close()
  })
}
