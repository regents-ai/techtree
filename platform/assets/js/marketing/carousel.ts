/**
 * The hero's published Results, one bright card in the middle and its
 * neighbours dimmed either side. Every few seconds the next one slides to the
 * middle, and as it arrives its figures count up, its bars grow and its rows
 * tick in one after another.
 *
 * The server draws each card in its first place (`data-slot`), so the page is
 * whole before this runs and stays so for a visitor who asked for less motion.
 * From then on this owns each card's place: the carousel is `phx-update="ignore"`.
 * A card moves by changing its `data-slot`; the stylesheet places each slot and
 * slides a card between them, so no card is ever left with a style of its own.
 *
 * The turning stops while a mouse is over the cards, while the keyboard is
 * inside, while it is off the screen, once Pause is pressed, and never starts
 * for less motion. The active dot fills as the next turn comes, and is the clock.
 * A swipe on a touch screen turns it by hand, as the dots do.
 */
import {animate, stagger, type JSAnimation} from "animejs"
import {EASE_OUT, play, still} from "../hooks/motion/shared"
import {countUp} from "./tally"

type Slot = "centre" | "next" | "prev" | "away"

/** How long each Result stays in the middle. */
const TURN_MS = 5600
/** How far a finger must move sideways to turn the carousel. */
const SWIPE_PX = 40

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

    const place = () => {
      cards.forEach((card, index) => {
        const slot = slotOf(index, current, count)
        card.dataset.slot = slot
        const middle = slot === "centre"
        card.inert = !middle
        if (middle) card.removeAttribute("aria-hidden")
        else card.setAttribute("aria-hidden", "true")
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

    // The active dot's fill is the clock: when it is full, the next Result turns
    // in. It runs on the fill's `--turn`, which the stylesheet turns into its width.
    const wind = () => {
      clock?.revert()
      clock = undefined
      if (calm || held) return
      const fill = dots[current]?.querySelector<HTMLElement>("[data-fill]")
      if (!fill) return
      clock = animate(fill, {
        "--turn": [0, 1],
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
      place()
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

    // From here the carousel owns each card's place, starting from where the server put it.
    place()
    wind()
    run()

    this.stop = () => {
      events.abort()
      sight.disconnect()
      clock?.revert()
    }
  },
  destroyed(this: CarouselHook) {
    this.stop?.()
  },
}
