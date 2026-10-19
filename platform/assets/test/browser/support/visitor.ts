import {execFileSync} from "node:child_process"
import type {BrowserContext, Page} from "@playwright/test"

// Runs one of the support scripts in the browser test database and returns the
// JSON it printed last.
function inBrowserDatabase(script: string): string {
  const out = execFileSync("mix", ["run", "--no-start", `assets/test/browser/support/${script}`], {
    cwd: "..",
    env: {...process.env, MIX_ENV: "test", MIX_TEST_PARTITION: "browser", TECHTREE_BROWSER_TEST: "1"},
    encoding: "utf8",
  })
  return out.trim().split("\n").findLast(line => line.startsWith("{")) as string
}

// Three recorded Wallet Bench tests, by outcome: passed, failed and running.
export function seedWalletBench(): {passed: string; failed: string; running: string} {
  return JSON.parse(inBrowserDatabase("seed_wallet_bench.exs"))
}

// A fresh signed-in session for one browser context. Each context gets its own:
// the site ends a session another browser presents after it has moved on.
export async function signIn(context: BrowserContext): Promise<void> {
  const {name, value} = JSON.parse(inBrowserDatabase("sign_in.exs"))
  await context.addCookies([{name, value, domain: "127.0.0.1", path: "/"}])
  // There is no Privy sign-in behind this session, so the provider bridge is
  // answered with an empty script; the real one would rightly sign it out.
  await context.route(/\/assets\/js\/privy_bridge/, route =>
    route.fulfill({contentType: "text/javascript", body: ""}))
}

// Every error a page raised or logged.
export function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on("pageerror", error => errors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error") errors.push(message.text())
  })
  return errors
}

// What a visitor would trip over: sideways scrolling, and press targets that are
// too small. On a touch screen every control and every link that stands on its
// own needs 44 pixels of height; a link inside a sentence is exempt (its paragraph
// says more than the link). With a mouse, WCAG 2.5.8's 24 pixels applies to
// controls, and an inline text link passes on the spacing around it. A visually
// hidden input is pressed through its label, so the label is what is measured.
export async function layoutProblems(page: Page): Promise<string[]> {
  // A press or an opening squishes or slides what moved; measure it at rest, once
  // the motion has handed every element back to the stylesheet.
  await page.waitForFunction(() => !document.querySelector("body [style*='transform']"))
  return page.evaluate(() => {
    const insideSentence = (el: Element, style: CSSStyleDeclaration) => {
      if (style.display !== "inline") return false
      const block = el.parentElement?.closest("p, li, dd, td, figcaption, h1, h2, h3, h4")
      return !!block && (block.textContent ?? "").trim().length > (el.textContent ?? "").trim().length + 2
    }
    const touch = matchMedia("(pointer: coarse)").matches
    const minHeight = touch ? 44 : 24
    const problems: string[] = []
    const root = document.documentElement
    if (root.scrollWidth > root.clientWidth) problems.push(`scrolls sideways (${root.scrollWidth} > ${root.clientWidth})`)

    for (const control of document.querySelectorAll<HTMLElement>("a[href], button, [role=button], summary, input, select")) {
      let el: HTMLElement = control
      let box = el.getBoundingClientRect()
      if (box.width <= 1 && box.height <= 1 && el instanceof HTMLInputElement && el.labels?.[0]) {
        el = el.labels[0]
        box = el.getBoundingClientRect()
      }
      const style = getComputedStyle(el)
      if (style.visibility === "hidden" || style.display === "none" || !box.width || !box.height) continue
      if (insideSentence(el, style)) continue
      if (!touch && el.tagName === "A" && style.display === "inline") continue
      if (box.height < minHeight || box.width < 24)
        problems.push(`${el.tagName.toLowerCase()} ${el.id || el.getAttribute("aria-label") || el.textContent?.trim().slice(0, 24)} is ${Math.round(box.width)}x${Math.round(box.height)}`)
    }
    return problems
  })
}
