/**
 * Motion for things the server decides: a list that changes. The page renders
 * every result first; the island only animates from the old picture to the
 * new one.
 */
import {createLayout, createScope, spring, type LayoutAnimationParams, type Scope} from "animejs"
import {BASE, byPointer, still} from "./shared"

// How a list moves when the server adds, reorders or removes its items. Each
// is built fresh per change because a spring or stagger remembers what it
// measured.
const LAYOUTS: Record<string, () => LayoutAnimationParams> = {
  bounce: () => ({
    ease: spring({bounce: 0.35, duration: 420}),
    enterFrom: {opacity: 0, transform: "translateY(-12px)"},
    leaveTo: {opacity: 0, transform: "scale(.9)", ease: "in(3)", duration: BASE},
  }),
}

/**
 * A list the server owns. It renders `data-layout-id` on the list and on
 * every item, so an item that stays keeps its identity across a change: it
 * glides to its new place while new items drop in.
 */
type ListHook = {el: HTMLElement; scope?: Scope}

export const MotionList = {
  mounted(this: ListHook) {
    const scope = createScope({root: this.el})

    this.scope = scope.add(() => {
      const layout = createLayout(this.el, {children: this.el.dataset.children})
      // A change asked for from the keyboard shows at once, like any other
      // keyboard press; one the server makes by itself still moves.
      let pressedByKeyboard = false
      const onClick = (event: MouseEvent) => {
        pressedByKeyboard = !byPointer(event)
      }

      // Layout hands the items that dropped in back with `translate: none`
      // written on the frame after it finishes; take it off then so every item
      // is back as its stylesheet draws it.
      const tidy = () =>
        requestAnimationFrame(() => {
          for (const el of this.el.querySelectorAll<HTMLElement>("[style]")) {
            if (el.style.translate === "none") el.style.removeProperty("translate")
          }
        })

      scope.add("record", () => layout.record())
      scope.add("glide", () => {
        if (!pressedByKeyboard && !still()) {
          layout.animate({...LAYOUTS[this.el.dataset.variant!](), onComplete: tidy})
        }
        pressedByKeyboard = false
      })

      document.addEventListener("click", onClick, true)
      return () => document.removeEventListener("click", onClick, true)
    })
  },

  beforeUpdate(this: ListHook) {
    this.scope!.methods.record()
  },

  updated(this: ListHook) {
    this.scope!.methods.glide()
  },

  destroyed(this: ListHook) {
    this.scope?.revert()
  },
}
