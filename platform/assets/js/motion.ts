/**
 * The standard motion on every page: a squish when something is pressed, a
 * shake when the answer is no, panels that slide or pop open, and on pages the
 * server draws once, the headline rising in word by word and the cards
 * settling into place. The version of each is named in `TechtreeWeb.Motion`
 * and every version that was tried is kept in the template's motion lab at
 * /animations.
 *
 * A live page draws its own parts again whenever it changes, so only what the
 * server drew once moves as the page opens; live parts move from their hooks.
 *
 * Nothing here waits for, stops or repeats a press: a wallet button reaches
 * the wallet the moment it is pressed, and the motion plays alongside.
 */
import {splitText} from "animejs"
import {deny, nope, squish} from "./hooks/motion/press"
import {GRIDS, HEADLINES} from "./hooks/motion/reveals"
import {CLIPPED_WORD, byPointer, lastInputByPointer, still, watchInput} from "./hooks/motion/shared"
import {backdrop, drawer, menu, sheet} from "./hooks/motion/slides"

// A menu's summary is its button; other summaries open disclosures in the
// page's own flow and stay still. The theme switch turns its own cube, and the
// lab's presses, named with `data-press`, answer for themselves.
const PRESSABLE =
  ":is(button, .rg-button, [role='button'], summary:has(~ [data-panel='menu'])):not(.rg-theme-toggle, [data-press])"

// The first cards of a list cascade in; later ones start below the fold and
// are simply there.
const CASCADE = 12

const live = (el: Element) => el.closest("[data-phx-session]") !== null

export function mountMotion(doc: Document) {
  watchInput(doc)
  doc.addEventListener("click", press)
  doc.addEventListener("toggle", toggle, true)

  const main = doc.querySelector("main")
  if (main === null || live(main) || still(main)) return

  const headline = main.querySelector<HTMLElement>("h1")
  if (headline !== null) rise(headline)

  for (const list of main.querySelectorAll("[data-cascade]")) GRIDS.cascade([...list.children].slice(0, CASCADE))

  // A form the server sent back refused says why, and the reason shakes once.
  for (const reason of main.querySelectorAll("[role='alert']")) deny(reason)
}

// By the time a press reaches the document, the page has already acted on
// it, so a control that opens a drawer says it is open. A button that says it
// cannot be used yet shakes its head instead of squishing. A wallet button
// squishes only its `data-press-label`, so the button itself never shrinks
// and a quick second press near its edge still lands on it.
export function press(event: MouseEvent) {
  if (!(event.target instanceof Element) || !byPointer(event)) return
  const control = event.target.closest(PRESSABLE)
  if (control === null || still(control)) return

  if (control.getAttribute("aria-disabled") === "true") {
    nope(control)
    return
  }

  squish(control.querySelector("[data-press-label]") ?? control)

  if (control.getAttribute("aria-expanded") !== "true") return
  const panel = event.target.ownerDocument.getElementById(control.getAttribute("aria-controls") ?? "")
  if (panel?.dataset.panel !== "drawer") return

  drawer(panel)
  const shade = panel.parentElement?.querySelector(":scope > [data-backdrop]")
  if (shade) backdrop(shade)
}

// A dialog rises as a sheet and a header menu pops open. A page that redraws
// an open one closes and reopens it within one moment, which reports it as
// having been open all along, so it does not move again.
function toggle(event: Event) {
  if (!(event instanceof ToggleEvent) || event.oldState !== "closed" || event.newState !== "open") return
  const {target} = event
  if (!(target instanceof HTMLElement) || !lastInputByPointer() || still(target)) return

  if (target instanceof HTMLDialogElement) sheet(target)
  if (target instanceof HTMLDetailsElement) {
    const panel = target.querySelector(":scope > [data-panel='menu']")
    if (panel) menu(panel)
  }
}

// The words are joined back into plain text once they have risen.
function rise(headline: HTMLElement) {
  const split = splitText(headline, {words: CLIPPED_WORD})
  HEADLINES.rise(split).then(() => split.revert())
}
