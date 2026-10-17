import {createScope, createTimer, type Scope, type Timer} from "animejs"
import type {Hook} from "../hook_composition"
import {EASE_IN_OUT, FAST, SLOW, play, still} from "./motion/shared"

// The home headline's last words turn through what an improvement is for. The
// phrases share one box sized to the longest, so the line never jumps. Each
// rises in as the last rises out. The turning waits while the headline is off
// screen or the tab is hidden, and with less motion asked for each phrase only
// fades in. Without the script the first phrase simply stays.

const HOLD = 3200

type HeroOutcomeHook = Hook & {
  el: HTMLElement
  scope?: Scope
  cleanup?: () => void
}

export const HeroOutcome: Hook = {
  mounted(this: HeroOutcomeHook) {
    const phrases = [...this.el.querySelectorAll<HTMLElement>(".hero-outcome__phrase")]
    if (phrases.length < 2) return

    let shown = Math.max(0, phrases.findIndex(phrase => phrase.dataset.shown !== undefined))
    let timer: Timer | undefined
    const scope = createScope({root: this.el})

    const turn = () => {
      const leaving = phrases[shown]
      shown = (shown + 1) % phrases.length
      const arriving = phrases[shown]
      // The stylesheet rests each phrase at the end of its move: the one leaving
      // hidden, the one arriving shown.
      delete leaving.dataset.shown
      arriving.dataset.shown = ""

      if (still(this.el)) {
        play(arriving, {opacity: {from: 0}, duration: FAST, ease: "linear"})
        return
      }

      play(leaving, {y: ["0%", "-100%"], opacity: [1, 0], duration: SLOW, ease: EASE_IN_OUT})
      play(arriving, {y: {from: "100%"}, opacity: {from: 0}, duration: SLOW, ease: EASE_IN_OUT})
    }

    this.scope = scope.add(() => {
      timer = createTimer({duration: HOLD, loop: true, onLoop: turn, autoplay: false})
    })

    // Turning only while someone can see it.
    let onScreen = false
    const sync = () => {
      if (onScreen && document.visibilityState === "visible") timer?.resume()
      else timer?.pause()
    }
    const sight = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting
      sync()
    })
    sight.observe(this.el)
    document.addEventListener("visibilitychange", sync)

    this.cleanup = () => {
      sight.disconnect()
      document.removeEventListener("visibilitychange", sync)
    }
  },

  destroyed(this: HeroOutcomeHook) {
    this.cleanup?.()
    this.scope?.revert()
  },
}
