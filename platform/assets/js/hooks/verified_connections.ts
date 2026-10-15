import {
  IDENTITY_REQUEST_EVENT,
  IDENTITY_STATE_EVENT,
  type IdentityRequest,
} from "../auth_lazy"
import type {Hook} from "../hook_composition"

type VerifiedConnectionsHook = Hook & {
  handleEvent(event: string, callback: (payload: unknown) => void): void
  pushEvent(event: string, payload: unknown): void
  identityStateListener?: (event: Event) => void
}

// The page asks on `window`, where the account loader listens, and hears the
// outcome on the same target; the outcome is handed back to the page as it is.
export const VerifiedConnections: Hook = {
  mounted(this: VerifiedConnectionsHook) {
    this.handleEvent("verified-connections:request", payload => {
      window.dispatchEvent(
        new CustomEvent<IdentityRequest>(IDENTITY_REQUEST_EVENT, {
          detail: payload as IdentityRequest,
        }),
      )
    })

    this.identityStateListener = event => {
      const detail =
        event instanceof CustomEvent && typeof event.detail === "object"
          ? event.detail
          : {error: "failed"}
      this.pushEvent("refresh_verified_connections", detail)
    }
    window.addEventListener(IDENTITY_STATE_EVENT, this.identityStateListener)
  },

  destroyed(this: VerifiedConnectionsHook) {
    if (this.identityStateListener) {
      window.removeEventListener(IDENTITY_STATE_EVENT, this.identityStateListener)
    }
  },
}
