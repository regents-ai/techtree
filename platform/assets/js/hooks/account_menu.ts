import type {Hook} from "../hook_composition"

type AccountMenuHook = Hook & {el: HTMLElement; cleanup?: () => void}

// The account menu the header's account button opens, on every page
// (TechtreeWeb.AccountMenuLive). The browser opens and closes it (`popover`) and
// closes it on Escape or a press outside it. A page change leaves it open, since
// it sits beside the page's own LiveView, so a link followed from it closes it.
export const AccountMenu: Hook = {
  mounted(this: AccountMenuHook) {
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null
      target?.closest("a[href]")?.closest<HTMLElement>("#account-menu")?.hidePopover()
    }

    this.el.addEventListener("click", onClick)
    this.cleanup = () => this.el.removeEventListener("click", onClick)
  },
  destroyed(this: AccountMenuHook) { this.cleanup?.() },
}
