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

function resetCopyFeedback(hook: CopyHook, words: HTMLElement, status: Element | null) {
  window.clearTimeout(hook.copyFeedbackTimer)
  if (hook.copyAnnouncementFrame !== undefined) window.cancelAnimationFrame(hook.copyAnnouncementFrame)
  delete words.dataset.copyState
  if (status) status.textContent = ""
}

function announceCopyStatus(hook: CopyHook, status: Element | null, message: string) {
  if (!status) return
  hook.copyAnnouncementFrame = window.requestAnimationFrame(() => {
    status.textContent = message
  })
}

function scheduleCopyFeedbackReset(hook: CopyHook, words: HTMLElement, status: Element | null, delay: number) {
  hook.copyFeedbackTimer = window.setTimeout(() => {
    delete words.dataset.copyState
    if (status) status.textContent = ""
  }, delay)
}

const COPIED_MESSAGE = "Page copied as Markdown."
const FAILED_MESSAGE = "Couldn't copy. Use View as Markdown to open the Markdown, then copy it manually."

// "Copy page" copies Markdown built from the page itself when pressed, so it
// keeps this step; every other copy control is `Regent.Primitives.copy_button`.
// Its words are all on the page, stacked (TechtreeWeb.PageCopy); this shows
// "Copied" or "Couldn't copy" for a moment by setting `data-copy-state` on them.
// `refuse` answers a copy that could not happen, beside the words that say so.
export function mountPageCopyButton(
  hook: CopyHook,
  copyValue: () => string,
  {refuse, writeText = value => navigator.clipboard.writeText(value)}: CopyOptions,
) {
  hook.el.addEventListener("click", async () => {
    if (hook.copyInFlight) return
    hook.copyInFlight = true

    const words = hook.el.querySelector<HTMLElement>("[data-copy-words]")!
    const status = copyStatusFor(hook.el)
    resetCopyFeedback(hook, words, status)

    try {
      await writeText(copyValue())
      words.dataset.copyState = "copied"
      announceCopyStatus(hook, status, COPIED_MESSAGE)
      scheduleCopyFeedbackReset(hook, words, status, 1800)
    } catch (_error) {
      words.dataset.copyState = "failed"
      refuse(hook.el)
      announceCopyStatus(hook, status, FAILED_MESSAGE)
      scheduleCopyFeedbackReset(hook, words, status, 4000)
    } finally {
      hook.copyInFlight = false
    }
  })
}
