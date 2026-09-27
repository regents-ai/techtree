/**
 * Motion for a page arriving: a headline that rises in word by word.
 */
import {animate, stagger, type TextSplitter} from "animejs"
import {EASE_OUT, SLOW} from "./shared"

// Moves in percent name both ends, so they stay a share of each piece's own
// height instead of being converted to pixels from its width.
export const HEADLINES = {
  rise: (split: TextSplitter) =>
    animate(split.words, {y: ["100%", "0%"], delay: stagger(50), duration: SLOW, ease: EASE_OUT}),
}
