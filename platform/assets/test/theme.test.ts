// Invariant: a theme chosen on any switch is written to the cookie the server
// reads and shown on the page at once; the page reads back only the two themes
// it offers; and every switch hears each change of the theme on screen once,
// whoever made it.
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest"
import {chooseTheme, chosenTheme, showingTheme, syncTheme, watchTheme, type Theme} from "../js/theme"

type Listener = () => void

let cookies: Map<string, string>
let written: string[]
let dataset: Record<string, string>
let deviceLight: boolean
let deviceListeners: Set<Listener>
let pageObservers: Set<Listener>
let metas: {name: string; media: string; content: string}[]
let location: {pathname: string; protocol: string}

beforeEach(() => {
  cookies = new Map()
  written = []
  deviceLight = false
  deviceListeners = new Set()
  pageObservers = new Set()
  location = {pathname: "/app", protocol: "http:"}
  metas = [
    {name: "color-scheme", media: "", content: "dark light"},
    {name: "theme-color", media: "(prefers-color-scheme: dark)", content: ""},
    {name: "theme-color", media: "(prefers-color-scheme: light)", content: ""},
  ]
  // The page's own attributes: a change to data-theme reaches every observer, as the browser's would.
  dataset = new Proxy({} as Record<string, string>, {
    set(target, name: string, value: string) {
      const changed = target[name] !== value
      target[name] = value
      if (changed && name === "theme") pageObservers.forEach(observer => observer())
      return true
    },
    deleteProperty(target, name: string) {
      const had = name in target
      delete target[name]
      if (had && name === "theme") pageObservers.forEach(observer => observer())
      return true
    },
  })
  const meta = (name: string) => metas.filter(m => m.name === name).map(m => ({
    get media() { return m.media },
    get content() { return m.content },
    set content(value: string) { m.content = value },
    setAttribute: (_: string, value: string) => void (m.content = value),
  }))
  vi.stubGlobal("document", {
    documentElement: {dataset},
    get cookie() {
      return [...cookies].map(([name, value]) => `${name}=${value}`).join("; ")
    },
    set cookie(line: string) {
      written.push(line)
      const [pair] = line.split("; ")
      const [name, value] = pair.split("=")
      cookies.set(name, value)
    },
    querySelector: (selector: string) => meta(selector.includes("color-scheme") ? "color-scheme" : "theme-color")[0] ?? null,
    querySelectorAll: () => meta("theme-color"),
  })
  vi.stubGlobal("window", {
    location,
    matchMedia: () => ({
      get matches() { return deviceLight },
      addEventListener: (_: string, listener: Listener) => void deviceListeners.add(listener),
      removeEventListener: (_: string, listener: Listener) => void deviceListeners.delete(listener),
    }),
  })
  vi.stubGlobal("MutationObserver", class {
    constructor(private seen: Listener) {}
    observe() { pageObservers.add(this.seen) }
    disconnect() { pageObservers.delete(this.seen) }
  })
})

afterEach(() => vi.unstubAllGlobals())

describe("choosing a theme", () => {
  it("writes the cookie the server reads and shows the theme at once", () => {
    chooseTheme("light")
    expect(chosenTheme()).toBe("light")
    expect(written.at(-1)).toMatch(/^techtree_theme=light; Path=\/; Max-Age=31536000; SameSite=Lax$/)
    expect(dataset.theme).toBe("light")
    expect(showingTheme()).toBe("light")
    expect(metas[0].content).toBe("light")
    expect(metas.slice(1).map(m => m.content)).toEqual(["#F3F5EF", "#F3F5EF"])

    chooseTheme("dark")
    expect(chosenTheme()).toBe("dark")
    expect(dataset.theme).toBe("dark")
    expect(metas.slice(1).map(m => m.content)).toEqual(["#0D1611", "#0D1611"])
  })

  it("keeps the cookie to secure connections on a secure page", () => {
    location.protocol = "https:"
    chooseTheme("dark")
    expect(written.at(-1)).toMatch(/; Secure$/)
  })
})

describe("reading the theme", () => {
  it("accepts only the two themes the page offers", () => {
    for (const value of ["blue", "", "Light", "light;"]) {
      cookies.set("techtree_theme", value)
      expect(chosenTheme()).toBeUndefined()
    }
    cookies.clear()
    cookies.set("other", "light")
    expect(chosenTheme()).toBeUndefined()
  })

  it("follows the device until a theme is chosen, then the choice", () => {
    syncTheme()
    expect(dataset.theme).toBeUndefined()
    expect(metas[0].content).toBe("dark light")
    expect(showingTheme()).toBe("dark")
    deviceLight = true
    expect(showingTheme()).toBe("light")
    cookies.set("techtree_theme", "dark")
    syncTheme()
    expect(showingTheme()).toBe("dark")
  })
})

describe("watching the theme", () => {
  it("hears each change once, whoever made it, and nothing after it stops", () => {
    const heard: Theme[] = []
    const stop = watchTheme(theme => heard.push(theme))

    chooseTheme("light") // another switch
    chooseTheme("light") // the same theme stated again
    syncTheme() // live navigation restating it
    dataset.theme = "dark" // the server's next page
    delete dataset.theme // nothing chosen: the device decides, still dark
    deviceLight = true
    deviceListeners.forEach(listener => listener()) // the device turns light
    expect(heard).toEqual(["light", "dark", "light"])

    stop()
    chooseTheme("dark")
    expect(heard).toEqual(["light", "dark", "light"])
    expect(pageObservers.size).toBe(0)
    expect(deviceListeners.size).toBe(0)
  })
})
