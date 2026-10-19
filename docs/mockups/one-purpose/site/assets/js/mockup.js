// The mockup's small behaviours: theme switch, the GPU crown, copy buttons,
// the button motion from the template's kit, and a light rise for the steps.
import {animate, createScope, stagger, utils} from "/assets/js/anime.esm.min.js"
import {createOpticsController} from "/assets/js/optics_controller.js"

const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches
const params = new URLSearchParams(location.search)
if (params.has("shot")) document.documentElement.dataset.shot = ""

// Theme: same cookie and crown colours as the live site.
const THEMES = {light: {crownVariant: "2"}, dark: {crownVariant: "4"}}
const lightDevice = matchMedia("(prefers-color-scheme: light)")
const chosenTheme = () => document.cookie.match(/(?:^|; )techtree_theme=(light|dark)/)?.[1]
const showingTheme = () => chosenTheme() ?? (lightDevice.matches ? "light" : "dark")

function syncTheme() {
  const chosen = chosenTheme()
  if (chosen) document.documentElement.dataset.theme = chosen
  else delete document.documentElement.dataset.theme
  const theme = showingTheme()
  document.querySelectorAll('[data-optics-kind="crown"] [data-optics-canvas]').forEach(canvas => {
    canvas.dataset.crownVariant = THEMES[theme].crownVariant
  })
  document.dispatchEvent(new CustomEvent("techtree:themechange", {detail: {theme, crownVariant: THEMES[theme].crownVariant}}))
}

document.addEventListener("click", event => {
  if (!event.target.closest?.("[data-theme-toggle]")) return
  const theme = showingTheme() === "dark" ? "light" : "dark"
  document.cookie = `techtree_theme=${theme}; Path=/; Max-Age=31536000; SameSite=Lax`
  syncTheme()
})
lightDevice.addEventListener("change", syncTheme)
syncTheme()

// The crown: the live site's own vgpu drawing, still picture when it cannot draw.
document.querySelectorAll("[data-optics-kind]").forEach(root => createOpticsController(root).mount())

// Copy buttons, in the live site's four states.
document.addEventListener("click", async event => {
  const button = event.target.closest?.("[data-copy-target], [data-copy-link]")
  if (!button) return
  const text = button.hasAttribute("data-copy-link")
    ? location.href.split("?")[0]
    : document.getElementById(button.dataset.copyTarget).textContent.trim()
  try {
    await navigator.clipboard.writeText(text)
    button.dataset.copyState = "copied"
  } catch {
    button.dataset.copyState = "failed"
  }
  clearTimeout(button.copyTimer)
  button.copyTimer = setTimeout(() => delete button.dataset.copyState, 1600)
})

// Button motion, as the template's kit plays it: the arrow nudges on a mouse
// hover, the button gives a little on a press. The press never waits on it.
const CTA = ".rg-button:not(.rg-button--quiet):not(.rg-copy):not(.rg-theme-toggle):not([role='tab'])"
const PRESSABLE = ".rg-button:not(.rg-theme-toggle)"
const active = new Map()
const stop = el => { active.get(el)?.revert(); active.delete(el) }

function move(event) {
  const press = event.type === "pointerdown"
  const el = event.target.closest?.(press ? PRESSABLE : CTA)
  if (!el || reduced()) return
  if (press && (event.button !== 0 || !event.isPrimary)) return
  if (!press && (event.pointerType !== "mouse" || el.contains(event.relatedTarget))) return
  stop(el)
  const scope = createScope({root: el})
  active.set(el, scope)
  scope.add(() => {
    const animation = animate(el, press
      ? {"--rg-press-scale": [1, 0.97, 1], duration: 240, ease: "out(3)"}
      : {"--rg-chevron-x": ["0px", "4px", "0px"], duration: 280, ease: "inOut(2)"})
    animation.then(() => {
      utils.cleanInlineStyles(animation)
      if (active.get(el) === scope) stop(el)
    })
  })
}
document.addEventListener("pointerover", move)
document.addEventListener("pointerdown", move)
document.addEventListener("keydown", () => { for (const el of active.keys()) stop(el) })

// Steps rise in once, when they first come into view below the fold.
const reveals = [...document.querySelectorAll("[data-reveal]")]
if (reveals.length && !reduced() && !document.documentElement.hasAttribute("data-shot")) {
  const below = reveals.filter(el => el.getBoundingClientRect().top > innerHeight)
  reveals.filter(el => !below.includes(el)).forEach(el => { el.dataset.revealed = "" })
  document.documentElement.dataset.motionReady = ""
  const observer = new IntersectionObserver(entries => {
    const shown = entries.filter(entry => entry.isIntersecting).map(entry => entry.target)
    if (!shown.length) return
    utils.set(shown, {opacity: 0})
    shown.forEach(el => { el.dataset.revealed = ""; observer.unobserve(el) })
    animate(shown, {
      opacity: [0, 1],
      y: [8, 0],
      duration: 360,
      delay: stagger(50),
      ease: "out(3)",
      onComplete: done => utils.cleanInlineStyles(done),
    })
  }, {rootMargin: "0px 0px -10% 0px"})
  below.forEach(el => observer.observe(el))
}
