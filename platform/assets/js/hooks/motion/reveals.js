/**
 * Motion for a page arriving: a headline that rises in word by word.
 */
import {animate, stagger} from "animejs"
import {EASE_OUT, SLOW} from "./shared.js"

// Moves in percent name both ends, so they stay a share of each piece's own
// height instead of being converted to pixels from its width.
export const HEADLINES = {
  rise: split =>
    animate(split.words, {y: ["100%", "0%"], delay: stagger(50), duration: SLOW, ease: EASE_OUT}),
}
