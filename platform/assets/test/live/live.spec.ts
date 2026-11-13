import {readFileSync} from "node:fs"
import {expect, test} from "@playwright/test"
import {publicPages} from "../browser/support/pages"
import {layoutProblems, watchErrors} from "../browser/support/visitor"

// The live site, signed out, read as a visitor's and an agent's browser read it
// (skills/regent-workflow, "Live checks"): it runs the commit this checkout is at,
// every public page opens and fits the screen, every moved address sends a visitor
// on for good, the documents answer in their own type, the home page offers exactly
// this checkout's browser tools and every public read that takes no input answers,
// the Agent Message window opens, and the theme switch turns the theme. Nothing is
// written: no form is sent and no signed tool is called.
const checkout = process.env.CHECKOUT_COMMIT
if (!checkout) throw new Error("Set CHECKOUT_COMMIT to the commit the site should run. Run it through make live-check.")

type Entry = {
  name: string
  authentication: string
  annotations: {readOnlyHint?: boolean}
  input_schema: {required: string[]}
  interfaces: Record<string, unknown>
}
const manifest: {tools: Entry[]} = JSON.parse(
  readFileSync(new URL("../../../priv/tool_manifest.json", import.meta.url), "utf8"),
)
const offered = manifest.tools.filter(tool => "webmcp" in tool.interfaces)
// The reads anyone may make with nothing filled in.
const reads = offered.filter(
  tool => tool.authentication === "public" && tool.annotations.readOnlyHint && !tool.input_schema.required.length,
)

const documents = [
  ["/capabilities.json", "application/json"],
  ["/openapi.json", "application/json"],
  ["/api/v1/health", "application/json"],
  ["/train.json", "application/json"],
  ["/wallet-bench.json", "application/json"],
  ["/skill.md", "text/markdown"],
  ["/agents.md", "text/markdown"],
  ["/llms.txt", "text/plain"],
  ["/sitemap.xml", "xml"],
]

// The addresses that moved, each to the page that took its place.
const moved = [
  ["/start", "/docs/run-locally"],
  ["/verify", "/docs/verify"],
  ["/docs/method", "/docs/verify"],
  ["/repo2rlenv", "/services/environments"],
  ["/train", "/services/models"],
  ["/services/verify", "/services/evals"],
  ["/services/verify/sample-report", "/services/evals"],
  ["/services/cyber-assist", "/services/security"],
  ["/services/cyber-assist/sample-report", "/services/security/sample-report"],
  ["/services/watchdog", "/services/security"],
]

// A stand-in document.modelContext holds what the page registers, as
// test/browser/page_tools.spec.ts does locally: Chromium here has no WebMCP.
const withPageTools = `
  const held = new Map()
  Object.defineProperty(document, "modelContext", {value: {
    registerTool: async (tool, {signal}) => {
      held.set(tool.name, tool)
      signal.addEventListener("abort", () => held.delete(tool.name))
    },
    getTools: async () => [...held.values()],
  }})
  window.pageTools = held
`
type Held = {pageTools: Map<string, {execute: (input: unknown, client: unknown) => Promise<{ok: boolean; status?: number}>}>}

test("the site answers and runs this checkout's commit", async ({page}) => {
  const health = await page.goto("/healthz")
  expect(health?.status()).toBe(200)
  expect((await health!.text()).trim()).toBe("ok")
  // Every migration the live release carries is applied.
  expect(await (await page.request.get("/api/v1/health")).json()).toEqual({status: "ok", migrations_applied: true})

  const capabilities = await page.goto("/capabilities.json")
  const {build} = (await capabilities!.json()) as {build: {commit: string}}
  expect(build.commit, "Run the live check from a checkout of the live commit.").toBe(checkout)
})

for (const [path, type] of documents) {
  test(`${path} answers as ${type}`, async ({page}) => {
    const answer = await page.request.get(path)
    expect(answer.status()).toBe(200)
    expect(answer.headers()["content-type"]).toContain(type)
  })
}

for (const path of publicPages) {
  test(`${path} opens and fits the screen`, async ({page}) => {
    const errors = watchErrors(page)
    const answer = await page.goto(path, {waitUntil: "networkidle"})
    expect(answer?.status()).toBe(200)
    await expect(page.locator("main")).toBeVisible()
    if (await page.locator("[data-phx-main]").count()) await expect(page.locator(".phx-connected").first()).toBeAttached()
    expect(await layoutProblems(page)).toEqual([])
    expect(errors).toEqual([])
  })
}

