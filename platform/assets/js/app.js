// The pages are read-only documents. This bundle keeps the live connection,
// copies published commands, remembers the reader's color preference, and
// draws the crown behind the headline. It never runs a command or sends the
// preference anywhere.

import "phoenix_html"
import {Socket} from "phoenix"
import {LiveSocket} from "phoenix_live_view"

import {Optics} from "./optics_controller"

const THEME_COOKIE = "techtree_theme"
const THEME_MAX_AGE = 60 * 60 * 24 * 365
const THEMES = {
  orange: {
    crownVariant: "2",
    name: "Orange",
    nextName: "Titanium dark",
    browserColor: "#f4eee4",
  },
  titanium: {
    crownVariant: "4",
    name: "Titanium",
    nextName: "Orange light",
    browserColor: "#101010",
  },
}
function readThemeCookie() {
  const prefix = `${THEME_COOKIE}=`
  const value = document.cookie
    .split("; ")
    .find(cookie => cookie.startsWith(prefix))
    ?.slice(prefix.length)

  return Object.hasOwn(THEMES, value) ? value : undefined
}

function writeThemeCookie(theme) {
  const secure = window.location.protocol === "https:" ? "; Secure" : ""
  document.cookie =
    `${THEME_COOKIE}=${theme}; Path=/; Max-Age=${THEME_MAX_AGE}; SameSite=Lax${secure}`
}

let savedTheme = readThemeCookie()

const resolvedTheme = () => savedTheme || "titanium"

function previewRouteTheme() {
  if (/^\/crown\/2\/?$/.test(window.location.pathname)) return "orange"
  if (/^\/crown\/4\/?$/.test(window.location.pathname)) return "titanium"
  return undefined
}

const pageTheme = () => previewRouteTheme() || resolvedTheme()

function syncThemeControl(theme) {
  const selected = THEMES[theme]
  const orangeActive = theme === "orange"

  document.querySelectorAll("[data-theme-toggle]").forEach(toggle => {
    toggle.dataset.theme = theme
    toggle.setAttribute("aria-pressed", String(orangeActive))
    toggle.setAttribute(
      "aria-label",
      `Color theme: ${selected.name}. Activate ${selected.nextName} theme.`,
    )
    toggle.setAttribute("title", `Switch to ${selected.nextName}`)
    const state = toggle.querySelector("[data-theme-toggle-state]")
    if (state) state.textContent = `${selected.name} theme active`
  })
}

function syncCrownTheme(theme) {
  const variant = THEMES[theme].crownVariant
  let changed = false

  document.querySelectorAll('[data-optics-kind="crown"]').forEach(root => {
    if (root.dataset.crownThemeControlled !== "true") return

    const canvas = root.querySelector("[data-optics-canvas]")
    const hero = root.closest(".hero")
    changed ||= root.dataset.crownVariant !== variant || canvas?.dataset.crownVariant !== variant
    root.dataset.crownVariant = variant
    if (canvas) canvas.dataset.crownVariant = variant
    if (hero) hero.dataset.crownVariant = variant
  })

  if (changed) {
    document.dispatchEvent(new CustomEvent("techtree:themechange", {
      detail: {theme, crownVariant: variant},
    }))
  }
}

function applyTheme(theme) {
  const selected = THEMES[theme]
  document.documentElement.dataset.theme = theme
  document.querySelector("meta[name='theme-color']")?.setAttribute("content", selected.browserColor)
  syncThemeControl(theme)
  syncCrownTheme(theme)
}

document.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.closest("[data-theme-toggle]")) return

  const activeTheme = document.documentElement.dataset.theme || pageTheme()
  const theme = activeTheme === "orange" ? "titanium" : "orange"
  savedTheme = theme
  writeThemeCookie(theme)
  applyTheme(theme)
})

window.addEventListener("phx:page-loading-stop", () => applyTheme(pageTheme()))
applyTheme(pageTheme())

const csrfToken = document.querySelector("meta[name='csrf-token']").getAttribute("content")

const Hooks = {Optics}

Hooks.CopyCommand = {
  mounted() {
    this.el.addEventListener("click", async () => {
      const label = this.el.querySelector("[data-copy-label]")

      try {
        await navigator.clipboard.writeText(this.el.dataset.copyValue)
        label.textContent = "Copied"
        this.el.classList.add("is-copied")

        window.setTimeout(() => {
          label.textContent = "Copy"
          this.el.classList.remove("is-copied")
        }, 1800)
      } catch (_error) {
        label.textContent = "Select the text"
      }
    })
  },
}


// One page, spoken as Markdown. The serializer walks exactly what the reader
// sees — headings, prose, lists, terms, commands, fingerprints — so the copy
// can never drift from the page, release values included. Nothing is sent
// anywhere: the result goes to the clipboard, or into a new tab the reader
// opened themselves.
function pageAsMarkdown(root) {
  const lines = []

  const text = (node) => node.textContent.replace(/\s+/g, " ").trim()

  const inline = (node) => {
    let out = ""
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        out += child.textContent.replace(/\s+/g, " ")
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        const tag = child.tagName.toLowerCase()
        if (tag === "code" || child.classList.contains("digest")) {
          out += "`" + text(child) + "`"
        } else if (tag === "a") {
          const href = child.getAttribute("href") || ""
          const absolute = href.startsWith("http") ? href : window.location.origin + href
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

  const walk = (node) => {
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
      } else if (tag === "dl") {
        let term = null
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

const docsRoot = () => document.querySelector("main")

Hooks.CopyCommandPage = {
  mounted() {
    this.el.addEventListener("click", async () => {
      const label = this.el.querySelector("[data-copy-label]")
      try {
        await navigator.clipboard.writeText(pageAsMarkdown(docsRoot()))
        label.textContent = "Copied"
        this.el.classList.add("is-copied")
        window.setTimeout(() => {
          label.textContent = "Copy page"
          this.el.classList.remove("is-copied")
        }, 1800)
      } catch (_error) {
        label.textContent = "Select the text"
      }
    })
  },
}

Hooks.CopyCommandPageView = {
  mounted() {
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
