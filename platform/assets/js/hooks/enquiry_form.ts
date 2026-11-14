import type {Hook} from "../hook_composition"

type EnquiryFormHook = {
  el: HTMLFormElement
  handleEvent(event: string, callback: (payload: {id: string}) => void): void
}

// The enquiry form (TechtreeWeb.Components.Enquiry). When the page refuses a
// Send, the keyboard goes to the first field to fix, so a person using a screen
// reader hears what is wrong there. LiveView hands the keyboard back to Send once
// the reply settles, after this event, so the move waits for the next frame. A
// field checked on leaving it keeps the keyboard where the person put it.
export const EnquiryForm: Hook = {
  mounted(this: EnquiryFormHook) {
    this.handleEvent("enquiry-refused", ({id}) => {
      if (id !== this.el.id) return
      requestAnimationFrame(() => this.el.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
    })
  },
}
