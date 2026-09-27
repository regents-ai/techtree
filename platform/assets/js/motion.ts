/**
 * Techtree's standard motion on every page: a squish when something is
 * pressed, and the page's headline rising in word by word.
 *
 * A live page draws its own parts again as it joins and whenever it changes,
 * which would wipe a moving headline part-way, so only a page the server drew
 * once has its headline rise; live lists move from their hooks.
 */
import {splitText} from "animejs"
import {byPointer, still} from "./hooks/motion/shared"
import {squish} from "./hooks/motion/press"
import {HEADLINES} from "./hooks/motion/reveals"

const PRESSABLE = "button, .rg-button, [role='button']"

const live = (el: Element) => el.closest("[data-phx-session]") !== null

export function mountMotion(doc: Document = document) {
  doc.addEventListener("click", press)

  const main = doc.querySelector("main")
  if (main === null || live(main) || still()) return

  const headline = main.querySelector("h1")
  if (headline !== null) rise(headline)
}

function press(event: MouseEvent) {
  const el = (event.target as Element).closest(PRESSABLE)
  if (el === null || !byPointer(event) || still()) return
  squish(el)
}

// The words are joined back into plain text once they have risen.
function rise(headline: HTMLElement) {
  const split = splitText(headline, {words: {wrap: "clip"}})
  HEADLINES.rise(split).then(() => split.revert())
}
