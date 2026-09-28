/**
 * Motion for things the server decides: a list that changes, such as a stack
 * of notes, and a figure that moves. The page renders every result first;
 * these islands only animate from the old picture to the new one.
 */
import {
  animate,
  createLayout,
  createScope,
  spring,
  splitText,
  stagger,
  type AnimationParams,
  type LayoutAnimationParams,
  type Scope,
  type TextSplitter,
} from "animejs"
import {BASE, CLIPPED_CHAR, SLOW, still} from "./shared"
import {deny} from "./press"
import type {Hook} from "../../hook_composition"

// How a list moves when the server adds, reorders or drops its items: `bounce`
// for lists and `pop` for notes that come and go. Each is built fresh per
// change because a stagger remembers the items it measured.
export const LAYOUTS: Record<string, () => LayoutAnimationParams> = {
  bounce: () => ({
    ease: spring({bounce: 0.35, duration: 420}),
    enterFrom: {opacity: 0, transform: "translateY(-12px)"},
    leaveTo: {opacity: 0, transform: "scale(.9)", ease: "in(3)", duration: BASE},
  }),
  pop: () => ({
    ease: spring({bounce: 0.45, duration: 360}),
    enterFrom: {opacity: 0, transform: "scale(.6)"},
    leaveTo: {opacity: 0, transform: "scale(.8)", ease: "in(3)", duration: BASE},
  }),
}

type ListHook = {el: HTMLElement; scope?: Scope}

/**
 * A list the server owns, built from a table of versions. It renders
 * `data-layout-id` on the list and on every item, names the items in
 * `data-children` and the version in `data-variant`. An item that is leaving
 * is hidden for a moment before the server drops it, so it can fade out while
 * its neighbours close the gap.
 */
export const listHook = (layouts: Record<string, () => LayoutAnimationParams>): Hook => ({
  mounted(this: ListHook) {
    const scope = createScope({root: this.el})

    this.scope = scope.add(() => {
      const layout = createLayout(this.el, {children: this.el.dataset.children})
      scope.add("record", () => layout.record())
      scope.add("move", () => layout.animate(layouts[this.el.dataset.variant ?? ""]()))
    })
  },

  beforeUpdate(this: ListHook) {
    this.scope?.methods.record()
  },

  updated(this: ListHook) {
    if (!still(this.el)) this.scope?.methods.move()
  },

  destroyed(this: ListHook) {
    this.scope?.revert()
  },
})

export const MotionList = listHook(LAYOUTS)

// How the digits that changed arrive. `clip` masks each digit in its own
// slot, so a digit rolling in is hidden until it reaches the slot.
export type Roll = {clip: boolean; move: (up: boolean) => AnimationParams}

export const ROLLS: Record<string, Roll> = {
  roll: {clip: true, move: up => ({y: [up ? "100%" : "-100%", "0%"], duration: SLOW, ease: "outBack(1.4)"})},
}

// What a figure is worth, decimals included, so 1.75 to 2 rolls up.
const worth = (text: string) => Number(text.replace(/[^\d.]/g, ""))

// A figure's characters as the split makes them, which leaves out spaces, so
// a figure with a unit such as "12.5 USDC" lines up digit for digit.
const glyphs = (figure: HTMLElement) => (figure.textContent ?? "").replace(/\s/g, "")

// The figures inside a part of the page, each marked `data-count`.
const figures = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>("[data-count]")]

type CountHook = {el: HTMLElement; scope?: Scope; before?: string[]; splits: Set<TextSplitter>}

// Put the plain figure back, but only for a split that is still on the page:
// an older one would write its stale figure over the new one.
function join(hook: CountHook, split: TextSplitter) {
  if (!hook.splits.delete(split)) return
  split.revert()
}

/**
 * Figures the server changes, built from a table of versions. A figure may
 * carry a unit, such as "12.5 USDC". Only the characters that changed move,
 * the ones nearest the end first, like a counter turning over. The figure is
 * split into pieces for the move and joined back as soon as it ends, so the
 * page always patches the plain figure it rendered.
 */
export const countHook = (rolls: Record<string, Roll>): Hook => ({
  mounted(this: CountHook) {
    const scope = createScope({root: this.el})
    this.splits = new Set()

    this.scope = scope.add(() => {
      scope.add("roll", (split: TextSplitter, digits: HTMLElement[], up: boolean) => {
        animate(digits, {
          ...rolls[this.el.dataset.variant ?? ""].move(up),
          delay: stagger(45, {from: "last"}),
          onComplete: () => join(this, split),
        })
      })
    })
  },

  beforeUpdate(this: CountHook) {
    for (const split of this.splits) join(this, split)
    this.before = figures(this.el).map(glyphs)
  },

  updated(this: CountHook) {
    const before = this.before ?? []
    const after = figures(this.el)
    if (still(this.el) || after.length !== before.length) return

    const {clip} = rolls[this.el.dataset.variant ?? ""]
    after.forEach((figure, index) => {
      const was = before[index]
      const now = glyphs(figure)
      if (was === now) return

      const split = splitText(figure, {words: false, chars: clip ? CLIPPED_CHAR : true})
      const digits = split.chars.filter((_char, i) => was.at(i - now.length) !== now[i])
      this.splits.add(split)
      this.scope?.methods.roll(split, digits, worth(now) > worth(was))
    })
  },

  destroyed(this: CountHook) {
    for (const split of this.splits) join(this, split)
    this.scope?.revert()
  },
})

export const MotionCount = countHook(ROLLS)

type RefusalHook = {el: HTMLElement; said?: string}

// Shake while `data-refused` is on the message.
function shake(hook: RefusalHook) {
  if (hook.el.dataset.refused !== undefined) deny(hook.el)
}

/**
 * A message a live page shows when it refuses something. It shakes once when
 * it appears and again whenever it says something new, while `data-refused`
 * is on it. Pages the server draws once shake their alerts from `motion.ts`.
 */
export const MotionRefusal: Hook = {
  mounted(this: RefusalHook) {
    this.said = this.el.textContent ?? ""
    shake(this)
  },

  updated(this: RefusalHook) {
    const said = this.el.textContent ?? ""
    if (said !== this.said) shake(this)
    this.said = said
  },
}
