import {execFileSync} from "node:child_process"
import type {BrowserContext, Locator, Page} from "@playwright/test"

// Runs one of the support scripts in the browser test database and returns the
// JSON it printed last.
function inBrowserDatabase(script: string): string {
  const out = execFileSync("mix", ["run", "--no-start", `assets/test/browser/support/${script}`], {
    cwd: "..",
    env: {
      ...process.env,
      MIX_ENV: "test",
      MIX_TEST_PARTITION: process.env.TECHTREE_BROWSER_PARTITION,
      TECHTREE_BROWSER_TEST: "1",
    },
    encoding: "utf8",
  })
  return out.trim().split("\n").findLast(line => line.startsWith("{")) as string
}

// Three recorded Wallet Bench tests, by outcome: passed, failed and running.
export type RecordedTest = {id: string; name: string}

export function seedWalletBench(): {passed: RecordedTest; failed: RecordedTest; running: RecordedTest} {
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

// Text inside `scope` whose contrast with what is behind it falls under WCAG's
// 4.5:1, as the page renders it: each colour is drawn onto a canvas and read
// back, so any colour the stylesheet mixes is measured as shown.
export async function lowContrast(scope: Locator): Promise<string[]> {
  return scope.evaluate(root => {
    const canvas = document.createElement("canvas")
    canvas.width = canvas.height = 1
    const pen = canvas.getContext("2d", {willReadFrequently: true})!
    const rgba = (color: string) => {
      pen.clearRect(0, 0, 1, 1)
      pen.fillStyle = color
      pen.fillRect(0, 0, 1, 1)
      return Array.from(pen.getImageData(0, 0, 1, 1).data)
    }
    const background = (el: Element | null): number[] => {
      for (; el; el = el.parentElement) {
        const [r, g, b, a] = rgba(getComputedStyle(el).backgroundColor)
        if (a === 255) return [r, g, b]
      }
      return [255, 255, 255]
    }
    const luminance = ([r, g, b]: number[]) =>
      [r, g, b].map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0)
    const problems: string[] = []
    for (const el of root.querySelectorAll<HTMLElement>("*")) {
      const text = Array.from(el.childNodes).filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join("").trim()
      const box = el.getBoundingClientRect()
      if (!text || box.width <= 1 || box.height <= 1) continue
      const [light, dark] = [luminance(rgba(getComputedStyle(el).color)), luminance(background(el))].sort((a, b) => b - a)
      const ratio = (light + 0.05) / (dark + 0.05)
      if (ratio < 4.5) problems.push(`"${text}" at ${ratio.toFixed(2)}:1`)
    }
    return problems
  })
}
