/**
 * Panels that open over the page. Techtree has one kind today: the small menu
 * beside "Copy page", a `<details>` that its summary opens and closes. The
 * island only adds movement to that; the browser still owns the open state, so
 * a keyboard or a reader who asked for less motion opens and closes it at once.
 * Which way it moves is read from `data-menu`, which the page keeps current.
 *
 * Every animation ends with the menu at rest and hands it back to its
 * stylesheet, so no offset, scale or fade is left behind.
 */
import {createScope, type AnimationParams, type Scope} from "animejs"
import {BASE, SLOW, byPointer, halt, move, still} from "./shared"

const CLOSE = {duration: BASE, ease: "in(3)"}

type Away = Record<string, number>

const PANELS: {menu: Record<string, {away: Away; open: AnimationParams}>} = {
  menu: {
    pop: {away: {y: -6, scale: 0.9, opacity: 0}, open: {duration: SLOW, ease: "outBack(2.2)"}},
  },
}

// Where a panel rests when it is open: no offset, full size.
const REST: Record<string, number> = {y: 0, scale: 1, opacity: 1}
const rest = (away: Away) => Object.fromEntries(Object.keys(away).map(key => [key, REST[key]]))
const from = (away: Away) => Object.fromEntries(Object.entries(away).map(([key, value]) => [key, {from: value}]))

type MenuHook = {el: HTMLDetailsElement; scope?: Scope}

export const MotionMenu = {
  mounted(this: MenuHook) {
    const scope = createScope({root: this.el})
    const summary = this.el.querySelector<HTMLElement>(":scope > summary")!
    const panel = this.el.querySelector<HTMLElement>("[data-panel]")!
    const variant = () => PANELS.menu[this.el.dataset.menu!]

    this.scope = scope.add(() => {
      let moving = false
      let closing = false

      const settle = () => {
        moving = false
        closing = false
      }

      // A menu caught closing turns round from where it is; a closed one
      // pops out from its away position.
      scope.add("open", () => {
        const {away, open} = variant()
        const start = moving ? rest(away) : from(away)
        moving = true
        closing = false
        move(panel, {...start, ...open, onComplete: settle})
      })

      scope.add("close", () => {
        moving = true
        closing = true
        move(panel, {
          ...variant().away,
          ...CLOSE,
          onComplete: () => {
            this.el.open = false
            settle()
          },
        })
      })

      // An instant toggle puts back anything still moving.
      scope.add("stop", () => {
        halt(panel)
        settle()
      })

      const onClick = (event: MouseEvent) => {
        if (!summary.contains(event.target as Node | null)) return
        if (!byPointer(event) || still()) return scope.methods.stop()

        if (!this.el.open) return scope.methods.open()

        // The browser would hide an open menu at once; hold it open while it
        // leaves, or bring it back if it was already leaving.
        event.preventDefault()
        closing ? scope.methods.open() : scope.methods.close()
      }

      summary.addEventListener("click", onClick)
      return () => summary.removeEventListener("click", onClick)
    })
  },

  destroyed(this: MenuHook) {
    this.scope?.revert()
  },
}
