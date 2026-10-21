import {browserCsrfToken, holdSocketDuringCookieRotation, installAccountAuthLazyLoader,
  installCrossTabCsrf, retireRefusedSession, type PinnedSocket} from "./auth_lazy"
import {InfoDialog} from "./hooks/info_dialog"
import {AccountPicture} from "./hooks/account_picture"
import {AccountShell} from "./hooks/account_shell"
import {SidePanel} from "./hooks/side_panel"
import {PanelAgents} from "./hooks/panel_agents"
import {VerifiedConnections} from "./hooks/verified_connections"
import "../vendor/regent_ui/blog.mjs"
import "../vendor/regent_ui/pill_select.mjs"

// The pages are read-only documents. This bundle keeps the live connection,
// copies published commands, remembers the reader's color preference, reads
// the repository's public star count, and plays the standard motion. It never
// runs a command or sends the color preference anywhere.

import "phoenix_html"
import {Socket} from "phoenix"
import {LiveSocket} from "phoenix_live_view"

import {mountPageCopyButton, type CopyHook} from "./copy_feedback"
import {installCopyButtons} from "./copy_buttons"
import {crownHook} from "./hooks/crown"
import {mountMotion} from "./motion"
import {deny} from "./hooks/motion/press"
import {MotionList, MotionCount, MotionRefusal} from "./hooks/motion/moments"
import {installPublicTools} from "./public_tools"

mountMotion(document)
installPublicTools()
installCopyButtons()

// The colour theme. Until the visitor chooses, the page carries no theme and the
// shared colours follow the device, dark unless it asks for light. A press
// chooses the opposite of the theme showing and writes it to the cookie the
// server reads, so the next page is drawn in it. The switch names the theme
// showing by itself; only the crown is redrawn from here.
const THEME_COOKIE = "techtree_theme"
const THEME_MAX_AGE = 60 * 60 * 24 * 365
const THEMES = {
  light: {crownVariant: 2, browserColor: "#F3F5EF"},
  dark: {crownVariant: 4, browserColor: "#0D1611"},
} as const
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

  document.dispatchEvent(new CustomEvent("techtree:themechange", {
    detail: {theme: showingTheme()},
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


if (!browserCsrfToken()) throw new Error("Missing CSRF token")

// The motion lab's own presses and moments are used only on the lab page, which
// nothing links to, so they load only when that page is opened directly.
const labHooks = document.querySelector("main.motion-lab")
  ? (await import("./motion_lab")).hooks : {}

// The wallet code drives only the Approve and Buy buttons in the Buy Credits
// window on the account pages. Those pages run in their own live session, so
// reaching one always loads the page afresh and asks again. Every account page
// loads it, signed in or not, since a sign-in can arrive on an open page
// without a reload. It is loaded before the page connects, so it is ready
// before either button can be pressed.
const walletHooks = document.getElementById("account-shell")
  ? {OnchainSteps: (await import("./hooks/onchain_steps")).OnchainSteps} : {}

const Hooks: Record<string, object> = {
  Crown: crownHook(() => THEMES[showingTheme()].crownVariant),
  MotionList,
  ...labHooks,
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

Object.assign(Hooks, {InfoDialog, AccountPicture, AccountShell, SidePanel, PanelAgents, VerifiedConnections, ...walletHooks, MotionCount, MotionRefusal})

const liveSocket = new LiveSocket("/live", Socket, {
  longPollFallbackMs: 2500,
  params: () => ({_csrf_token: browserCsrfToken()}),
  hooks: Hooks,
})

if (document.querySelector('meta[name="privy-app-id"]')) {
  holdSocketDuringCookieRotation(liveSocket.getSocket() as PinnedSocket)
  void retireRefusedSession()
  installAccountAuthLazyLoader()
  installCrossTabCsrf()
}
liveSocket.connect()

// Exposed for debugging in the browser console:
//   liveSocket.enableDebug()
//   liveSocket.disableDebug()
window.liveSocket = liveSocket
