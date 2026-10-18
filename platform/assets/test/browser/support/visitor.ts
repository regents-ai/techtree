import {execFileSync} from "node:child_process"
import type {BrowserContext, Page} from "@playwright/test"

// A fresh signed-in session for one browser context. Each context gets its own:
// the site ends a session another browser presents after it has moved on.
export async function signIn(context: BrowserContext): Promise<void> {
  const out = execFileSync("mix", ["run", "--no-start", "assets/test/browser/support/sign_in.exs"], {
    cwd: "..",
    env: {...process.env, MIX_ENV: "test", MIX_TEST_PARTITION: "browser", TECHTREE_BROWSER_TEST: "1"},
    encoding: "utf8",
  })
  const {name, value} = JSON.parse(out.trim().split("\n").at(-1) as string)
  await context.addCookies([{name, value, domain: "127.0.0.1", path: "/"}])
  // There is no Privy sign-in behind this session, so the provider bridge is
  // kept off the page; it would rightly sign the session out.
  await context.route(/privy_bridge|auth\.privy\.io/, route => route.abort())
}

// Errors a page raised, other than requests the test itself refused.
export function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on("pageerror", error => errors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error" && !/ERR_FAILED|api\.github\.com|status of 403/.test(message.text()))
      errors.push(message.text())
  })
  return errors
}

// What a visitor would trip over: sideways scrolling, and press targets smaller
// than a finger on a touch screen (44 pixels tall) or than WCAG 2.5.8's 24 pixels
// with a mouse. Links inside running text are exempt, as WCAG 2.5.8 allows.
export async function layoutProblems(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const minHeight = matchMedia("(pointer: coarse)").matches ? 44 : 24
    const problems: string[] = []
    const root = document.documentElement
    if (root.scrollWidth > root.clientWidth) problems.push(`scrolls sideways (${root.scrollWidth} > ${root.clientWidth})`)

    for (const el of document.querySelectorAll<HTMLElement>("a[href], button, [role=button], summary, input, select")) {
      const style = getComputedStyle(el)
      const box = el.getBoundingClientRect()
      if (style.visibility === "hidden" || style.display === "none" || !box.width || !box.height) continue
      if (el.closest("#shell-aside, [popover], dialog:not([open])")) continue
      if (style.display === "inline" && el.closest("p, li, dd, td, figcaption, h1, h2, h3")) continue
      if (box.height < minHeight || box.width < 24)
        problems.push(`${el.tagName.toLowerCase()} ${el.id || el.getAttribute("aria-label") || el.textContent?.trim().slice(0, 24)} is ${Math.round(box.width)}x${Math.round(box.height)}`)
    }
    return problems
  })
}
