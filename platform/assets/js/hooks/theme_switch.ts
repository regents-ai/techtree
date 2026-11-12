/**
 * The light and dark theme switch (`TechtreeWeb.Components.ThemeSwitch.theme_switch/1`).
 *
 * The switch is a real button with the role of a switch: on is the light theme.
 * Everything it does lives here and works with or without WebGPU and whatever
 * the motion setting: a press, Enter or Space turns it; dragging the knob
 * sideways moves it under the finger and, on release, it settles on the nearer
 * side. The theme changes once, when the switch is turned or released, never
 * part-way through a drag.
 *
 * The knob's position is one number, p: 0 at night (dark) on the left, 1 by day
 * (light) on the right. The still face the server drew reads it from
 * `--theme-switch-p`; the GPU picture (theme_switch/renderer.ts, inside the
 * shared canvas island) reads it with the swarm of blocks the knob scrubs. Every
 * move of the knob is Anime.js: an Animatable carries it when it settles, and
 * the swarm is a paused timeline seeked to it (theme_switch/morph.ts).
 *
 * The blocks are the server's: the still face draws the moon and the sun as
 * SVG squares, and the swarm is read from them, so both pictures have one source.
 *
 * Every switch on the page follows the theme on screen, whoever changed it, and
 * moves to match.
 */
import {createAnimatable, createScope, spring, type AnimatableObject} from "animejs"

import {createCanvasIsland, type CanvasIslandController} from "../canvas_island"
import {chooseTheme, showingTheme, watchTheme} from "../theme"
import {draggedPosition, isDrag, settleSide, sideOf, themeOf, type Side} from "../theme_switch/knob"
import {createMorph, PIXEL_STRIDE, type Morph} from "../theme_switch/morph"
import {pairByAngle, pixelsOf, type Cell, type Pair} from "../theme_switch/pixels"
import type {Rgb, SwitchPicture, ThemeSwitchRenderer} from "../theme_switch/renderer"
import {byPointer, lastInputByPointer, still} from "./motion/shared"

export type ThemeSwitchController = Pick<CanvasIslandController, "mount" | "pause" | "resume" | "destroy">

type Geometry = Pick<SwitchPicture, "width" | "height" | "track" | "lens">

type Pictures = {grid: number; pairs: readonly Pair[]}

type Press = {id: number; x: number; start: number; type: string; dragging: boolean; travel: number}

// How the knob settles after a release or a press: on a spring, played out
// within the 24 frames the canvas island gives an easing (400ms at 60 frames a second).
const SETTLE_MS = 400
const settling = spring({bounce: 0.2, duration: 300}).ease

/**
 * Any colour the page can state, as red, green and blue from 0 to 1, with its
 * opacity; nothing for a colour that paints nothing.
 */
function colourReader() {
  const canvas = document.createElement("canvas")
  canvas.width = 1
  canvas.height = 1
  const context = canvas.getContext("2d", {willReadFrequently: true})!
  return (css: string): {rgb: Rgb; opaque: boolean} | undefined => {
    context.clearRect(0, 0, 1, 1)
    context.fillStyle = "rgba(0, 0, 0, 0)"
    context.fillStyle = css
    context.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data
    if (a === 0) return undefined
    return {rgb: [r / 255, g / 255, b / 255], opaque: a === 255}
  }
}

/** One of the still face's pictures: its grid's side and its blocks. */
function readPicture(svg: SVGSVGElement): {grid: number; cells: Cell[]} {
  const grid = Number(svg.getAttribute("viewBox")!.trim().split(/[\s,]+/)[2])
  const cells = [...svg.querySelectorAll("rect")].map(rect => ({
    col: Number(rect.getAttribute("x")),
    row: Number(rect.getAttribute("y")),
  }))
  return {grid, cells}
}

/**
 * The moon and the sun as the server drew them in the still face, every block
 * of the moon paired with one of the sun. The server holds both on one grid with
 * as many blocks (`TechtreeWeb.Components.ThemeSwitch`, checked when it compiles).
 */
function readPictures(root: HTMLElement): Pictures {
  const moon = readPicture(root.querySelector<SVGSVGElement>("svg.theme-switch__moon")!)
  const sun = readPicture(root.querySelector<SVGSVGElement>("svg.theme-switch__sun")!)
  return {grid: moon.grid, pairs: pairByAngle(pixelsOf(moon.cells, moon.grid), pixelsOf(sun.cells, sun.grid))}
}

