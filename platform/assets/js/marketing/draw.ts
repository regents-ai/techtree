/**
 * The On-ramp in the home page's dark band: the path from a team's own work
 * through Techtree to Prime Intellect. The first time it scrolls into view the
 * links between its stops draw out one after the other, and Techtree's mark,
 * in the middle stop, is traced from its middle outwards and fills in. After
 * that a light runs through the mark's squares while the band is on the
 * screen, and the stylesheet runs a light along each link. The server draws
 * the path whole; this only moves it, and leaves no moved element out of
 * place when it stops.
 */
import {
  animate,
  createDrawable,
  createScope,
  onScroll,
  stagger,
  type FunctionValue,
  type JSAnimation,
  type Scope,
} from "animejs"
import {onFirstSight} from "../hooks/motion/reveals"
import {EASE_IN_OUT, EASE_OUT, play, still} from "../hooks/motion/shared"

// When each square starts, after `start`: later the further it sits from the
// mark's middle column (`data-col`, 0 to 4) and from its top row (`data-row`,
// 0 to 2).
const wave = (squares: Element[], column: number, row: number, start = 0): FunctionValue<number> =>
  (_square, index = 0) => {
    const {col, row: line} = (squares[index] as SVGElement).dataset
    return start + Math.abs(Number(col) - 2) * column + Number(line) * row
  }

type DrawHook = {el: HTMLElement; scope?: Scope}

export const MarketingDraw = {
  mounted(this: DrawHook) {
    const root = this.el
    this.scope = createScope({root}).add(() => {
      const links = [...root.querySelectorAll("[data-link]")]
      const outlines = [...root.querySelectorAll("[data-outline]")]
      const blocks = [...root.querySelectorAll("[data-block]")]
      let shimmer: JSAnimation | undefined
      const stop = onFirstSight(root, () => {
        if (still(root)) return
        play(links, {scale: [0, 1], duration: 760, ease: EASE_IN_OUT, delay: stagger(820)})
        animate(createDrawable(outlines), {draw: ["0 0", "0 1"], duration: 900, ease: EASE_IN_OUT, delay: wave(outlines, 110, 70)})
        play(blocks, {opacity: [0, 1], scale: [0.4, 1], duration: 520, ease: EASE_OUT, delay: wave(blocks, 80, 60, 640)})
          .then(() => {
            shimmer = animate(blocks, {
              opacity: [1, 0.3, 1],
              duration: 1500,
              ease: "inOutSine",
              delay: wave(blocks, 90, 140),
              loop: true,
              loopDelay: 1600,
              autoplay: onScroll({target: root}),
            })
          })
      })
      return () => {
        stop()
        shimmer?.revert()
      }
    })
  },
  destroyed(this: DrawHook) {
    this.scope?.revert()
  },
}
