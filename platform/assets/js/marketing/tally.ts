/**
 * Figures that count up to the number the server wrote: the hero's Result
 * figures each time a card comes to the middle (`carousel.ts`), and the proof
 * band's counts the first time they scroll into view (`MarketingTally`). The
 * figure keeps its width while it counts, so nothing beside it moves, and ends
 * on exactly the text it started with.
 */
import {animate, createScope, type JSAnimation, type Scope} from "animejs"
import {onFirstSight} from "../hooks/motion/reveals"
import {EASE_OUT, still} from "../hooks/motion/shared"

// The text each figure was drawn with, kept from its first count, and the count
// still running on it.
const finals = new WeakMap<HTMLElement, string>()
const running = new WeakMap<HTMLElement, JSAnimation>()

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

export function countUp(figure: HTMLElement, duration: number) {
  running.get(figure)?.cancel()
  const text = finals.get(figure) ?? figure.textContent ?? ""
  finals.set(figure, text)
  const read = reading(text)
  if (!read) return

  figure.textContent = text
  figure.style.minWidth = `${figure.getBoundingClientRect().width}px`
  const count = {value: 0}
  const write = () => { figure.textContent = written(text, count.value) }
  write()
  running.set(figure, animate(count, {
    value: read.value,
    duration,
    ease: EASE_OUT,
    onUpdate: write,
    onComplete: () => {
      figure.textContent = text
      figure.style.minWidth = ""
      running.delete(figure)
    },
  }))
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
