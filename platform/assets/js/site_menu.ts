/**
 * The header's Services menu and its Menu sheet (`TechtreeWeb.Layouts`). Each
 * is a popover its button opens: the browser closes it on Escape or a press
 * outside, and puts its links next in the Tab order. What is left is done here:
 *
 * - A menu opened by a mouse or a finger drops in and its columns follow one
 *   after another; one opened from the keyboard is simply there.
 * - Below a wide screen the menu and links are one sheet under the header
 *   (#site-menu). While it is open the page and its footer are out of reach:
 *   every part of the frame but the header goes inert until it closes, so Tab
 *   and a press can't land on a link behind it.
 * - A screen that crosses the wide line closes whatever it no longer shows.
 */
import {stagger} from "animejs"
import {BASE, EASE_OUT, SLOW, lastInputByPointer, play, still} from "./hooks/motion/shared"

const WIDE = "(min-width: 64rem)"

export function installSiteMenu() {
  const wideScreen = window.matchMedia(WIDE)
  wideScreen.addEventListener("change", () => {
    const hidden = wideScreen.matches ? "#site-menu" : "[data-mega]"
    for (const panel of document.querySelectorAll<HTMLElement>(`${hidden}:popover-open`)) panel.hidePopover()
  })

  document.addEventListener("beforetoggle", arrive, true)

  document.addEventListener("toggle", event => {
    if (!(event.target instanceof HTMLElement) || event.target.id !== "site-menu") return
    const open = (event as ToggleEvent).newState === "open"
    for (const part of document.querySelectorAll<HTMLElement>(".techtree-frame > :not(.masthead)")) {
      part.inert = open
    }
  }, true)
}

// Started before the panel is first drawn, so its first frame is already the
// start of the move.
function arrive(event: Event) {
  const {target} = event
  if (!(event instanceof ToggleEvent) || !(target instanceof HTMLElement)) return
  if (event.newState !== "open" || !lastInputByPointer() || still(target)) return
  if (!target.matches("[data-mega], #site-menu")) return

  play(target, {opacity: {from: 0}, y: {from: -8}, duration: BASE, ease: EASE_OUT})
  const parts = [...target.querySelectorAll(".menu-columns__column, .sheet__links, .sheet__end")]
  play(parts, {opacity: {from: 0}, y: {from: 8}, delay: stagger(35, {start: 40}), duration: SLOW, ease: EASE_OUT})
}
