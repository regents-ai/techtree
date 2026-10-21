/** Delegated CTA motion also covers buttons arriving in LiveView patches. */
import {createScope, type Scope} from "animejs"
import {play, still} from "./shared"

const active = new Map<Element, Scope>()
export const CTA = ".rg-button:not(.rg-button--quiet):not(.rg-copy):not(.rg-theme-toggle):not([role='tab'])"

function stop(el: Element) {
  active.get(el)?.revert()
  active.delete(el)
}

export function mountButtons(doc: Document) {
  const reset = () => { for (const el of active.keys()) stop(el) }
  const move = (event: PointerEvent) => {
    if (!(event.target instanceof Element)) return
    const el = event.target.closest(CTA)
    if (!el || still(el) || el.matches(":disabled, [disabled], [aria-disabled='true']")) return
    const press = event.type === "pointerdown"
    if (press && (event.button !== 0 || !event.isPrimary)) return
    if (!press && (event.pointerType !== "mouse" ||
      (event.relatedTarget instanceof Node && el.contains(event.relatedTarget)))) return
    stop(el)
    const scope = createScope({root: el as HTMLElement})
    active.set(el, scope)
    scope.add(() => {
      const animation = play(el, press
        ? {"--rg-press-scale": [1, 0.97, 1], duration: 240, ease: "out(3)"}
        : {"--rg-chevron-x": ["0px", "4px", "0px"], duration: 280, ease: "inOut(2)"})
      animation.then(() => { if (active.get(el) === scope) stop(el) })
    })
  }
  doc.addEventListener("pointerover", move)
  doc.addEventListener("pointerdown", move)
  doc.addEventListener("keydown", reset)
  doc.addEventListener("phx:page-loading-start", reset)
  doc.defaultView?.addEventListener("pagehide", reset)
  doc.defaultView?.matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", reset)
}
