import type {Hook} from "../hook_composition"

type AccountShellHook = Hook & {el: HTMLElement; route?: string}

// The account tabs patch one LiveView, so opening a tab retains the surrounding
// frame; the new tab's heading takes focus. The shell names the open tab in
// `data-destination`, which the kit's ShellViews also reads to glide it in.
export const AccountShell: Hook = {
  mounted(this: AccountShellHook) {
    this.route = this.el.dataset.destination
  },
  updated(this: AccountShellHook) {
    if (this.route !== this.el.dataset.destination) {
      this.route = this.el.dataset.destination
      this.el.querySelector<HTMLElement>("h1")?.focus({preventScroll: true})
    }
  },
}
