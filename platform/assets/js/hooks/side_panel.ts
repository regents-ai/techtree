import type {Hook} from "../hook_composition"

type SidePanelHook = Hook & {el: HTMLElement; cleanup?: () => void}

// The side panel the account name opens, on every page (TechtreeWeb.SidePanelLive).
// Whether it is open lives on <html data-aside>, which the server first draws
// from the cookie written here (the router's put_aside), so LiveView never
// patches it away. On a phone, where the panel covers the page, it opens only
// when the person opens it on this page (<html data-aside-here>), never from the
// remembered state.

const yearInSeconds = 60 * 60 * 24 * 365
const root = () => document.documentElement
const covering = window.matchMedia("(max-width: 47.99rem)")

export const asideOpen = () =>
  root().dataset.aside === "open" && (!covering.matches || root().dataset.asideHere !== undefined)

// Closed is the default, so only open is kept.
function remember(open: boolean) {
  const secure = window.location.protocol === "https:" ? "; Secure" : ""
  const age = open ? yearInSeconds : 0
  document.cookie = `techtree_aside=${open ? "open" : "closed"}; Path=/; Max-Age=${age}; SameSite=Lax${secure}`
}

export const SidePanel: Hook = {
  mounted(this: SidePanelHook) {
    const aside = () => document.querySelector<HTMLElement>("#shell-aside")
    const chip = () => document.querySelector<HTMLElement>("#account-chip")

    const sync = () => {
      document.querySelectorAll("[data-aside-toggle]").forEach(toggle =>
        toggle.setAttribute("aria-expanded", String(asideOpen())))
    }

    const setAside = (open: boolean) => {
      root().dataset.aside = open ? "open" : "closed"
      if (open) root().dataset.asideHere = ""
      else delete root().dataset.asideHere
      remember(open)
      sync()
      // Opened, focus moves into it, so Escape closes it and returns focus to the
      // name, and what it shows is read again.
      if (!open) return
      // On a phone it hangs under the header, which keeps the name that closes it.
      if (covering.matches) window.scrollTo({top: 0})
      aside()?.focus({preventScroll: true})
      aside()
        ?.querySelectorAll("[data-read-on-open]")
        .forEach(reader => reader.dispatchEvent(new CustomEvent("ash:aside-opened")))
    }

    // The name in the header toggles it; a page's own Pair New Agent button opens it.
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null
      if (!target) return
      if (target.closest("[data-aside-toggle]")) return setAside(!asideOpen())
      if (target.closest("[data-aside-open]")) return setAside(true)
      // On a phone, where the panel covers the page, a link inside it closes it.
      if (covering.matches && target.closest("#shell-aside a")) setAside(false)
    }

    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && asideOpen() && aside()?.contains(document.activeElement)) {
        event.preventDefault()
        setAside(false)
        chip()?.focus()
      }
    }

    document.addEventListener("click", onClick)
    document.addEventListener("keydown", onKeydown)
    covering.addEventListener("change", sync)
    sync()

    this.cleanup = () => {
      document.removeEventListener("click", onClick)
      document.removeEventListener("keydown", onKeydown)
      covering.removeEventListener("change", sync)
    }
  },
  updated(this: SidePanelHook) {
    document.querySelectorAll("[data-aside-toggle]").forEach(toggle =>
      toggle.setAttribute("aria-expanded", String(asideOpen())))
  },
  destroyed(this: SidePanelHook) { this.cleanup?.() },
}
