/**
 * The hero's published Results, one bright card in the middle and its
 * neighbours dimmed either side. Every few seconds the next one slides to the
 * middle, and as it arrives its figures count up, its bars grow and its rows
 * tick in one after another.
 *
 * The server draws each card in its first place (`data-slot`), so the page is
 * whole before this runs and stays so for a visitor who asked for less motion.
 * From then on this owns each card's place: the carousel is `phx-update="ignore"`.
 *
 * The turning stops while a mouse is over the cards, while the keyboard is
 * inside, while it is off the screen, once Pause is pressed, and never starts
 * for less motion. The active dot fills as the next turn comes, and is the clock.
 * A swipe on a touch screen turns it by hand, as the dots do.
 */
import {animate, stagger, utils, type JSAnimation} from "animejs"
import {EASE_IN_OUT, EASE_OUT, play, still} from "../hooks/motion/shared"
import {countUp} from "./tally"

type Slot = "centre" | "next" | "prev" | "away"
type Place = {x: string; scale: number; opacity: number}

/** How long each Result stays in the middle. */
const TURN_MS = 5600
/** How long a card takes to slide to its next place. */
const SLIDE_MS = 760
/** How far a finger must move sideways to turn the carousel. */
const SWIPE_PX = 40

const WIDE = "(min-width: 48rem)"

// Each place as a share of the card's own width, so the cards keep their
// spacing at any size. On a narrow screen the neighbours only peek in.
const places = (): Record<Slot, Place> => {
  const side = matchMedia(WIDE).matches ? 66 : 94
  return {
    centre: {x: "0%", scale: 1, opacity: 1},
    next: {x: `${side}%`, scale: 0.84, opacity: 0.42},
    prev: {x: `-${side}%`, scale: 0.84, opacity: 0.42},
    away: {x: "0%", scale: 0.72, opacity: 0},
  }
}

/** Where the card at `index` sits when `current` is in the middle of `count` cards. */
export const slotOf = (index: number, current: number, count: number): Slot => {
  const step = (index - current + count) % count
  if (step === 0) return "centre"
  if (step === 1) return "next"
  if (step === count - 1 && count > 2) return "prev"
  return "away"
}

type CarouselHook = {el: HTMLElement; stop?: () => void}

export const MarketingCarousel = {
  mounted(this: CarouselHook) {
    const root = this.el
    const stage = root.querySelector<HTMLElement>("[data-carousel-stage]")!
    const cards = [...stage.querySelectorAll<HTMLElement>("[data-carousel-card]")]
    const dots = [...root.querySelectorAll<HTMLButtonElement>("[data-carousel-dot]")]
    const pause = root.querySelector<HTMLButtonElement>("[data-carousel-pause]")
    const count = cards.length
    if (count < 2) return

    const calm = still(root)
    let current = cards.findIndex(card => card.dataset.slot === "centre")
    let held = false
    let hovered = false
    let focused = false
    let onscreen = false
    let clock: JSAnimation | undefined
    const events = new AbortController()
    const options = {signal: events.signal}

    const place = (animated: boolean) => {
      const at = places()
      cards.forEach((card, index) => {
        const slot = slotOf(index, current, count)
        card.dataset.slot = slot
        const middle = slot === "centre"
        card.inert = !middle
        if (middle) card.removeAttribute("aria-hidden")
        else card.setAttribute("aria-hidden", "true")
        if (animated) animate(card, {...at[slot], duration: SLIDE_MS, ease: EASE_IN_OUT})
        else utils.set(card, at[slot])
      })
      dots.forEach((dot, index) => dot.setAttribute("aria-current", String(index === current)))
    }

    // The new card in the middle shows its figures arriving.
    const arrive = (card: HTMLElement) => {
      for (const figure of card.querySelectorAll<HTMLElement>("[data-figure]")) countUp(figure, 900)
      play([...card.querySelectorAll("[data-bar]")], {scaleX: {from: 0}, delay: stagger(120, {start: 220}), duration: 900, ease: EASE_OUT})
      play([...card.querySelectorAll("[data-tick]")], {opacity: {from: 0}, x: {from: -8}, delay: stagger(90, {start: 160}), duration: 420, ease: EASE_OUT})
    }

    const turning = () => !calm && !held && !hovered && !focused && onscreen

    // The active dot's fill is the clock: when it is full, the next Result turns in.
    const wind = () => {
      clock?.revert()
      clock = undefined
      if (calm || held) return
      const fill = dots[current]?.querySelector<HTMLElement>("[data-fill]")
      if (!fill) return
      clock = animate(fill, {
        scaleX: [0, 1],
        duration: TURN_MS,
        ease: "linear",
        autoplay: turning(),
        onComplete: () => go(current + 1),
      })
    }

    const go = (next: number) => {
      const was = current
      current = (next + count) % count
      if (current === was) return
      place(!calm)
      if (!calm) arrive(cards[current])
      wind()
    }

    const run = () => {
      stage.setAttribute("aria-live", turning() ? "off" : "polite")
      if (!clock) return
      if (turning()) clock.resume()
      else clock.pause()
    }

    dots.forEach((dot, index) => dot.addEventListener("click", () => go(index), options))
    pause?.addEventListener("click", () => {
      held = !held
      pause.classList.toggle("is-held", held)
      pause.querySelector("[data-label]")!.textContent = held ? "Play" : "Pause"
      wind()
      run()
    }, options)

    stage.addEventListener("pointerenter", event => {
      if (event.pointerType !== "mouse") return
      hovered = true
      run()
    }, options)
    stage.addEventListener("pointerleave", () => {
      hovered = false
      run()
    }, options)
    // Focus from the keyboard holds it; a dot pressed with a mouse does not.
    root.addEventListener("focusin", event => {
      focused = event.target instanceof Element && event.target.matches(":focus-visible")
      run()
    }, options)
    root.addEventListener("focusout", event => {
      focused = event.relatedTarget instanceof Element && root.contains(event.relatedTarget) &&
        event.relatedTarget.matches(":focus-visible")
      run()
    }, options)

    let swipe: number | undefined
    stage.addEventListener("pointerdown", event => {
      swipe = event.pointerType === "mouse" ? undefined : event.clientX
    }, options)
    stage.addEventListener("pointerup", event => {
      if (swipe === undefined) return
      const moved = event.clientX - swipe
      swipe = undefined
      if (Math.abs(moved) >= SWIPE_PX) go(current + (moved < 0 ? 1 : -1))
    }, options)

    const sight = new IntersectionObserver(([entry]) => {
      onscreen = entry.isIntersecting
      run()
    })
    sight.observe(root)
    matchMedia(WIDE).addEventListener("change", () => place(false), options)

    // From here the carousel owns each card's place, starting from where the server put it.
    place(false)
    wind()
    run()

    this.stop = () => {
      events.abort()
      sight.disconnect()
      clock?.revert()
      utils.remove(cards)
    }
  },
  destroyed(this: CarouselHook) {
    this.stop?.()
  },
}
