/**
 * The cards of the home page's Evaluate & Climb story, each a short loop that
 * plays while the card is on the screen and rests when it leaves:
 *
 * - Validate: a band of light sweeps down a Skill's lines, lighting each as it goes.
 * - Deduplicate: two pieces of guidance slide together until their repeated
 *   lines meet and light up, then part.
 * - Live run: the newest Result's tasks drop in as squares, the ones the Skill
 *   made better lift, then they clear for the next pass.
 * - Verdict: a dial's needle swings to the newest Result's verdict, or, with
 *   none yet, to each verdict in turn.
 * - Offline check: each check on a downloaded Result ticks in turn, and its
 *   line lights as it does.
 *
 * Each card is drawn whole by the server; the loops move it from there. As a
 * card leaves the screen its loop pauses and hands the card back to its
 * stylesheet, and as it returns the loop picks up where it paused.
 */
import {createDrawable, createScope, createTimeline, onScroll, stagger, utils, type Scope} from "animejs"
import {EASE_IN_OUT, EASE_OUT, still} from "../hooks/motion/shared"

/** The needle's angle, from straight up, when it rests. */
const REST = -90

/**
 * A loop that plays only while `card` is on the screen. It is started and
 * paused by hand rather than linked to the scroll, which would draw its first
 * frame onto a card nobody has scrolled to yet.
 */
const loop = (card: HTMLElement, loopDelay: number) => {
  const timeline = createTimeline({loop: true, loopDelay, autoplay: false})
  onScroll({
    target: card,
    onEnter: () => timeline.play(),
    onLeave: () => utils.cleanInlineStyles(timeline.pause()),
  })
  return timeline
}

function validate(card: HTMLElement) {
  const sweep = card.querySelector("[data-sweep]")
  const lines = [...card.querySelectorAll("[data-line]")]
  if (sweep === null || lines.length === 0) return
  const pass = 1800
  loop(card, 900)
    .add(sweep, {y: ["-100%", "100%"], opacity: [0, 1, 1, 0], duration: pass, ease: "linear"})
    .add(lines, {opacity: [0.35, 1], duration: 260, ease: EASE_OUT, delay: stagger(pass / (lines.length + 1), {start: 120})}, "<<")
    .add(lines, {opacity: [1, 0.35], duration: 420, ease: "inQuad"}, "+=900")
}

function deduplicate(card: HTMLElement) {
  const left = card.querySelector("[data-copy='left']")
  const right = card.querySelector("[data-copy='right']")
  const repeats = [...card.querySelectorAll("[data-repeat]")]
  if (left === null || right === null) return
  const timeline = loop(card, 700)
    .add(left, {x: ["-18%", "0%"], duration: 900, ease: EASE_IN_OUT})
    .add(right, {x: ["18%", "0%"], duration: 900, ease: EASE_IN_OUT}, "<<")
  if (repeats.length) timeline.add(repeats, {opacity: [0.35, 1], scale: [1, 1.04, 1], duration: 520, ease: EASE_OUT, delay: stagger(80)}, "-=120")
  timeline
    .add(left, {x: ["0%", "-18%"], duration: 800, ease: EASE_IN_OUT}, "+=1800")
    .add(right, {x: ["0%", "18%"], duration: 800, ease: EASE_IN_OUT}, "<<")
  if (repeats.length) timeline.add(repeats, {opacity: [1, 0.35], duration: 400, ease: "inQuad"}, "<<")
}

function runs(card: HTMLElement) {
  const cells = [...card.querySelectorAll<HTMLElement>("[data-cell]")]
  if (cells.length === 0) return
  const better = cells.filter(cell => cell.dataset.cell === "better")
  const timeline = loop(card, 700)
    .add(cells, {scale: [0, 1], opacity: [0, 1], duration: 420, ease: EASE_OUT, delay: stagger(34)})
  if (better.length) timeline.add(better, {y: [0, -4, 0], duration: 560, ease: "inOutSine", delay: stagger(45)}, "+=240")
  timeline.add(cells, {scale: [1, 0.5], opacity: [1, 0], duration: 320, ease: "inQuad", delay: stagger(16, {from: "last"})}, "+=2400")
}

function dial(card: HTMLElement) {
  const needle = card.querySelector<SVGElement>("[data-needle]")
  if (needle === null) return
  const verdict = card.dataset.angle
  const stops = verdict === undefined ? [-60, 0, 60] : [Number(verdict)]
  const swing = {duration: 1200, ease: "outElastic(1, .6)"}
  const timeline = loop(card, 500)
    .add(needle, {rotate: [REST, stops[0]], ...swing})
  for (const stop of stops.slice(1)) timeline.add(needle, {rotate: stop, ...swing}, "+=700")
  timeline.add(needle, {rotate: REST, duration: 700, ease: EASE_IN_OUT}, "+=2400")
}

function checks(card: HTMLElement) {
  const ticks = card.querySelectorAll("[data-check]")
  const lines = [...card.querySelectorAll("[data-check-line]")]
  if (ticks.length === 0) return
  const marks = createDrawable(ticks)
  loop(card, 500)
    .add(marks, {draw: ["0 0", "0 1"], duration: 420, ease: EASE_OUT, delay: stagger(360)})
    .add(lines, {opacity: [0.4, 1], duration: 320, ease: EASE_OUT, delay: stagger(360)}, "<<")
    .add(marks, {draw: ["0 1", "1 1"], duration: 360, ease: "inQuad", delay: stagger(60)}, "+=2400")
    .add(lines, {opacity: [1, 0.4], duration: 360, ease: "inQuad", delay: stagger(60)}, "<<")
}

const LOOPS: Record<string, (card: HTMLElement) => void> = {validate, deduplicate, runs, verdict: dial, checks}

type CardsHook = {el: HTMLElement; scope?: Scope}

export const MarketingCards = {
  mounted(this: CardsHook) {
    const root = this.el
    if (still(root)) return
    this.scope = createScope({root}).add(() => {
      for (const card of root.querySelectorAll<HTMLElement>("[data-loop]")) LOOPS[card.dataset.loop!]?.(card)
    })
  },
  destroyed(this: CardsHook) {
    this.scope?.revert()
  },
}
