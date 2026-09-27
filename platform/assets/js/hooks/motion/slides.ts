/**
 * Panels that open over the page: the phone menu slides out as a drawer, a
 * dialog rises as a sheet and a header menu pops under its button. The page
 * opens and closes them itself; this only moves a panel from where it starts
 * to where it rests, then hands it back to its stylesheet. Closing is
 * immediate.
 *
 * Moves in percent name both ends, so they stay a share of the panel's own
 * size instead of being converted to pixels.
 */
import {spring} from "animejs"
import {BASE, EASE_OUT, SLOW, play} from "./shared"

// The phone menu sits against the left edge, so its drawer comes from there.
export const drawer = (el: Element) =>
  play(el, {x: ["-100%", "0%"], ease: spring({bounce: 0.3, duration: 380})})

export const sheet = (el: Element) =>
  play(el, {y: ["100%", "0%"], ease: spring({bounce: 0.35, duration: 400})})

export const menu = (el: Element) =>
  play(el, {
    y: {from: -6},
    scale: {from: 0.9},
    opacity: {from: 0},
    duration: SLOW,
    ease: "outBack(2.2)",
  })

export const backdrop = (el: Element) =>
  play(el, {opacity: {from: 0}, duration: BASE, ease: EASE_OUT})
