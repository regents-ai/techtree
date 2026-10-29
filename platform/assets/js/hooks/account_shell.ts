import type {Hook} from "../hook_composition"

type AccountShellHook = Hook & {el: HTMLElement; cleanup?: () => void; route?: string}

// The element the address's #fragment names, such as the Account page's pairing box.
const hashTarget = () => {
  const id = decodeURIComponent(window.location.hash.slice(1))
  return id ? document.getElementById(id) : null
}

/**
 * Brings `target`, what an address's #fragment names, into view. When it holds a
 * choice, such as the pairing box's agents, focus goes to the chosen one, or the
 * first, so the keyboard starts there.
 */
function arriveAt(target: HTMLElement) {
  target.scrollIntoView()
  const choices = [...target.querySelectorAll<HTMLInputElement>("input[type=radio]")]
  const choice = choices.find(radio => radio.checked) ?? choices[0]
  // Next frame: following the link, and LiveView's patch, each move focus first.
  if (choice) requestAnimationFrame(() => choice.focus({preventScroll: true}))
}

// Same native Credits dialog and refresh event as the template shell. The
// account tabs patch one LiveView, so opening a tab retains the surrounding frame.
// A page opened at a #fragment, such as the account menu's Pair New Agent, starts at
// what it names, and a link to one on the page already open brings it into view
// every press.
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
      // A press on the dialog's own backdrop lands on the dialog itself.
      if (target === dialog) dialog.close()
    }

    // A link to a #fragment of this page changes nothing LiveView sees when the
    // address already shows it, so what it names comes into view here, every press.
    // The account menu sits outside the page, so its links are heard on the document;
    // any other link, such as the skip link, is left to the browser.
    const onLink = (event: MouseEvent) => {
      const link = event.target instanceof Element
        ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!link?.hash || link.pathname !== window.location.pathname) return
      if (!link.closest("#account-menu") && !this.el.contains(link)) return
      const named = document.getElementById(decodeURIComponent(link.hash.slice(1)))
      if (named && this.el.contains(named)) arriveAt(named)
    }

    // LiveView records a new address only once its page is drawn, so what a
    // #fragment names is reached here, after the page has changed.
    const onNavigate = () => {
      const named = hashTarget()
      if (named && this.el.contains(named)) arriveAt(named)
    }

    this.el.addEventListener("click", onClick)
    document.addEventListener("click", onLink)
    window.addEventListener("phx:navigate", onNavigate)
    onNavigate()
    this.cleanup = () => {
      this.el.removeEventListener("click", onClick)
      document.removeEventListener("click", onLink)
      window.removeEventListener("phx:navigate", onNavigate)
    }
  },
  updated(this: AccountShellHook) {
    if (this.route !== this.el.dataset.route) {
      this.route = this.el.dataset.route
      this.el.querySelector<HTMLElement>("h1")?.focus({preventScroll: true})
    }
  },
  destroyed(this: AccountShellHook) { this.cleanup?.() },
}
