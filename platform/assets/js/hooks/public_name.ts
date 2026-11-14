import {createProfileClient} from "../../vendor/regent_identity/profile_client.mjs"
import {mountProfile} from "../../vendor/regent_ui/profile.mjs"
import {browserCsrfToken} from "../auth_lazy"
import type {Hook} from "../hook_composition"

type PublicNameHook = {
  el: HTMLElement
  pushEvent(event: string, payload: unknown): void
  stop?: () => void
}

// Saves the person's Public Display Name with the page's own sign-in, its
// session cookie and forms token, then tells the page, so every place showing
// the name reads it again. Each save keeps the forms token of its press of Save:
// a switch of account renews the session and its token, so a save pressed before
// one changes nothing after it.
export const PublicName: Hook = {
  mounted(this: PublicNameHook) {
    this.stop = mountProfile(this.el, {
      openProfile: () => {
        const token = browserCsrfToken()
        return createProfileClient({csrfToken: () => token})
      },
      onSaved: () => this.pushEvent("public_name_saved", {}),
    })
  },

  destroyed(this: PublicNameHook) {
    this.stop?.()
  },
}
