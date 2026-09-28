import "../vendor/regent_ui/blog.mjs"

// The pages are read-only documents. This bundle keeps the live connection,
// copies published commands, remembers the reader's color preference, reads
// the repository's public star count, and plays the standard motion. It never
// runs a command or sends the color preference anywhere.

import "phoenix_html"
import {Socket} from "phoenix"
import {LiveSocket} from "phoenix_live_view"

import {mountPageCopyButton, type CopyHook} from "./copy_feedback"
import {installCopyButtons} from "./copy_buttons"
import {Optics, type OpticsHook} from "./optics_controller"
import {mountMotion} from "./motion"
import {deny} from "./hooks/motion/press"
import {MotionList} from "./hooks/motion/moments"
import {installPublicTools} from "./public_tools"

mountMotion(document)
installPublicTools()
installCopyButtons()

const GITHUB_STAR_CACHE = "techtree-github-stars"
const GITHUB_STAR_REFRESH_MS = 2 * 60 * 1000
const githubStarFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  compactDisplay: "short",
  maximumFractionDigits: 1,
})

// A star count is a whole number; anything else read back is ignored.
const isCount = (value: unknown): value is number => Number.isInteger(value)

function formatGitHubStars(count: number) {
  if (count < 1000) return count.toLocaleString("en-US")

  return githubStarFormatter
    .format(count)
    .replace(/[KMBT]$/, suffix => suffix.toLowerCase())
}

function showGitHubStars(count: number) {
  if (!Number.isInteger(count) || count < 0) return

  document.querySelectorAll<HTMLElement>("[data-github-stars]").forEach(node => {
    node.querySelector("[data-github-stars-value]")!.textContent = formatGitHubStars(count)
    node.hidden = false
  })

  document.querySelectorAll("[data-github-stars-link]").forEach(link => {
    const noun = count === 1 ? "star" : "stars"
    const exactCount = count.toLocaleString("en-US")
    link.setAttribute("aria-label", `regents-ai/techtree on GitHub, ${exactCount} ${noun}`)
  })
}

async function syncGitHubStars() {
  let cached: unknown

  try {
    cached = JSON.parse(window.sessionStorage.getItem(GITHUB_STAR_CACHE) ?? "null")
  } catch (_error) {
    cached = null
  }

  if (isCount(cached)) {
    showGitHubStars(cached)
  }

  const link = document.querySelector<HTMLElement>("[data-github-stars-link]")
  const repository = link?.dataset.githubRepository
  if (!repository) return

  try {
    const response = await fetch(`https://api.github.com/repos/${repository}`, {
      headers: {Accept: "application/vnd.github+json"},
      cache: "no-store",
    })

    if (!response.ok) return
    const payload: {stargazers_count?: unknown} = await response.json()
    const count = payload.stargazers_count
    if (!isCount(count)) return

    try {
      window.sessionStorage.setItem(GITHUB_STAR_CACHE, JSON.stringify(count))
    } catch (_error) {
      // The public count can still render when storage is unavailable.
    }

    showGitHubStars(count)
  } catch (_error) {
    // Keep the server-rendered fallback when GitHub is unavailable.
  }
}

syncGitHubStars()
const githubStarRefresh = window.setInterval(syncGitHubStars, GITHUB_STAR_REFRESH_MS)
window.addEventListener("pagehide", () => window.clearInterval(githubStarRefresh), {once: true})

// The colour theme. Until the visitor chooses, the page carries no theme and the
// shared colours follow the device, dark unless it asks for light. A press
// chooses the opposite of the theme showing and writes it to the cookie the
// server reads, so the next page is drawn in it. The switch names the theme
// showing by itself; only the crown is redrawn from here.
const THEME_COOKIE = "techtree_theme"
const THEME_MAX_AGE = 60 * 60 * 24 * 365
const THEMES = {
  light: {crownVariant: "2", browserColor: "#F6F4EA"},
  dark: {crownVariant: "4", browserColor: "#161616"},
}
type Theme = keyof typeof THEMES
const lightDevice = window.matchMedia("(prefers-color-scheme: light)")

