import type {Hook} from "../hook_composition"

const CONTROLS = "a[href], button, input, select, textarea, [tabindex]"

type Held = {site: HTMLElement; index: number}
type SiteFocusHook = Hook & {el: HTMLElement; held?: Held | null}

// Your sites: when a site is removed, the keyboard stays with the list. Focus
// moves to the next site's Remove site, else the one before it, else New site's
// Add site, so it never falls to the page. The next site slides up into the
// removed one's place; the one before it, or Add site, stays where it is and is
// brought into view once the list's motion has put the page back. When the list
// is read again, a site that stays may have its controls rebuilt, so focus
// returns to the same control in it. Focus moves only when it would otherwise
// fall to the page or leave with the site; a person who has moved on keeps it.
export const SiteFocus: Hook = {
  beforeUpdate(this: SiteFocusHook) {
    const active = document.activeElement
    const site = active?.closest<HTMLElement>("[data-site]")
    this.held = active && site && this.el.contains(site)
      ? {site, index: Array.from(site.querySelectorAll(CONTROLS)).indexOf(active)}
      : null
  },

  updated(this: SiteFocusHook) {
    const held = this.held
    this.held = null
    if (!held) return

    const active = document.activeElement
    const fell = !active || active === document.body
    if (held.site.isConnected && !held.site.hidden) {
      if (fell) held.site.querySelectorAll<HTMLElement>(CONTROLS)[held.index]?.focus({preventScroll: true})
      return
    }
    if (!fell && !held.site.contains(active)) return

    const sites = Array.from(this.el.querySelectorAll<HTMLElement>("[data-site]"))
    const at = sites.indexOf(held.site)
    const staying = (list: HTMLElement[]) => list.find(site => !site.hidden)
    const next = staying(sites.slice(at + 1))
    const target = (next ?? staying(sites.slice(0, at).reverse()))?.querySelector<HTMLElement>("[data-remove-site]")
      ?? document.getElementById("watchdog-add-site")
    if (!target) return
    target.focus({preventScroll: true})
    if (!next) requestAnimationFrame(() => target.scrollIntoView({block: "nearest"}))
  },
}
