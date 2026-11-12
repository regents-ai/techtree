/**
 * The mark in the home page's dark band, drawn in lines. The first time it
 * scrolls into view its squares are traced from the middle outwards and then
 * fill in; after that a light runs through the squares while the band is on
 * the screen. The server draws the mark whole; this only moves it.
 */
import {
  animate,
  createDrawable,
  createScope,
  createTimeline,
  onScroll,
  type FunctionValue,
  type JSAnimation,
  type Scope,
} from "animejs"
import {EASE_IN_OUT, EASE_OUT, still} from "../hooks/motion/shared"

// When each square starts: later the further it sits from the mark's middle
// column (`data-col`, 0 to 4) and from its top row (`data-row`, 0 to 2).
const wave = (squares: Element[], column: number, row: number): FunctionValue<number> =>
  (_square, index = 0) => {
    const {col, row: line} = (squares[index] as SVGElement).dataset
    return Math.abs(Number(col) - 2) * column + Number(line) * row
  }

type DrawHook = {el: HTMLElement; scope?: Scope}

export const MarketingDraw = {
  mounted(this: DrawHook) {
    const root = this.el
    if (still(root)) return
    this.scope = createScope({root}).add(() => {
      const outlines = [...root.querySelectorAll("[data-outline]")]
      const blocks = [...root.querySelectorAll("[data-block]")]
      let shimmer: JSAnimation | undefined
      const shine = () => {
        shimmer = animate(blocks, {
          opacity: [1, 0.3, 1],
          duration: 1500,
          ease: "inOutSine",
          delay: wave(blocks, 90, 140),
          loop: true,
          loopDelay: 1600,
          autoplay: onScroll({target: root}),
        })
      }
      createTimeline({autoplay: onScroll({target: root, repeat: false}), onComplete: shine})
        .add(createDrawable(outlines), {draw: ["0 0", "0 1"], duration: 900, ease: EASE_IN_OUT, delay: wave(outlines, 110, 70)})
        .add(blocks, {opacity: [0, 1], scale: [0.4, 1], duration: 520, ease: EASE_OUT, delay: wave(blocks, 80, 60)}, "-=380")
      return () => shimmer?.revert()
    })
  },
  destroyed(this: DrawHook) {
    this.scope?.revert()
  },
}
