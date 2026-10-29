// The header's Menu, below a wide screen, opens the list of pages over the page
// (#site-pages, a popover). While it is open the page and its footer are out of
// reach: every part of the frame but the header goes inert until it closes, so Tab
// and a press can't land on a link behind it. A wide screen shows the pages in a
// row with no Menu, so a screen that widens past one closes the list.
export function installSiteMenu() {
  const wideScreen = window.matchMedia("(min-width: 64rem)")
  wideScreen.addEventListener("change", () => {
    const list = document.getElementById("site-pages")
    if (wideScreen.matches && list?.matches(":popover-open")) list.hidePopover()
  })

  document.addEventListener("toggle", event => {
    if (!(event.target instanceof HTMLElement) || event.target.id !== "site-pages") return
    const open = (event as ToggleEvent).newState === "open"
    document.querySelectorAll<HTMLElement>(".techtree-frame > :not(.masthead)").forEach(part => {
      part.inert = open
    })
  }, true)
}