test("every moved address sends a visitor on for good", async ({page}) => {
  for (const [from, to] of moved) {
    const answer = await page.request.get(from, {maxRedirects: 0})
    expect(answer.status(), from).toBe(301)
    expect(answer.headers()["location"], from).toBe(to)
  }
})

test("the first comparison opens from Results", async ({page}) => {
  const errors = watchErrors(page)
  await page.goto("/results", {waitUntil: "networkidle"})
  await page.locator("#comparisons a[href^='/train/']").first().click()
  await expect(page).toHaveURL(/\/train\/[a-z0-9-]+$/)
  await expect(page.locator("main h1")).toBeVisible()
  expect(await layoutProblems(page)).toEqual([])
  expect(errors).toEqual([])
})

test("addresses with nothing behind them say so", async ({page}) => {
  // The team's page is not found for a visitor; a page has one address, with no
  // slash at its end; the hosted MCP address takes POST only.
  for (const [path, status] of [["/admin/messages", 404], ["/about/", 404], ["/climbs/does-not-exist", 404], ["/mcp", 405]] as const)
    expect((await page.request.get(path)).status(), path).toBe(status)
})

test("the Agent Message window opens with its three texts and no form", async ({page}, info) => {
  const errors = watchErrors(page)
  await page.goto("/services/security", {waitUntil: "networkidle"})
  await expect(page.locator(".phx-connected").first()).toBeAttached()
  const open = page.getByRole("button", {name: "Agent Message"})
  await (info.project.name === "phone" ? open.tap() : open.click())

  const dialog = page.getByRole("dialog", {name: "Agent Message"})
  await expect(dialog).toBeVisible()
  await expect(dialog.locator(".agent-message__texts > li")).toHaveCount(3)
  await expect(dialog.getByRole("textbox")).toHaveCount(0)
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  expect(await layoutProblems(page)).toEqual([])
  expect(errors).toEqual([])
})

// The header's theme switch, signed out, from a device set to light and from one set
// to dark: a press turns the theme once, on the home page and on a second page, and
// the choice holds over a reload. The choice is a cookie in the check's own browser;
// the site keeps nothing.
for (const device of ["light", "dark"] as const) {
  test.describe(`on a ${device}-set device`, () => {
    test.use({colorScheme: device})

    test("the theme switch turns once a press on two pages, and the choice holds over a reload", async ({page}, info) => {
      const errors = watchErrors(page)
      const other = device === "light" ? "dark" : "light"
      const toggle = page.getByRole("switch", {name: "Light theme"})
      const press = () => (info.project.name === "phone" ? toggle.tap() : toggle.click())
      // The account control beside the page is ready, and the one switch says what shows.
      const says = async (theme: "light" | "dark") => {
        await expect(page.locator(".masthead__account.phx-connected")).toBeAttached()
        await expect(toggle).toHaveCount(1)
        await expect(toggle).toHaveAttribute("aria-checked", String(theme === "light"))
      }
      const shows = async (theme: "light" | "dark") => {
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme)
        await says(theme)
      }

      // Until a choice is made the page carries no theme and the device decides.
      await page.goto("/", {waitUntil: "networkidle"})
      expect(await page.locator("html").getAttribute("data-theme")).toBeNull()
      await says(device)
      await press()
      await shows(other)
      await page.reload({waitUntil: "networkidle"})
      await shows(other)

      await page.goto("/docs", {waitUntil: "networkidle"})
      await shows(other)
      await press()
      await shows(device)
      await page.reload({waitUntil: "networkidle"})
      await shows(device)
      expect(await layoutProblems(page)).toEqual([])
      expect(errors).toEqual([])
    })
  })
}

// The tools are the same at every width, so they are read once, from the desktop.
test("the home page offers this checkout's tools and every public read answers", async ({page}, info) => {
  test.skip(info.project.name !== "desktop", "The tools are read once, from the desktop.")
  await page.addInitScript(withPageTools)
  await page.goto("/")
  await expect(page.locator("html[data-webmcp-status='connected']")).toBeAttached()

  const names = await page.evaluate(() => [...(window as unknown as Held).pageTools.keys()])
  expect(names.sort()).toEqual(offered.map(tool => tool.name).sort())

  const answers: Record<string, string> = {}
  for (const {name} of reads) {
    const reply = await page.evaluate(name => (window as unknown as Held).pageTools.get(name)!.execute({}, {}), name)
    answers[name] = reply.ok ? "ok" : `${reply.status ?? "-"}`
  }
  console.log(`WebMCP: ${names.length} tools offered, ${reads.length} public reads called`)
  expect(Object.entries(answers).filter(([, answer]) => answer !== "ok")).toEqual([])
})
