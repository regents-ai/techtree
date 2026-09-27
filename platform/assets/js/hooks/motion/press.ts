/**
 * Answers to a press. The control still does its job the instant it is
 * pressed, wallet buttons included; the motion only plays alongside it. Both
 * end where they began, then hand the element back to its stylesheet, so a
 * hover style that moves it still can. One pressed again mid-move starts over
 * from rest.
 */
import {play, still} from "./shared"

export const squish = (el: Element) =>
  play(el, {scale: [{to: 0.9, duration: 90, ease: "out(3)"}, {to: 1, duration: 360, ease: "outBack(3)"}]})

export const nope = (el: Element) =>
  play(el, {x: [0, -7, 6, -4, 2, 0], duration: 380, ease: "inOut(2)"})

// Something was refused. Unlike a press, the shake plays however the refused
// thing was asked for, because it is the answer, not decoration.
export function deny(el: Element) {
  if (!still(el)) nope(el)
}