function chosenTheme(): Theme | undefined {
  const prefix = `${THEME_COOKIE}=`
  const value = document.cookie
    .split("; ")
    .find(cookie => cookie.startsWith(prefix))
    ?.slice(prefix.length)

  return value === "light" || value === "dark" ? value : undefined
}

const showingTheme = (): Theme => chosenTheme() ?? (lightDevice.matches ? "light" : "dark")

function syncCrownTheme(theme: Theme) {
  const variant = THEMES[theme].crownVariant

  document.querySelectorAll<HTMLElement>('[data-optics-kind="crown"] [data-optics-canvas]').forEach(canvas => {
    canvas.dataset.crownVariant = variant
  })
}

// Live navigation keeps the document, so each page restates its theme: the
// visitor's choice, or none so the device decides.
function syncTheme() {
  const root = document.documentElement
  const chosen = chosenTheme()
  if (chosen) root.dataset.theme = chosen
  else delete root.dataset.theme
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", chosen ?? "dark light")
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach(meta => {
    meta.content = THEMES[chosen ?? (meta.media.includes("light") ? "light" : "dark")].browserColor
  })

  const theme = showingTheme()
  syncCrownTheme(theme)
  document.dispatchEvent(new CustomEvent("techtree:themechange", {
    detail: {theme, crownVariant: THEMES[theme].crownVariant},
  }))
}

document.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.closest("[data-theme-toggle]")) return

  const theme: Theme = showingTheme() === "dark" ? "light" : "dark"
  const secure = window.location.protocol === "https:" ? "; Secure" : ""
  document.cookie = `${THEME_COOKIE}=${theme}; Path=/; Max-Age=${THEME_MAX_AGE}; SameSite=Lax${secure}`
  syncTheme()
})

window.addEventListener("phx:page-loading-stop", syncTheme)
lightDevice.addEventListener("change", syncTheme)
syncTheme()


const csrfToken = document.querySelector("meta[name='csrf-token']")!.getAttribute("content")

const Hooks: Record<string, object> = {
  Optics: {
    ...Optics,
    mounted(this: OpticsHook) {
      // A connected render can restore server attributes after initial theme sync.
      // Resolve them before the existing controller creates its first renderer.
      syncCrownTheme(showingTheme())
      Optics.mounted.call(this)
    },
  },
  MotionList,
}

type AgentVersionsHook = {
  el: HTMLElement
  hadFocus?: boolean
  revealSelection(this: AgentVersionsHook): void
}

Hooks.AgentVersions = {
  mounted(this: AgentVersionsHook) { this.revealSelection() },
  beforeUpdate(this: AgentVersionsHook) { this.hadFocus = this.el.contains(document.activeElement) },
  updated(this: AgentVersionsHook) { this.revealSelection() },
  revealSelection(this: AgentVersionsHook) {
    const strip = this.el.querySelector(".agent-versions__list")
    const selected = strip?.querySelector<HTMLElement>('[aria-current="page"]')
    if (!strip || !selected) return
    if (this.hadFocus && !this.el.contains(document.activeElement)) {
      selected.focus({preventScroll: true})
    }
    this.hadFocus = false
    const stripBounds = strip.getBoundingClientRect()
    const selectedBounds = selected.getBoundingClientRect()
    strip.scrollLeft += selectedBounds.left - stripBounds.left -
      (strip.clientWidth - selectedBounds.width) / 2
  },
}


// One page, spoken as Markdown. The serializer walks exactly what the reader
// sees — headings, prose, lists, terms, commands, fingerprints — so the copy
// can never drift from the page, release values included. Nothing is sent
// anywhere: the result goes to the clipboard, or into a new tab the reader
// opened themselves.
const isElement = (node: Node): node is Element => node.nodeType === Node.ELEMENT_NODE

