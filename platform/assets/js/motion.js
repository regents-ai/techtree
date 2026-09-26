/**
 * Techtree's standard motion on every page: a squish when something is
 * pressed, and the page's headline rising in word by word.
 *
 * A live page draws its own parts again as it joins and whenever it changes,
 * which would wipe a moving headline part-way, so only a page the server drew
 * once has its headline rise; live lists move from their hooks.
 */
import {splitText} from "animejs"
import {byPointer, still} from "./hooks/motion/shared.js"
import {squish} from "./hooks/motion/press.js"
import {HEADLINES} from "./hooks/motion/reveals.js"

const PRESSABLE = "button, .rg-button, [role='button']"

const live = el => el.closest("[data-phx-session]") !== null

export function mountMotion(doc = document) {
  doc.addEventListener("click", press)

  const main = doc.querySelector("main")
  if (main === null || live(main) || still()) return

  const headline = main.querySelector("h1")
  if (headline !== null) rise(headline)
}

function press(event) {
  const el = event.target.closest(PRESSABLE)
  if (el === null || !byPointer(event) || still()) return
  squish(el)
}

// The words are joined back into plain text once they have risen.
function rise(headline) {
  const split = splitText(headline, {words: {wrap: "clip"}})
  HEADLINES.rise(split).then(() => split.revert())
}
