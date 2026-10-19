// Headless checks and pictures for the Techtree one-purpose mockups.
import {chromium} from "playwright"

const BASE = "http://localhost:4015"
const SHOTS = new URL("site/page-list/shots", import.meta.url).pathname
const pages = [["home", "/"], ["docs", "/docs/"], ["guide", "/docs/test-a-skill/"], ["list", "/page-list/"]]
const sizes = {desktop: {width: 1440, height: 900}, phone: {width: 390, height: 844}, small: {width: 320, height: 640}}
const wanted = new Set(["home-desktop-light", "home-phone-dark", "docs-desktop-dark", "docs-phone-light", "guide-desktop-light", "guide-phone-dark"])
const shoot = process.argv.includes("--shots")

const browser = await chromium.launch({channel: "chromium", args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan", "--use-angle=metal"]})
const problems = []
let checks = 0
const ok = (cond, what) => { checks++; if (!cond) problems.push(what) }

for (const [name, path] of pages) {
  for (const [sizeName, viewport] of Object.entries(sizes)) {
    for (const scheme of ["light", "dark"]) {
      const context = await browser.newContext({viewport, colorScheme: scheme, deviceScaleFactor: sizeName === "desktop" ? 1 : 2})
      const page = await context.newPage()
      const errors = []
      page.on("console", m => { if (m.type() === "error") errors.push(m.text()) })
      page.on("pageerror", e => errors.push(String(e)))
      const failed = []
      page.on("response", r => { if (r.status() >= 400) failed.push(`${r.status()} ${r.url()}`) })
      await page.goto(`${BASE}${path}?shot`, {waitUntil: "networkidle"})
      const tag = `${name}-${sizeName}-${scheme}`
      if (name === "home") {
        await page.locator("#hero-crown").scrollIntoViewIfNeeded().catch(() => {})
        await page.waitForFunction(() => {
          const r = document.querySelector("#hero-crown")
          return r.dataset.opticsReady === "true" || r.dataset.opticsFailed === "true" || getComputedStyle(r).display === "none"
        }, null, {timeout: 15000}).catch(() => {})
        const crown = await page.evaluate(() => { const r = document.querySelector("#hero-crown"); return {ready: r.dataset.opticsReady, failed: r.dataset.opticsFailed, display: getComputedStyle(r).display} })
        if (sizeName === "desktop") console.log(`${tag} crown`, JSON.stringify(crown))
        ok(crown.ready === "true" || crown.failed === "true" || crown.display === "none", `${tag}: crown neither drew nor showed its still`)
        await page.evaluate(() => scrollTo(0, 0))
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)
      ok(overflow <= 0, `${tag}: page is ${overflow}px wider than the screen`)
      ok(errors.length === 0, `${tag}: console errors ${errors.join(" | ")}`)
      ok(failed.length === 0, `${tag}: failed loads ${failed.join(" | ")}`)
      const theme = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
      ok(scheme === "dark" ? theme === "rgb(22, 22, 22)" : theme === "rgb(246, 244, 234)", `${tag}: background ${theme}`)
      const footer = await page.evaluate(() => { const f = document.querySelector(".regent-footer").getBoundingClientRect(); return f.bottom <= document.documentElement.scrollHeight + 1 && f.height > 0 })
      ok(footer, `${tag}: footer missing`)
      if (shoot && wanted.has(tag)) {
        await page.screenshot({path: `${SHOTS}/${tag}.jpg`, type: "jpeg", quality: 78, fullPage: true})
      }
      await context.close()
    }
  }
}

// Every link inside the mockup lands on a page or an anchor that exists.
{
  const context = await browser.newContext()
  const page = await context.newPage()
  const seen = new Set()
  for (const [, path] of pages) {
    await page.goto(`${BASE}${path}`)
    const links = await page.$$eval("a[href^='/']", as => as.map(a => a.getAttribute("href")))
    for (const link of links) seen.add(link)
  }
  for (const link of seen) {
    const [path, hash] = link.split("#")
    const response = await page.goto(`${BASE}${path}`)
    ok(response.status() === 200, `link ${link} answers ${response.status()}`)
    if (hash) ok(await page.$(`#${hash}`) !== null, `link ${link} has no #${hash} on its page`)
  }
  console.log(`links checked: ${seen.size}`)
  await context.close()
}

// Interactions: theme switch, copy, the arrow nudge and the press.
{
  const context = await browser.newContext({viewport: sizes.desktop, colorScheme: "light", permissions: ["clipboard-read", "clipboard-write"]})
  const page = await context.newPage()
  await page.goto(`${BASE}/`)
  await page.click("[data-theme-toggle]")
  ok(await page.evaluate(() => document.documentElement.dataset.theme) === "dark", "theme switch did not turn dark")
  await page.click("[data-theme-toggle]")
  ok(await page.evaluate(() => document.documentElement.dataset.theme) === "light", "theme switch did not turn light")
  await page.click(".hero .rg-copy")
  ok(await page.waitForFunction(() => document.querySelector(".hero .rg-copy").dataset.copyState === "copied", null, {timeout: 1000}).then(() => true, () => false), "copy did not say Copied")
  ok((await page.evaluate(() => navigator.clipboard.readText())).startsWith("Read https://techtree.sh/agents.md"), "copy put the wrong text on the clipboard")

  await page.goto(`${BASE}/docs/test-a-skill/`)
  const next = page.locator(".mk-next .rg-button")
  await next.hover()
  await page.waitForTimeout(120)
  const nudge = await next.evaluate(el => el.style.getPropertyValue("--rg-chevron-x"))
  ok(nudge && nudge !== "0px", `hover arrow did not move (${nudge})`)
  await page.waitForTimeout(400)
  ok(await next.evaluate(el => el.getAttribute("style") || "") === "", "hover left an inline style behind")
  await next.evaluate(el => el.addEventListener("click", e => e.preventDefault()))
  await page.mouse.move(0, 0)
  const box = await next.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.waitForTimeout(400)
  await page.mouse.down()
  await page.waitForTimeout(60)
  const pressed = await next.evaluate(el => el.style.getPropertyValue("--rg-press-scale"))
  await page.mouse.up()
  ok(pressed && Number(pressed) < 1, `press did not give (${pressed})`)
  await page.goto(`${BASE}/docs/test-a-skill/`)
  await page.click("[data-copy-link]")
  ok((await page.evaluate(() => navigator.clipboard.readText())) === `${BASE}/docs/test-a-skill/`, "Copy link copied the wrong address")
  const clip = await page.evaluate(() => getComputedStyle(document.querySelector(".mk-next .rg-button"), "::before").clipPath)
  ok(clip.startsWith("polygon"), `buttons are not cut (${clip})`)
  await context.close()
}

// Reduced motion: nothing moves on hover.
{
  const context = await browser.newContext({viewport: sizes.desktop, reducedMotion: "reduce"})
  const page = await context.newPage()
  await page.goto(`${BASE}/docs/test-a-skill/`)
  const next = page.locator(".mk-next .rg-button")
  await next.hover()
  await page.waitForTimeout(120)
  ok(await next.evaluate(el => el.style.getPropertyValue("--rg-chevron-x")) === "", "arrow moved with reduced motion")
  await context.close()
}

await browser.close()
console.log(`${checks} checks, ${problems.length} problems`)
for (const p of problems) console.log(` - ${p}`)
process.exit(problems.length ? 1 : 0)
