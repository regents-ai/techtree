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
