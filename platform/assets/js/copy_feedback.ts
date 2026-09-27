// The hook a copy button mounts on, and the feedback it is part-way through.
export type CopyHook = {
  el: HTMLElement
  copyFeedbackTimer?: number
  copyAnnouncementFrame?: number
  copyInFlight?: boolean
}

type CopyOptions = {
  refuse: (el: HTMLElement) => void
  writeText?: (value: string) => Promise<void>
}

function copyStatusFor(button: HTMLElement) {
  const status = button.nextElementSibling
  return status?.matches("[data-copy-status]") ? status : null
}

function resetCopyFeedback(hook: CopyHook, label: Element, idleLabel: string, status: Element | null) {
  window.clearTimeout(hook.copyFeedbackTimer)
  if (hook.copyAnnouncementFrame !== undefined) window.cancelAnimationFrame(hook.copyAnnouncementFrame)
  label.textContent = idleLabel
  if (status) status.textContent = ""
}

function announceCopyStatus(hook: CopyHook, status: Element | null, message: string) {
  if (!status) return
  hook.copyAnnouncementFrame = window.requestAnimationFrame(() => {
    status.textContent = message
  })
}

function scheduleCopyFeedbackReset(
  hook: CopyHook,
  label: Element,
  idleLabel: string,
  status: Element | null,
  delay: number,
) {
  hook.copyFeedbackTimer = window.setTimeout(() => {
    label.textContent = idleLabel
      if (status) status.textContent = ""
  }, delay)
}

const IDLE_LABEL = "Copy page"
const COPIED_MESSAGE = "Page copied as Markdown."
const FAILED_MESSAGE = "Couldn't copy. Use View as Markdown to open the Markdown, then copy it manually."

// "Copy page" copies Markdown built from the page itself when pressed, so it
// keeps this step; every other copy control is `Regent.Primitives.copy_button`.
// `refuse` answers a copy that could not happen, beside the words that say so.
export function mountPageCopyButton(
  hook: CopyHook,
  copyValue: () => string,
  {refuse, writeText = value => navigator.clipboard.writeText(value)}: CopyOptions,
) {
  hook.el.addEventListener("click", async () => {
    if (hook.copyInFlight) return
    hook.copyInFlight = true

    const label = hook.el.querySelector("[data-copy-label]")!
    const status = copyStatusFor(hook.el)
    resetCopyFeedback(hook, label, IDLE_LABEL, status)

    try {
      await writeText(copyValue())
      label.textContent = "Copied"
      announceCopyStatus(hook, status, COPIED_MESSAGE)
      scheduleCopyFeedbackReset(hook, label, IDLE_LABEL, status, 1800)
    } catch (_error) {
      label.textContent = "Couldn't copy"
      refuse(hook.el)
      announceCopyStatus(hook, status, FAILED_MESSAGE)
      scheduleCopyFeedbackReset(hook, label, IDLE_LABEL, status, 4000)
    } finally {
      hook.copyInFlight = false
    }
  })
}
