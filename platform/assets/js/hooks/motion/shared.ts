/**
 * What all of Techtree's motion shares: the design system's timings and
 * curves, the two questions asked before anything moves, and how a motion
 * hands its element back to the stylesheet.
 */
import {animate, cubicBezier, utils, type AnimationParams, type JSAnimation} from "animejs"

export const BASE = 200
export const SLOW = 280

export const EASE_OUT = cubicBezier(0.23, 1, 0.32, 1)

// The reader asked for less motion in their system settings.
export function still() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches
}

// A click from Enter or Space reports no pointer presses. Keyboard-driven UI
// answers at once rather than animating.
export function byPointer(event: MouseEvent) {
  return event.detail > 0
}

// The motions playing on each element since it was last at rest. A motion
// that catches another part-way remembers that part-way look as where it
// began, so the element is only tidied once the last of them has ended, and
// the first of them is tidied last: its record is the element at rest.
const runs = new WeakMap<Element, JSAnimation[]>()

// Moves one element and, once nothing else is moving it, leaves it exactly as
// its stylesheet draws it.
export function move(el: Element, params: AnimationParams) {
  const animation = animate(el, {
    ...params,
    onComplete: () => {
      params.onComplete?.(animation)
      settle(el)
    },
  })
  runs.set(el, [...(runs.get(el) ?? []), animation])
  return animation
}

// Puts an element back at rest at once, whatever is moving it.
export function halt(el: Element) {
  const run = runs.get(el) ?? []
  runs.delete(el)
  for (const animation of [...run].reverse()) animation.revert()
}

function settle(el: Element) {
  const run = runs.get(el)
  if (run === undefined || run.some(animation => !animation.completed && !animation.cancelled)) return
  runs.delete(el)
  for (const animation of [...run].reverse()) utils.cleanInlineStyles(animation)
}
