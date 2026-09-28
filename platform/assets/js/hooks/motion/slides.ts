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
import {BASE, EASE_OUT, SLOW, lastInputByPointer, play, still} from "./shared"
import type {Hook} from "../../hook_composition"

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

// How each kind of panel, named in `data-panel`, moves when it opens.
const PANELS: Record<string, (el: Element) => unknown> = {drawer, sheet, menu}

type PanelsHook = {el: HTMLElement; watch?: MutationObserver}

/**
 * An island whose panels, each marked `data-panel`, are opened by LiveView
 * commands rather than by a press the page follows, such as a menu a button
 * opens with `JS.show`. A command acts only after the press has reached the
 * document, so this watches each panel's `hidden` go and moves it then, when
 * the reader was last using a mouse or a finger.
 */
export const MotionPanels: Hook = {
  mounted(this: PanelsHook) {
    const panels = () => [...this.el.querySelectorAll<HTMLElement>("[data-panel]")]
    const open = new Set(panels().filter(el => !el.hidden))

    this.watch = new MutationObserver(() => {
      for (const el of panels()) {
        if (el.hidden) open.delete(el)
        if (el.hidden || open.has(el)) continue
        open.add(el)
        if (lastInputByPointer() && !still(el)) PANELS[el.dataset.panel ?? ""](el)
      }
    })
    this.watch.observe(this.el, {subtree: true, attributes: true, attributeFilter: ["hidden"]})
  },

  destroyed(this: PanelsHook) {
    this.watch?.disconnect()
  },
}
