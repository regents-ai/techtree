import type {Hook} from "../hook_composition"

type AccountShellHook = Hook & {el: HTMLElement; cleanup?: () => void; route?: string}

// Same native Credits dialog and refresh event as the template shell. The
// account tabs patch one LiveView, so opening a tab retains the surrounding frame.
export const AccountShell: Hook = {
  mounted(this: AccountShellHook) {
    this.route = this.el.dataset.route
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null
      const dialog = this.el.querySelector<HTMLDialogElement>("#shell-credits")
      if (!target || !dialog) return
      if (target.closest("[data-credits-open]") && !dialog.open) {
        dialog.showModal()
        dialog.querySelectorAll("[data-refresh-funds]").forEach(panel =>
          panel.dispatchEvent(new CustomEvent("ash:refresh-funds")))
      }
      if (target.closest("[data-credits-close]")) dialog.close()
    }
    this.el.addEventListener("click", onClick)
    this.cleanup = () => this.el.removeEventListener("click", onClick)
  },
  updated(this: AccountShellHook) {
    if (this.route !== this.el.dataset.route) {
      this.route = this.el.dataset.route
      this.el.querySelector<HTMLElement>("h1")?.focus({preventScroll: true})
    }
  },
  destroyed(this: AccountShellHook) { this.cleanup?.() },
}
