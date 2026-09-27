/**
 * Small answers to a mouse or finger press. The button still does its job the
 * instant it is pressed; the motion only plays alongside it. A press from the
 * keyboard, or a reader who asked for less motion, gets no motion at all.
 *
 * Squish is the standard press, played on every page from `motion.ts`; nope is
 * the standard answer when something is refused.
 */
import {move, still} from "./shared"

// Both end where they began and hand the element back to its stylesheet. One
// pressed again mid-move starts over from wherever it is.
export const squish = (el: Element) =>
  move(el, {scale: [{to: 0.9, duration: 90, ease: "out(3)"}, {to: 1, duration: 360, ease: "outBack(3)"}]})

export const nope = (el: Element) => move(el, {x: [0, -7, 6, -4, 2, 0], duration: 380, ease: "inOut(2)"})

// Something was refused. Unlike a press, the shake plays however the refused
// thing was asked for, because it is the answer, not decoration.
export function deny(el: Element) {
  if (!still()) nope(el)
}
