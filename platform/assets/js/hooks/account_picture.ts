import type {Hook} from "../hook_composition"

interface AccountPictureHook {
  el: HTMLElement
  js(): {ignoreAttributes(el: HTMLElement, attrs: string[]): void}
}

// An account's ENS picture lies over the squares drawn from its wallet. Once
// it has arrived the squares are hidden (`data-shown`), and redraws keep that.
export const AccountPicture: Hook = {
  mounted(this: AccountPictureHook) {
    this.js().ignoreAttributes(this.el, ["data-shown"])

    const picture = this.el.querySelector<HTMLImageElement>("img + img")
    if (!picture) return

    const shown = () => this.el.toggleAttribute("data-shown", true)
    if (picture.complete && picture.naturalWidth > 0) shown()
    else picture.addEventListener("load", shown, {once: true})
  },
}
