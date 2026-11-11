import type {Hook} from "../hook_composition"

type AccountShellHook = Hook & {el: HTMLElement; route?: string}

// The account tabs patch one LiveView, so opening a tab retains the surrounding
// frame; the new tab's heading takes focus.
export const AccountShell: Hook = {
  mounted(this: AccountShellHook) {
    this.route = this.el.dataset.route
  },
  updated(this: AccountShellHook) {
    if (this.route !== this.el.dataset.route) {
      this.route = this.el.dataset.route
      this.el.querySelector<HTMLElement>("h1")?.focus({preventScroll: true})
    }
  },
}
