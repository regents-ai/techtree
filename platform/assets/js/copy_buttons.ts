import {deny} from "./hooks/motion/press"

type Outcome = "copied" | "selected" | "failed"

const WORDS: Record<Outcome, string> = {copied: "Copied", selected: "Selected", failed: "Couldn't copy"}
const SHOWN_MS = 1600

const timers = new WeakMap<HTMLElement, number>()

/**
 * Every `Regent.Primitives.copy_button` on every page, LiveView or not, from one
 * listener on the document. A press copies the button's `data-copy-text`, or the
 * text of the element `data-copy-target` names, then for a moment the button
 * says "Copied", or "Couldn't copy" with a shake when the browser refuses, and
 * its polite status says the same for screen readers. When the browser refuses
 * and there is a target, the target's text is selected for the person to copy
 * themselves and the button says "Selected". The button tells LiveView to leave
 * `data-copy-state` alone, so a redraw meanwhile keeps the answer on screen.
 */
export function installCopyButtons() {
  document.addEventListener("click", event => {
    const button = event.target instanceof Element ? event.target.closest("button.rg-copy") : null
    if (button instanceof HTMLButtonElement) void copy(button)
  })
}

async function copy(button: HTMLButtonElement) {
  const targetId = button.dataset.copyTarget
  const target = targetId ? document.getElementById(targetId) : null
  let outcome: Outcome = "copied"
  try {
    await navigator.clipboard.writeText(target ? textOf(target) : (button.dataset.copyText ?? ""))
  } catch {
    outcome = target ? select(target) : "failed"
  }
  if (!button.isConnected) return

  answer(button, outcome)
  if (outcome === "failed") deny(button)
  window.clearTimeout(timers.get(button))
  timers.set(button, window.setTimeout(() => answer(button, undefined), SHOWN_MS))
}

function textOf(target: HTMLElement): string {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
    ? target.value
    : (target.textContent ?? "")
}

// A field selects its own text; anything else, like a prompt shown on the page,
// is selected as a range.
function select(target: HTMLElement): Outcome {
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    target.focus()
    target.select()
    return "selected"
  }

  const selection = document.getSelection()
  if (!selection) return "failed"
  const range = document.createRange()
  range.selectNodeContents(target)
  selection.removeAllRanges()
  selection.addRange(range)
  return "selected"
}

function answer(button: HTMLButtonElement, outcome: Outcome | undefined) {
  if (outcome) button.dataset.copyState = outcome
  else delete button.dataset.copyState
  const status = document.getElementById(button.dataset.copyStatus ?? "")
  if (status) status.textContent = outcome ? WORDS[outcome] : ""
}
