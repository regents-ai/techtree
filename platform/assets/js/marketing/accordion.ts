/**
 * A group of products on the home page: an accordion beside a dot-screen
 * picture. Opening an item tells the picture which shape to draw next
 * (`data-field-shape`, read by `field_hook.ts`); the still picture under the
 * canvas follows the open item from the stylesheet alone. An item opened with
 * a mouse or a finger lets its words settle in; one opened from the keyboard
 * is simply there.
 */
import {BASE, EASE_OUT, lastInputByPointer, play, still} from "../hooks/motion/shared"

type AccordionHook = {el: HTMLElement; stop?: () => void}

export const MarketingAccordion = {
  mounted(this: AccordionHook) {
    const root = this.el
    const picture = root.querySelector<HTMLElement>("[data-field]")

    const opened = (event: Event) => {
      if (!(event instanceof ToggleEvent) || event.newState !== "open") return
      const item = event.target
      if (!(item instanceof HTMLDetailsElement) || item.dataset.shape === undefined) return
      picture?.setAttribute("data-field-shape", item.dataset.shape)
      const body = item.querySelector("[data-item-body]")
      if (body && lastInputByPointer() && !still(item)) {
        play(body, {opacity: {from: 0}, y: {from: -6}, duration: BASE * 2, ease: EASE_OUT})
      }
    }

    root.addEventListener("toggle", opened, true)
    this.stop = () => root.removeEventListener("toggle", opened, true)
  },
  destroyed(this: AccordionHook) {
    this.stop?.()
  },
}
