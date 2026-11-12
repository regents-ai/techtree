/**
 * One value card's moving panel (`value_cards/renderer.ts`) on the canvas
 * island. The card names its panel in `data-value-card`, and the panel brings
 * its own colours. A mouse over the card steers the pattern. A visitor who
 * asked for less motion, or whose browser cannot draw it, keeps the still frame
 * the server put there.
 */
import {createCanvasIsland, type CanvasIslandController} from "../canvas_island"
import type {ValueCardRenderer} from "../value_cards/renderer"

type ValueCardHook = {el: HTMLElement; island?: CanvasIslandController}

export const ValueCard = {
  mounted(this: ValueCardHook) {
    const card = this.el
    const name = card.dataset.valueCard!

    this.island = createCanvasIsland<ValueCardRenderer>(card, {}, {
      canvasSelector: "[data-value-card-canvas]",
      readyFlag: "valueCardReady",
      motionSensitive: true,
      continuous: true,
      browserLoad: async (canvas, size, onDeviceLost) => {
        const {createValueCardRenderer} = await import("../value_cards/renderer")
        return createValueCardRenderer(canvas, size, onDeviceLost, name)
      },
      interact({canvas, renderer}) {
        const events = new AbortController()
        const options = {passive: true, signal: events.signal}
        card.addEventListener("pointermove", (event: PointerEvent) => {
          if (event.pointerType !== "mouse") return
          const {left, top, width, height} = canvas().getBoundingClientRect()
          const across = (place: number, length: number) => Math.min(1, Math.max(0, place / length))
          renderer()?.point([across(event.clientX - left, width), across(event.clientY - top, height)])
        }, options)
        card.addEventListener("pointerleave", () => renderer()?.point(null), options)
        return () => events.abort()
      },
    })
    this.island.mount()
  },
  disconnected(this: ValueCardHook) {
    this.island?.pause()
  },
  reconnected(this: ValueCardHook) {
    this.island?.resume()
  },
  destroyed(this: ValueCardHook) {
    this.island?.destroy()
  },
}
