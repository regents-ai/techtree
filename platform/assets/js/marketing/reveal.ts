/**
 * A marketing page arriving: its opening band's parts as the page opens, and
 * each row of tiles the first time it scrolls into view. Nothing is hidden
 * before it moves, so a visitor who asked for less motion, or whose script
 * never ran, sees the whole page as the server drew it.
 */
import {createScope, splitText, stagger, type Scope} from "animejs"
import {onFirstSight} from "../hooks/motion/reveals"
import {CLIPPED_WORD, EASE_OUT, play, still} from "../hooks/motion/shared"

/**
 * The opening band as the page opens: the headline's words rise one after
 * another, then the rest settles in below it. It runs on the page as the
 * server sent it, before the live connection joins, so its headline is
 * `phx-update="ignore"`: the join leaves the risen words alone.
 */
export function mountEntrance(doc: Document) {
  const hero = doc.querySelector<HTMLElement>("[data-entrance]")
  if (hero === null || still(hero)) return

  const display = hero.querySelector<HTMLElement>("[data-entrance-display]")
  if (display) {
    const split = splitText(display, {words: CLIPPED_WORD})
    play(split.words, {y: ["100%", "0%"], delay: stagger(70, {start: 80}), duration: 640, ease: EASE_OUT})
      .then(() => split.revert())
  }

  const parts = [...hero.querySelectorAll("[data-entrance-part]")]
  if (parts.length) play(parts, {opacity: {from: 0}, y: {from: 12}, delay: stagger(90, {start: 380}), duration: 560, ease: EASE_OUT})
}

type StaggerHook = {el: HTMLElement; scope?: Scope}

/**
 * A row of tiles (`data-stagger`) that rise in one after another, from the
 * row's middle outwards, the first time the row scrolls into view. The row is
 * `phx-update="ignore"`, so the page never redraws a tile while it moves.
 */
export const MarketingStagger = {
  mounted(this: StaggerHook) {
    const row = this.el
    const scope = createScope({root: row})
    this.scope = scope.add(() =>
      onFirstSight(row, () => {
        if (still(row)) return
        const tiles = [...row.querySelectorAll("[data-stagger]")]
        play(tiles, {opacity: {from: 0}, y: {from: 18}, delay: stagger(55, {from: "center"}), duration: 620, ease: EASE_OUT})
      }))
  },
  destroyed(this: StaggerHook) {
    this.scope?.revert()
  },
}
