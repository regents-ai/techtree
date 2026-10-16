import type {Hook} from "../hook_composition"
import {asideOpen} from "./side_panel"

interface PanelAgentsHook {
  el: HTMLElement
  read?: () => void
  pushEventTo(target: HTMLElement, event: string, payload: object): void
}

// The side panel's agents read what each one last did only while someone can
// see them: when the page arrives with the panel open, and each time it opens
// (`ash:aside-opened`, from the `SidePanel` hook).
export const PanelAgents: Hook = {
  mounted(this: PanelAgentsHook) {
    this.read = () => this.pushEventTo(this.el, "read_last_actions", {})
    this.el.addEventListener("ash:aside-opened", this.read)
    if (asideOpen()) this.read()
  },

  destroyed(this: PanelAgentsHook) {
    if (this.read) this.el.removeEventListener("ash:aside-opened", this.read)
  },
}