function pageAsMarkdown(root: Element) {
  const lines: string[] = []

  const text = (node: Element) => node.textContent.replace(/\s+/g, " ").trim()

  const inline = (node: Element): string => {
    let out = ""
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        out += child.textContent!.replace(/\s+/g, " ")
      } else if (isElement(child)) {
        const tag = child.tagName.toLowerCase()
        if (tag === "code" || child.classList.contains("digest")) {
          out += "`" + text(child) + "`"
        } else if (tag === "a") {
          const href = child.getAttribute("href") || ""
          const absolute = new URL(href, window.location.href).href
          out += "[" + text(child) + "](" + absolute + ")"
        } else if (tag === "strong" || tag === "b") {
          out += "**" + text(child) + "**"
        } else {
          out += inline(child)
        }
      }
    }
    return out
  }

  const walk = (node: Element) => {
    for (const child of node.children) {
      if (child.closest("[data-markdown-skip]")) continue
      const tag = child.tagName.toLowerCase()

      if (/^h[1-6]$/.test(tag)) {
        lines.push("#".repeat(Number(tag[1])) + " " + text(child), "")
      } else if (tag === "p") {
        const line = inline(child).replace(/\s+/g, " ").trim()
        if (line) lines.push(line, "")
      } else if (tag === "pre") {
        lines.push("```", child.textContent.trim(), "```", "")
      } else if (tag === "ul" || tag === "ol") {
        Array.from(child.children).forEach((item, index) => {
          const marker = tag === "ol" ? `${index + 1}.` : "-"
          lines.push(marker + " " + inline(item).replace(/\s+/g, " ").trim())
        })
        lines.push("")
      } else if (tag === "table") {
        const rows = Array.from(child.querySelectorAll("tr"), row =>
          Array.from(row.children, cell => inline(cell).replace(/\s+/g, " ").trim()))
        const line = (cells: string[]) => "| " + cells.join(" | ") + " |"
        if (rows.length) {
          lines.push(line(rows[0]), line(rows[0].map(() => "---")), ...rows.slice(1).map(line), "")
        }
      } else if (tag === "dl") {
        let term: string | null = null
        for (const part of child.children) {
          if (part.tagName === "DT") term = text(part)
          if (part.tagName === "DD" && term !== null) {
            lines.push("- **" + term + "**: " + inline(part).replace(/\s+/g, " ").trim())
            term = null
          }
        }
        lines.push("")
      } else {
        walk(child)
      }
    }
  }

  walk(root)
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n"
}

const docsRoot = () => document.querySelector("[data-markdown-root]") ?? document.querySelector("main")!

Hooks.CopyCommandPage = {
  mounted(this: CopyHook) {
    mountPageCopyButton(this, () => pageAsMarkdown(docsRoot()), {refuse: deny})
  },
}

Hooks.CopyCommandPageView = {
  mounted(this: {el: HTMLElement}) {
    this.el.addEventListener("click", () => {
      const markdown = pageAsMarkdown(docsRoot())
      const tab = window.open("", "_blank")
      if (!tab) return
      tab.document.title = "Techtree docs as Markdown"
      const pre = tab.document.createElement("pre")
      pre.style.cssText = "white-space:pre-wrap;font-family:ui-monospace,monospace;padding:2rem;max-width:60rem;margin:0 auto;"
      pre.textContent = markdown
      tab.document.body.appendChild(pre)
    })
  },
}

const liveSocket = new LiveSocket("/live", Socket, {
  longPollFallbackMs: 2500,
  params: {_csrf_token: csrfToken},
  hooks: Hooks,
})

liveSocket.connect()

// Exposed for debugging in the browser console:
//   liveSocket.enableDebug()
//   liveSocket.disableDebug()
window.liveSocket = liveSocket
