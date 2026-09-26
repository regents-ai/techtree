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
import {createScope} from "animejs"
import {BASE, SLOW, byPointer, halt, move, still} from "./shared.js"

const CLOSE = {duration: BASE, ease: "in(3)"}

const PANELS = {
  menu: {
    pop: {away: {y: -6, scale: 0.9, opacity: 0}, open: {duration: SLOW, ease: "outBack(2.2)"}},
  },
}

// Where a panel rests when it is open: no offset, full size.
const REST = {y: 0, scale: 1, opacity: 1}
const rest = away => Object.fromEntries(Object.keys(away).map(key => [key, REST[key]]))
const from = away => Object.fromEntries(Object.entries(away).map(([key, value]) => [key, {from: value}]))

export const MotionMenu = {
  mounted() {
    const scope = createScope({root: this.el})
    const summary = this.el.querySelector(":scope > summary")
    const panel = this.el.querySelector("[data-panel]")
    const variant = () => PANELS.menu[this.el.dataset.menu]

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

      const onClick = event => {
        if (!summary.contains(event.target)) return
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

  destroyed() {
    this.scope?.revert()
  },
}
