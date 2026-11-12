import {browserCsrfToken, holdSocketDuringCookieRotation, installAccountAuthLazyLoader,
  holdAdoptionWhileLeaving, installCrossTabCsrf, retireRefusedSession, type PinnedSocket} from "./auth_lazy"
import {InfoDialog} from "./hooks/info_dialog"
import {AccountPicture} from "./hooks/account_picture"
import {AccountMenu} from "./hooks/account_menu"
import {AccountShell} from "./hooks/account_shell"
import {MenuAgents} from "./hooks/menu_agents"
import {VerifiedConnections} from "./hooks/verified_connections"
import "../vendor/regent_ui/blog.mjs"
import "../vendor/regent_ui/confirm.mjs"
import "../vendor/regent_ui/pill_select.mjs"

// The pages are read-only documents. This bundle keeps the live connection,
// copies published commands, turns the light and dark theme switch, reads the
// repository's public star count, and plays the standard motion. It never runs
// a command or sends the theme chosen anywhere.

import {Socket} from "phoenix"
import {LiveSocket} from "phoenix_live_view"

import {installAgentMessage} from "./agent_message"
import {mountPageCopyButton, type CopyHook} from "./copy_feedback"
import {installCopyButtons} from "./copy_buttons"
import {crownHook} from "./hooks/crown"
import {ThemeSwitch} from "./hooks/theme_switch"
import {mountMotion} from "./motion"
import {deny} from "./hooks/motion/press"
import {MotionList, MotionRefusal} from "./hooks/motion/moments"
import {MotionCascade} from "./hooks/motion/reveals"
import {installPublicTools} from "./public_tools"
import {installSiteMenu} from "./site_menu"
import {showingTheme, syncTheme} from "./theme"
import {installVisitLog} from "./visit_log"

// First, so an error anywhere below is reported too.
installVisitLog()
mountMotion(document)
installPublicTools()
installCopyButtons()
installAgentMessage()
installSiteMenu()

// Live navigation keeps the document, and Back may bring a kept page, so each
// page restates the theme (theme.ts).
window.addEventListener("phx:page-loading-stop", syncTheme)
window.addEventListener("popstate", syncTheme)
window.addEventListener("pageshow", syncTheme)

if (!browserCsrfToken()) throw new Error("Missing CSRF token")

// The motion lab's own presses and moments are used only on the lab page, which
// nothing links to, so they load only when that page is opened directly.
const labHooks = document.querySelector("main.motion-lab")
  ? (await import("./motion_lab")).hooks : {}

const Hooks: Record<string, object> = {
  // Each theme has its own crown.
  Crown: crownHook(() => (showingTheme() === "light" ? 2 : 4)),
  MotionList,
  ThemeSwitch,
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

Object.assign(Hooks, {InfoDialog, AccountPicture, AccountMenu, AccountShell, MenuAgents, VerifiedConnections, MotionRefusal, MotionCascade})

const liveSocket = new LiveSocket("/live", Socket, {
  longPollFallbackMs: 2500,
  params: () => ({_csrf_token: browserCsrfToken()}),
  hooks: Hooks,
})

if (document.querySelector('meta[name="privy-app-id"]')) {
  holdSocketDuringCookieRotation(liveSocket.getSocket() as PinnedSocket)
  holdAdoptionWhileLeaving()
  void retireRefusedSession()
  installAccountAuthLazyLoader()
  installCrossTabCsrf()
}
liveSocket.connect()

// Exposed for debugging in the browser console:
//   liveSocket.enableDebug()
//   liveSocket.disableDebug()
window.liveSocket = liveSocket
