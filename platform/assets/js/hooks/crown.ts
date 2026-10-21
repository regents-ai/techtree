import {
  createCanvasIsland,
  type CanvasIslandController,
  type CanvasIslandOptions,
  type LoadRenderer,
  type MediaQuery,
} from "../canvas_island"
import type {CrownRenderer} from "../crown"
import type {CrownVariant} from "../crown/crown-types"

export type CrownOptions = CanvasIslandOptions<CrownRenderer> & {
  /** The crown for the theme the page is showing now. */
  variant: () => CrownVariant
  pointerQuery?: () => MediaQuery
  viewportHeight?: () => number
}

export type CrownController = CanvasIslandController & {
  /** Draws the crown again when the theme showing asks for the other one. */
  restyle(): void
}

const browserLoadCrown =
  (variant: () => CrownVariant): LoadRenderer<CrownRenderer> =>
  async (canvas, size, onDeviceLost) => {
    const {createCrownRenderer} = await import("../crown")
    return createCrownRenderer(canvas, size, onDeviceLost, variant())
  }

const clampUnit = (value: number): number => Math.min(1, Math.max(0, value))

/**
 * The homepage crown: thirteen glass cubes and a beam of light, drawn on the
 * island's canvas behind the hero.
 *
 * The island takes no pointer events itself, so the pointer is read from the hero
 * it decorates: it turns the camera a little and swings the light. A touch is not a
 * hover, so on a phone a touch sets where the crown looks across, and how far the
 * hero has travelled up the screen sets where it looks down.
 *
 * A visitor who asked for less motion gets the crown as one composed shot: it is
 * drawn, and then left alone. Without WebGPU nothing is drawn, and the still
 * picture the server rendered stays.
 */
export const createCrownController = (
  root: HTMLElement,
  options: CrownOptions,
): CrownController => {
  const pointerQuery =
    options.pointerQuery ?? (() => window.matchMedia("(hover: hover) and (pointer: fine)"))
  const viewportHeight = options.viewportHeight ?? (() => window.innerHeight)
  const motionQuery =
    options.motionQuery ?? (() => window.matchMedia("(prefers-reduced-motion: reduce)"))
  let paused = false

  const island = createCanvasIsland(root, options, {
    canvasSelector: "[data-crown-canvas]",
    readyFlag: "crownReady",
    browserLoad: browserLoadCrown(options.variant),
    motionSensitive: false,
    continuous: false,
    interact({root: layer, canvas, renderer, nudge, onReady}) {
      const stage = () => layer.parentElement!
      const fine = pointerQuery().matches
      const calm = motionQuery()
      let acrossX = 0.5

      const onPointerMove = (event: PointerEvent) => {
        if (event.isPrimary === false) return
        const current = renderer()
        if (!current) return
        const {left, top, width, height} = canvas().getBoundingClientRect()
        if (width <= 0 || height <= 0) return
        const x = clampUnit((event.clientX - left) / width)
        const y = clampUnit((event.clientY - top) / height)
        if (!fine || event.pointerType === "touch") acrossX = x
        current.aim(x, y)
        nudge()
      }
      const onPointerLeave = () => {
        renderer()?.rest()
        nudge()
      }
      const onScroll = () => {
        const current = renderer()
        if (!current) return
        const {top, height} = canvas().getBoundingClientRect()
        const travel = viewportHeight() + height
        if (travel <= 0) return
        current.aim(acrossX, clampUnit((viewportHeight() - top) / travel))
        nudge()
      }
      const onThemeChange = () => {
        const current = renderer()
        if (current && current.variant !== options.variant()) restyle()
      }

      const follow = () => {
        stage().addEventListener("pointerdown", onPointerMove, {passive: true})
        stage().addEventListener("pointermove", onPointerMove, {passive: true})
        stage().addEventListener("pointerleave", onPointerLeave, {passive: true})
        if (!fine) document.addEventListener("scroll", onScroll, {passive: true})
      }
      const unfollow = () => {
        stage().removeEventListener("pointerdown", onPointerMove)
        stage().removeEventListener("pointermove", onPointerMove)
        stage().removeEventListener("pointerleave", onPointerLeave)
        document.removeEventListener("scroll", onScroll)
      }
      const onCalmChange = () => {
        unfollow()
        onPointerLeave()
        if (!calm.matches) follow()
      }

      if (!calm.matches) follow()
      calm.addEventListener("change", onCalmChange)
      document.addEventListener("techtree:themechange", onThemeChange)
      onReady(() => {
        // The theme may have changed while this crown was on its way.
        if (renderer()!.variant !== options.variant()) return restyle()
        // The visitor may arrive part-way down the page, so the first shot is
        // composed for where the hero already is.
        if (!fine && !calm.matches) onScroll()
      })

      return () => {
        calm.removeEventListener("change", onCalmChange)
        document.removeEventListener("techtree:themechange", onThemeChange)
        unfollow()
      }
    },
  })

  // Each theme has its own crown, built whole, so a crown already drawn for the
  // other theme is put away and the right one drawn in its place, once the island
  // has finished whatever it was doing when the theme changed.
  const restyle = () => {
    queueMicrotask(() => {
      island.destroy()
      island.mount()
      if (paused) island.pause()
    })
  }

  return {
    ...island,
    pause() {
      paused = true
      island.pause()
    },
    resume() {
      paused = false
      island.resume()
    },
    restyle,
  }
}

type CrownHook = {
  el: HTMLElement
  controller?: CrownController
}

/** The `Crown` hook, drawing the crown for the theme `variant` names. */
export const crownHook = (variant: () => CrownVariant) => ({
  mounted(this: CrownHook) {
    this.controller = createCrownController(this.el, {variant})
    this.controller.mount()
  },
  disconnected(this: CrownHook) {
    this.controller?.pause()
  },
  reconnected(this: CrownHook) {
    this.controller?.resume()
  },
  destroyed(this: CrownHook) {
    this.controller?.destroy()
    this.controller = undefined
  },
})
