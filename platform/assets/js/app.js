// The pages are read-only documents. This bundle keeps the live connection
// that renders them, and offers one local convenience: putting a command the
// active release already published onto the reader's clipboard. It never runs
// that command, sends anything anywhere, or reads anything about the reader.

import "phoenix_html"
import {Socket} from "phoenix"
import {LiveSocket} from "phoenix_live_view"

const csrfToken = document.querySelector("meta[name='csrf-token']").getAttribute("content")

const Hooks = {}

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
