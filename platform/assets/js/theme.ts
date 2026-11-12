/**
 * The colour theme, light or dark, and the one place it is kept.
 *
 * Until the visitor chooses, the page carries no theme and the shared colours
 * follow the device, dark unless it asks for light. Choosing writes the theme
 * to the cookie the server reads (`TechtreeWeb.Router`), so the next page is
 * drawn in it, and puts it on the page at once. The choice is never sent
 * anywhere else.
 */
export type Theme = "light" | "dark"

export const THEME_COOKIE = "techtree_theme"
const themeMaxAge = 60 * 60 * 24 * 365
// The browser's own bars, in each theme's page colour.
const themeColors: Record<Theme, string> = {dark: "#0D1611", light: "#F3F5EF"}
const deviceLight = "(prefers-color-scheme: light)"

/** The theme the visitor chose; nothing while the device still decides. */
export function chosenTheme(): Theme | undefined {
  const prefix = `${THEME_COOKIE}=`
  const value = document.cookie
    .split("; ")
    .find(cookie => cookie.startsWith(prefix))
    ?.slice(prefix.length)

  return value === "light" || value === "dark" ? value : undefined
}

/** The theme on screen: the page's own once chosen, otherwise the device's. */
export function showingTheme(): Theme {
  const theme = document.documentElement.dataset.theme
  if (theme === "light" || theme === "dark") return theme
  return window.matchMedia(deviceLight).matches ? "light" : "dark"
}

/**
 * Live navigation keeps the document, so each page restates its theme: the
 * visitor's choice, or none so the device decides.
 */
export function syncTheme(): void {
  const root = document.documentElement
  const theme = chosenTheme()
  if (theme) root.dataset.theme = theme
  else delete root.dataset.theme
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", theme ?? "dark light")
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach(meta => {
    meta.content = themeColors[theme ?? (meta.media.includes("light") ? "light" : "dark")]
  })
}

/** Keeps `theme` for a year and shows it now. */
export function chooseTheme(theme: Theme): void {
  const secure = window.location.protocol === "https:" ? "; Secure" : ""
  document.cookie = `${THEME_COOKIE}=${theme}; Path=/; Max-Age=${themeMaxAge}; SameSite=Lax${secure}`
  syncTheme()
}

/**
 * Calls `listener` whenever the theme on screen changes, whoever changed it:
 * a switch on the page, or the device while no choice has been made. Returns
 * the way to stop.
 */
export function watchTheme(listener: (theme: Theme) => void): () => void {
  let last = showingTheme()
  const check = () => {
    const next = showingTheme()
    if (next === last) return
    last = next
    listener(next)
  }
  const page = new MutationObserver(check)
  page.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]})
  const device = window.matchMedia(deviceLight)
  device.addEventListener("change", check)
  return () => {
    page.disconnect()
    device.removeEventListener("change", check)
  }
}
