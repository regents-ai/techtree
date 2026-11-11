import type {Hook} from "../hook_composition"

type AccountMenuHook = Hook & {el: HTMLElement; cleanup?: () => void}

// The account menu the header's account button opens, on every page
// (TechtreeWeb.AccountMenuLive). The browser opens and closes it (`popover`) and
// closes it on Escape or a press outside it. A page change leaves it open, since
// it sits beside the page's own LiveView, so a link followed from it closes it.
//
// The same LiveView holds the pairing window. Pair New Agent, in the menu and on the
// Agents page, opens it; the menu closes first. It opens on the list of agents
// while none is chosen, with the keyboard on the dropdown. Its close button, a
// press on its backdrop and Escape close it.
export const AccountMenu: Hook = {
  mounted(this: AccountMenuHook) {
    const pairing = () => this.el.querySelector<HTMLDialogElement>("#shell-pairing")

    const openPairing = () => {
      const dialog = pairing()
      if (!dialog || dialog.open) return
      dialog.showModal()
      const pick = dialog.querySelector<HTMLDetailsElement>("details.rg-pill-select")
      if (!pick) return
      if (!pick.querySelector("input:checked")) pick.open = true
      pick.querySelector<HTMLElement>(":scope > summary")?.focus()
    }

    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null
      if (!target) return
      const opener = target.closest<HTMLElement>("[data-pair-open]")
      if (opener) {
        opener.closest<HTMLElement>("[popover]")?.hidePopover()
        return openPairing()
      }
      if (target.closest("[data-pair-close]") || target === pairing()) return pairing()?.close()
      target.closest("a[href]")?.closest<HTMLElement>("#account-menu")?.hidePopover()
    }

    document.addEventListener("click", onClick)
    this.cleanup = () => document.removeEventListener("click", onClick)
  },
  destroyed(this: AccountMenuHook) { this.cleanup?.() },
}
