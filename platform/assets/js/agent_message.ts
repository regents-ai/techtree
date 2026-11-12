/**
 * The Agent Message window (`AgentMessage`), on every page that shows its
 * button, from one listener on the document. The button opens the window its
 * `aria-controls` names; the window's X, Escape, or a press on its backdrop,
 * which lands on the window itself, closes it. Its copy buttons are the page's
 * shared copy listener's.
 */
export function installAgentMessage() {
  document.addEventListener("click", event => {
    const target = event.target instanceof Element ? event.target : null
    const opener = target?.closest<HTMLButtonElement>("[data-agent-message-open]")
    const dialog = opener && document.getElementById(opener.getAttribute("aria-controls") ?? "")
    if (dialog instanceof HTMLDialogElement) {
      dialog.showModal()
      return
    }

    const shown = target?.closest<HTMLDialogElement>("dialog[data-agent-message]")
    if (shown && (target === shown || target?.closest("[data-agent-message-close]"))) shown.close()
  })
}
