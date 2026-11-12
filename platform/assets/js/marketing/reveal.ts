/**
 * The home page arriving: the hero's parts as the page opens, and each
 * section's heading the first time it scrolls into view. Nothing is hidden
 * before it moves, so a visitor who asked for less motion, or whose script
 * never ran, sees the whole page as the server drew it.
 */
import {createScope, splitText, stagger, type Scope} from "animejs"
import {onFirstSight} from "../hooks/motion/reveals"
import {CLIPPED_WORD, EASE_OUT, SLOW, play, still} from "../hooks/motion/shared"

/**
 * The hero as the page opens: the news line drops in, the headline's words
 * rise one after another, then the rest settles in below it. It runs on the
 * page as the server sent it, before the live connection joins, so its
 * headline is `phx-update="ignore"`: the join leaves the risen words alone.
 */
export function mountEntrance(doc: Document) {
  const hero = doc.querySelector<HTMLElement>("[data-entrance]")
  if (hero === null || still(hero)) return

  const news = hero.querySelector("[data-entrance-news]")
  if (news) play(news, {opacity: {from: 0}, y: {from: -8}, duration: SLOW, ease: EASE_OUT})

  const display = hero.querySelector<HTMLElement>("[data-entrance-display]")
  if (display) {
    const split = splitText(display, {words: CLIPPED_WORD})
    play(split.words, {y: ["100%", "0%"], delay: stagger(70, {start: 80}), duration: 640, ease: EASE_OUT})
      .then(() => split.revert())
  }

  const parts = [...hero.querySelectorAll("[data-entrance-part]")]
  if (parts.length) play(parts, {opacity: {from: 0}, y: {from: 12}, delay: stagger(90, {start: 380}), duration: 560, ease: EASE_OUT})
}

type RiseHook = {el: HTMLElement; scope?: Scope}

/**
 * A section heading whose words rise into place the first time it scrolls
 * into view. The heading is `phx-update="ignore"`, so the page never redraws
 * it while its words are apart.
 */
export const MarketingRise = {
  mounted(this: RiseHook) {
    const heading = this.el
    const scope = createScope({root: heading})
    this.scope = scope.add(() =>
      onFirstSight(heading, () => {
        if (still(heading)) return
        const split = splitText(heading, {words: CLIPPED_WORD})
        play(split.words, {y: ["100%", "0%"], delay: stagger(60), duration: 560, ease: EASE_OUT})
          .then(() => split.revert())
      }))
  },
  destroyed(this: RiseHook) {
    this.scope?.revert()
  },
}
