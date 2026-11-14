/**
 * Figures that count up to the number the server wrote, the first time they
 * scroll into view (`MarketingTally`): the home page's demonstration. The figure
 * keeps its width while it counts, so nothing beside it moves, and ends on
 * exactly the text it started with.
 */
import {animate, createScope, type Scope} from "animejs"
import {onFirstSight} from "../hooks/motion/reveals"
import {EASE_OUT, still} from "../hooks/motion/shared"

/** The number in a figure's text, how many decimals it shows, and whether it groups thousands. */
export const reading = (text: string) => {
  const found = text.match(/\d[\d,]*(\.\d+)?/)
  if (!found) return undefined
  return {
    written: found[0],
    value: Number(found[0].replace(/,/g, "")),
    decimals: found[1] ? found[1].length - 1 : 0,
    grouped: found[0].includes(","),
  }
}

/** The figure's text with its number replaced by `value`, written the same way. */
export const written = (text: string, value: number) => {
  const read = reading(text)
  if (!read) return text
  const number = read.grouped
    ? value.toLocaleString("en-US", {minimumFractionDigits: read.decimals, maximumFractionDigits: read.decimals})
    : value.toFixed(read.decimals)
  return text.replace(read.written, number)
}

function countUp(figure: HTMLElement, duration: number) {
  const text = figure.textContent ?? ""
  const read = reading(text)
  if (!read) return

  figure.style.minWidth = `${figure.getBoundingClientRect().width}px`
  const count = {value: 0}
  const write = () => { figure.textContent = written(text, count.value) }
  write()
  animate(count, {
    value: read.value,
    duration,
    ease: EASE_OUT,
    onUpdate: write,
    onComplete: () => {
      figure.textContent = text
      figure.style.minWidth = ""
    },
  })
}

type TallyHook = {el: HTMLElement; scope?: Scope}

/** Every `data-tally` figure inside counts up once, the first time the part scrolls into view. */
export const MarketingTally = {
  mounted(this: TallyHook) {
    const root = this.el
    const scope = createScope({root})
    this.scope = scope.add(() =>
      onFirstSight(root, () => {
        if (still(root)) return
        for (const figure of root.querySelectorAll<HTMLElement>("[data-tally]")) countUp(figure, 1200)
      }))
  },
  destroyed(this: TallyHook) {
    this.scope?.revert()
  },
}
