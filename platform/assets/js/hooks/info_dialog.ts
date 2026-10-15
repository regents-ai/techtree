import type {Hook} from "../hook_composition"

interface InfoDialogHook {
  el: HTMLDialogElement
  js(): {ignoreAttributes(el: HTMLElement, attrs: string[]): void}
  pushEventTo(target: HTMLElement, event: string, payload: object): void
}

// A server-rendered <dialog> rendered only while it has something to show. It
// opens as it arrives (`data-open`) and stays open while what it shows is
// replaced: redraws keep its `open` and the inline style its rise is drawn
// with, so it neither closes nor rises again under them. It tells whatever
// rendered it, the page or a part of it, when the reader closes it
// (`data-close-event`).
export const InfoDialog: Hook = {
  mounted(this: InfoDialogHook) {
    this.js().ignoreAttributes(this.el, ["open", "style"])

    const closeEvent = this.el.dataset.closeEvent
    if (closeEvent) this.el.addEventListener("close", () => this.pushEventTo(this.el, closeEvent, {}))

    if (this.el.hasAttribute("data-open")) this.el.showModal()
  },
}