export function createThemeSwitch(root: HTMLElement): ThemeSwitchController {
  const button = root.querySelector<HTMLButtonElement>("[role='switch']")!
  const trackBox = root.querySelector<HTMLElement>("[data-theme-switch-track]")!
  const knobBox = root.querySelector<HTMLElement>("[data-theme-switch-knob]")!
  const canvas = root.querySelector<HTMLCanvasElement>("[data-theme-switch-canvas]")!
  const readColour = colourReader()
  const pictures = readPictures(root)

  // What Anime.js moves: the knob, between 0 and 1.
  const knob = {p: sideOf(showingTheme()) as number}
  let side: Side = sideOf(showingTheme())
  let morph: Morph | undefined
  let motion: AnimatableObject | undefined
  let geometry: Geometry = {width: 1, height: 1, track: {x: 0, y: 0, width: 1, height: 1}, lens: 1}
  let colours: SwitchPicture["colours"] | undefined
  const pixels = new Float32Array(pictures.pairs.length * PIXEL_STRIDE)
  let draw = () => {}
  let press: Press | undefined
  let swallowClick = false
  let connected = true

  const measure = () => {
    const box = canvas.getBoundingClientRect()
    const track = trackBox.getBoundingClientRect()
    // A menu dropping open scales what it holds for a moment; the picture keeps
    // to the layout's own sizes, as the canvas island does.
    const k = canvas.clientWidth > 0 && box.width > 0 ? box.width / canvas.clientWidth : 1
    geometry = {
      width: canvas.clientWidth || 1,
      height: canvas.clientHeight || 1,
      track: {
        x: (track.left - box.left) / k,
        y: (track.top - box.top) / k,
        width: track.width / k,
        height: track.height / k,
      },
      lens: knobBox.offsetWidth,
    }
  }

  // The page under the switch is the first ancestor that paints a solid
  // background; the beam is the switch's own two tokens (theme_switch.css).
  const readColours = (): SwitchPicture["colours"] => {
    let page: Rgb | undefined
    for (let el: Element | null = root; el && !page; el = el.parentElement) {
      const found = readColour(getComputedStyle(el).backgroundColor)
      if (found?.opaque) page = found.rgb
    }
    const style = getComputedStyle(root)
    const token = (name: string) => readColour(style.getPropertyValue(name).trim())!.rgb
    return {
      page: page ?? token("--color-bg"),
      ink: readColour(getComputedStyle(button).color)!.rgb,
      night: token("--theme-switch-night"),
      day: token("--theme-switch-day"),
    }
  }

  const picture = (): SwitchPicture => {
    morph?.seek(knob.p)
    morph?.write(pixels)
    colours ??= readColours()
    return {p: knob.p, ...geometry, grid: pictures.grid, pixels, count: pictures.pairs.length, colours}
  }

  // Shows the knob where it is now: the still face's knob and, when the GPU
  // draws, the picture.
  const render = () => {
    root.style.setProperty("--theme-switch-p", (Math.round(knob.p * 10000) / 10000).toString())
    draw()
  }

  const scope = createScope({root}).add(() => {
    morph = createMorph(pictures.pairs)
    motion = createAnimatable(knob, {p: 0, onUpdate: render})
  })

  const moveTo = (target: Side, animated: boolean) => {
    if (animated && !still(root)) {
      motion?.p(target, SETTLE_MS, settling)
    } else {
      motion?.p(target, 0, "linear")
      knob.p = target
      render()
    }
  }

  const announce = () => button.setAttribute("aria-checked", String(side === 1))

  /** Turns the switch to `next`, and the page with it. */
  const commit = (next: Side, animated: boolean) => {
    side = next
    announce()
    moveTo(next, animated)
    if (showingTheme() !== themeOf(next)) chooseTheme(themeOf(next))
  }

  const follow = watchTheme(theme => {
    colours = undefined
    const next = sideOf(theme)
    if (next === side) {
      render()
      return
    }
    side = next
    announce()
    if (!press?.dragging) moveTo(next, lastInputByPointer())
  })

  const onPointerDown = (event: PointerEvent) => {
    if (!event.isPrimary || event.button !== 0) return
    measure()
    swallowClick = false
    press = {
      id: event.pointerId,
      x: event.clientX,
      start: knob.p,
      type: event.pointerType,
      dragging: false,
      travel: geometry.track.width - geometry.lens,
    }
    try {
      button.setPointerCapture(event.pointerId)
    } catch {
      // A pointer that is already gone cannot be captured; its up event still ends the press.
    }
  }

  const onPointerMove = (event: PointerEvent) => {
    if (!press || event.pointerId !== press.id) return
    const dx = event.clientX - press.x
    if (!press.dragging) {
      if (!isDrag(dx, press.type)) return
      press.dragging = true
    }
    motion?.p(draggedPosition(press.start, dx, press.travel), 0, "linear")
    knob.p = draggedPosition(press.start, dx, press.travel)
    render()
  }

  const onPointerUp = (event: PointerEvent) => {
    if (!press || event.pointerId !== press.id) return
    const dragged = press.dragging
    press = undefined
    if (!dragged) return // The click that follows turns the switch.
    swallowClick = true
    commit(settleSide(knob.p), true)
  }

  // The browser took the press for a scroll: the knob goes back to its side.
  const onPointerCancel = (event: PointerEvent) => {
    if (!press || event.pointerId !== press.id) return
    const dragged = press.dragging
    press = undefined
    if (dragged) moveTo(side, true)
  }

  // A press turns the switch; so do Enter and Space, at once rather than
  // animated, as every keyboard-driven control here does.
  const onClick = (event: MouseEvent) => {
    if (swallowClick && byPointer(event)) {
      swallowClick = false
      event.preventDefault()
      return
    }
    swallowClick = false
    commit(side === 1 ? 0 : 1, byPointer(event))
  }

  const island = createCanvasIsland<ThemeSwitchRenderer>(root, {}, {
    canvasSelector: "[data-theme-switch-canvas]",
    readyFlag: "themeSwitchReady",
    motionSensitive: true,
    // Drawn only when the knob or the theme moves; nothing moves between.
    continuous: false,
    // A canvas this small costs nothing at the screen's full sharpness, and the
    // blocks only read as blocks there.
    maxDevicePixelRatio: 3,
    browserLoad: async (surface, size, lost) => {
      const {createThemeSwitchRenderer} = await import("../theme_switch/renderer")
      return createThemeSwitchRenderer(surface, size, lost)
    },
    interact: ({renderer, nudge, onReady}) => {
      draw = () => {
        const current = renderer()
        if (!current) return
        current.show(picture())
        nudge()
      }
      onReady(() => renderer()?.show(picture()))
      return () => {
        draw = () => {}
      }
    },
  })

  // Less motion asked for round the switch (`data-motion="reduced"`) keeps the
  // still face too, as forced colours do; the stylesheet shows it, and the island rests.
  const forced = window.matchMedia("(forced-colors: active)")
  const syncMotion = () => {
    if (!connected || still(root) || forced.matches) island.pause()
    else island.resume()
    render()
  }
  const calm = new MutationObserver(syncMotion)
  const resized = new ResizeObserver(() => {
    measure()
    render()
  })
  const events = new AbortController()

  return {
    mount() {
      measure()
      announce()
      render()
      const listen = {signal: events.signal}
      button.addEventListener("pointerdown", onPointerDown, listen)
      button.addEventListener("pointermove", onPointerMove, listen)
      button.addEventListener("pointerup", onPointerUp, listen)
      button.addEventListener("pointercancel", onPointerCancel, listen)
      button.addEventListener("click", onClick, listen)
      calm.observe(document.documentElement, {subtree: true, attributes: true, attributeFilter: ["data-motion"]})
      forced.addEventListener("change", syncMotion, listen)
      resized.observe(button)
      island.mount()
      syncMotion()
    },
    pause() {
      connected = false
      island.pause()
    },
    resume() {
      connected = true
      syncMotion()
    },
    destroy() {
      events.abort()
      follow()
      calm.disconnect()
      resized.disconnect()
      island.destroy()
      scope.revert()
    },
  }
}

type ThemeSwitchHook = {el: HTMLElement; controller?: ThemeSwitchController}

export const ThemeSwitch = {
  mounted(this: ThemeSwitchHook) {
    this.controller = createThemeSwitch(this.el)
    this.controller.mount()
  },
  disconnected(this: ThemeSwitchHook) {
    this.controller?.pause()
  },
  reconnected(this: ThemeSwitchHook) {
    this.controller?.resume()
  },
  destroyed(this: ThemeSwitchHook) {
    this.controller?.destroy()
    this.controller = undefined
  },
}
