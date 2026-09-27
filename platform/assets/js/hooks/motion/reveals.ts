/**
 * Motion for moving between views and for a page arriving: the app's page
 * gliding in when another is chosen, tabs whose underline travels to the
 * chosen tab, a headline that rises in word by word and a grid of cards that
 * settles into place.
 */
import {
  animate,
  createScope,
  stagger,
  utils,
  type AnimationParams,
  type JSAnimation,
  type Scope,
  type TextSplitter,
} from "animejs"
import {EASE_IN_OUT, EASE_OUT, SLOW, byPointer, play, still} from "./shared"
import type {Hook} from "../../hook_composition"

type Spot = {x: number; scaleX: number}

// How the underline travels and how the new view arrives. `step` is 1 when
// the chosen view comes after the last one and -1 when it comes before; `base`
// is the underline's own width.
export type TabMove = {
  ink: (from: Spot, to: Spot, base: number) => AnimationParams
  panel: (step: number) => AnimationParams
}

export const TABS: Record<string, TabMove> = {
  glide: {
    ink: (_from, to) => ({...to, duration: SLOW, ease: EASE_IN_OUT}),
    panel: step => ({x: {from: step * 24}, opacity: {from: 0}, duration: SLOW, ease: EASE_OUT}),
  },
}

type ViewsHook = {el: HTMLElement; scope?: Scope; destination?: string; pointer: boolean}

/**
 * The app's pages, switched by the server as the reader moves through the
 * navigation. The shell names where it is in `data-destination` and the
 * version in `data-variant`; a page chosen with a mouse or finger glides in,
 * one reached from the keyboard or the browser's back button is simply there.
 */
export const ShellViews: Hook = {
  mounted(this: ViewsHook) {
    const scope = createScope({root: this.el})
    this.destination = this.el.dataset.destination
    this.pointer = false

    this.scope = scope.add(() => {
      const place = (path?: string) =>
        [...this.el.querySelectorAll("#shell-sidebar a[href]")].findIndex(
          link => link.getAttribute("href") === path,
        )

      scope.add("glide", (from: string, to: string) => {
        const view = this.el.querySelector("#route-content")
        const step = place(to) < place(from) ? -1 : 1
        if (view) play(view, TABS[this.el.dataset.variant ?? ""].panel(step))
      })

      const onClick = (event: MouseEvent) => {
        if (event.target instanceof Element && event.target.closest("a[href]")) {
          this.pointer = byPointer(event)
        }
      }

      this.el.addEventListener("click", onClick, true)
      return () => this.el.removeEventListener("click", onClick, true)
    })
  },

  updated(this: ViewsHook) {
    const from = this.destination
    const to = this.el.dataset.destination
    this.destination = to
    if (from === to || from === undefined || to === undefined) return

    if (this.pointer && !still(this.el)) this.scope?.methods.glide(from, to)
    this.pointer = false
  },

  destroyed(this: ViewsHook) {
    this.scope?.revert()
  },
}

type TabsHook = {el: HTMLElement; scope?: Scope; active?: string; pointer: boolean}

/**
 * Tabs the server switches, built from a table of versions. The island names
 * the chosen tab in `data-active` and the version in `data-variant`; each tab
 * carries `data-tab`, the view is its `role="tabpanel"`, and an optional
 * `data-ink` underline keeps the position this island gives it across page
 * updates. A tab picked with a mouse or finger moves; one picked from the
 * keyboard is simply there.
 */
export const tabsHook = (moves: Record<string, TabMove>): Hook => ({
  mounted(this: TabsHook) {
    const scope = createScope({root: this.el})
    this.active = this.el.dataset.active
    this.pointer = false

    this.scope = scope.add(() => {
      const ink = this.el.querySelector<HTMLElement>("[data-ink]")
      const tabs = [...this.el.querySelectorAll<HTMLElement>("[data-tab]")]
      const tab = (name: string) => tabs.find(el => el.dataset.tab === name)
      const spot = (name: string, base: number): Spot => ({
        x: tab(name)?.offsetLeft ?? 0,
        scaleX: (tab(name)?.offsetWidth ?? 0) / base,
      })

      scope.add("place", () => {
        if (ink) utils.set(ink, spot(this.el.dataset.active ?? "", ink.offsetWidth))
      })

      scope.add("move", (from: string, to: string) => {
        const move = moves[this.el.dataset.variant ?? ""]
        if (ink) animate(ink, move.ink(spot(from, ink.offsetWidth), spot(to, ink.offsetWidth), ink.offsetWidth))
        const step = tabs.indexOf(tab(to)!) > tabs.indexOf(tab(from)!) ? 1 : -1
        const panel = this.el.querySelector("[role='tabpanel']")
        if (panel) play(panel, move.panel(step))
      })

      const onClick = (event: MouseEvent) => {
        if (event.target instanceof Element && event.target.closest("[data-tab]")) this.pointer = byPointer(event)
      }
      const watch = new ResizeObserver(() => scope.methods.place())

      scope.methods.place()
      watch.observe(this.el)
      this.el.addEventListener("click", onClick, true)
      return () => {
        watch.disconnect()
        this.el.removeEventListener("click", onClick, true)
      }
    })
  },

  updated(this: TabsHook) {
    const from = this.active
    const to = this.el.dataset.active
    this.active = to
    if (from === to || from === undefined || to === undefined) return

    if (this.pointer && !still(this.el)) this.scope?.methods.move(from, to)
    else this.scope?.methods.place()
    this.pointer = false
  },

  destroyed(this: TabsHook) {
    this.scope?.revert()
  },
})

export const MotionTabs = tabsHook(TABS)

// Moves in percent name both ends, so they stay a share of each word's own
// height instead of being converted to pixels from its width.
export const HEADLINES: Record<string, (split: TextSplitter) => JSAnimation> = {
  rise: split => play(split.words, {y: ["100%", "0%"], delay: stagger(50), duration: SLOW, ease: EASE_OUT}),
}

export const GRIDS: Record<string, (cards: Element[]) => JSAnimation> = {
  cascade: cards =>
    play(cards, {y: {from: 16}, opacity: {from: 0}, delay: stagger(45), duration: SLOW, ease: EASE_OUT}),
}
