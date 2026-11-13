/**
 * One of the home page's moving pictures (`field.ts`) on the canvas island.
 * The root names its scene in `data-field` and, for the dot screen, the shape
 * it draws in `data-field-shape`; its stylesheet gives the colours as
 * `--field-ground`, `--field-ink` and `--field-glow`, so a theme turning
 * repaints it. A mouse over the root steers the picture. A visitor who asked
 * for less motion, or whose browser cannot draw it, keeps the still picture
 * the stylesheet draws under the canvas.
 */
import {createCanvasIsland, type CanvasIslandController} from "../canvas_island"
import type {FieldRenderer} from "./field"
import type {Colours, Scene} from "./scenes"

type FieldHook = {el: HTMLElement; island?: CanvasIslandController}

const colours = (root: HTMLElement): Colours => {
  const style = getComputedStyle(root)
  const read = (name: string) => style.getPropertyValue(name).trim()
  return {ground: read("--field-ground"), ink: read("--field-ink"), glow: read("--field-glow")}
}

export const MarketingField = {
  mounted(this: FieldHook) {
    const root = this.el
    const scene = root.dataset.field as Scene

    this.island = createCanvasIsland<FieldRenderer>(root, {}, {
      canvasSelector: "[data-field-canvas]",
      readyFlag: "fieldReady",
      motionSensitive: true,
      continuous: true,
      browserLoad: async (canvas, size, onDeviceLost) => {
        const {createFieldRenderer} = await import("./field")
        return createFieldRenderer(canvas, size, onDeviceLost, scene, colours(root), Number(root.dataset.fieldShape ?? 0))
      },
      interact({canvas, renderer}) {
        const events = new AbortController()
        const options = {passive: true, signal: events.signal}
        root.addEventListener("pointermove", (event: PointerEvent) => {
          if (event.pointerType !== "mouse") return
          const {left, top, width, height} = canvas().getBoundingClientRect()
          const across = (place: number, length: number) => Math.min(1, Math.max(0, place / length))
          renderer()?.point([across(event.clientX - left, width), across(event.clientY - top, height)])
        }, options)
        root.addEventListener("pointerleave", () => renderer()?.point(null), options)

        // The theme turned, by the switch or by the device: the picture takes the new colours.
        const repaint = () => renderer()?.paint(colours(root))
        const theme = new MutationObserver(repaint)
        theme.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]})
        const scheme = matchMedia("(prefers-color-scheme: dark)")
        scheme.addEventListener("change", repaint, {signal: events.signal})

        return () => {
          events.abort()
          theme.disconnect()
        }
      },
    })
    this.island.mount()
  },
  disconnected(this: FieldHook) {
    this.island?.pause()
  },
  reconnected(this: FieldHook) {
    this.island?.resume()
  },
  destroyed(this: FieldHook) {
    this.island?.destroy()
  },
}
