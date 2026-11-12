// Invariant: one model of light serves both themes. The theme switch's strip
// colours stand the same distance from the page whether it is the dark one or
// the light one, lighter on a dark page and deeper on a light one, their hue
// kept, and always a colour the screen can show.
import {describe, expect, it} from "vitest"
import {asLight, distance, LIGHT_DISTANCE, oklab, type Rgb} from "../js/theme_switch/light"

const hex = (value: string): Rgb => [1, 3, 5].map(i => parseInt(value.slice(i, i + 2), 16) / 255) as unknown as Rgb

const NIGHT = hex("#AECACD") // powder blue
const DAY = hex("#FF5B19") // tangerine tango
// Techtree's own page colours (js/theme.ts) beside the shared design system's.
const DARK_PAGES = ["#0D1611", "#0B0B0B", "#161616"].map(hex)
const LIGHT_PAGES = ["#F3F5EF", "#F6F4EA", "#E5E3D2"].map(hex)

function numbers(seed: number) {
  let state = seed >>> 0
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0
    return state / 2 ** 32
  }
}

const randomColour = (next: () => number): Rgb => [next(), next(), next()]
const hue = (colour: Rgb) => {
  const [, a, b] = oklab(colour)
  return Math.atan2(b, a)
}
const chroma = (colour: Rgb) => Math.hypot(oklab(colour)[1], oklab(colour)[2])

describe("the switch's lights on the site's pages", () => {
  it("stand as far from the dark page as from the light one", () => {
    const standing = [...DARK_PAGES, ...LIGHT_PAGES].flatMap(page => [NIGHT, DAY].map(light => distance(asLight(light, page), page)))
    for (const value of standing) expect(Math.abs(value - LIGHT_DISTANCE)).toBeLessThan(0.035)
    expect(Math.max(...standing) - Math.min(...standing)).toBeLessThan(0.035)
  })

  it("keep their hue", () => {
    for (const page of [...DARK_PAGES, ...LIGHT_PAGES]) {
      for (const light of [NIGHT, DAY]) {
        const turn = Math.abs(Math.atan2(Math.sin(hue(asLight(light, page)) - hue(light)), Math.cos(hue(asLight(light, page)) - hue(light))))
        expect(turn).toBeLessThan(0.12)
      }
    }
  })
})

describe("any light on any page", () => {
  it("is lighter than a dark page and deeper than a light one", () => {
    const next = numbers(23)
    for (let round = 0; round < 300; round++) {
      const page = randomColour(next)
      const light = asLight(randomColour(next), page)
      const [pageL] = oklab(page)
      const [lightL] = oklab(light)
      if (pageL < 0.3) expect(lightL).toBeGreaterThan(pageL)
      if (pageL > 0.8) expect(lightL).toBeLessThan(pageL)
    }
  })

  it("is a colour the screen can show and never further than asked", () => {
    const next = numbers(29)
    for (let round = 0; round < 500; round++) {
      const page = randomColour(next)
      const reach = 0.1 + next() * 0.6
      const light = asLight(randomColour(next), page, reach)
      for (const channel of light) {
        expect(channel).toBeGreaterThanOrEqual(0)
        expect(channel).toBeLessThanOrEqual(1)
      }
      expect(distance(light, page)).toBeLessThanOrEqual(reach + 1e-3)
    }
  })

  it("reaches the distance asked whenever the screen has room", () => {
    const next = numbers(31)
    let reached = 0
    for (let round = 0; round < 300; round++) {
      const page = randomColour(next)
      const colour = randomColour(next)
      const light = asLight(colour, page, 0.3)
      // Nothing was lost to the screen's limits when the light kept its strength.
      if (Math.abs(chroma(light) - chroma(colour)) < 1e-3 || distance(colour, page) > 0.3) {
        if (Math.abs(distance(light, page) - 0.3) < 2e-3) reached += 1
      }
    }
    expect(reached).toBeGreaterThan(100)
  })

  it("is the colour itself when it already stands just that far away, on the far side", () => {
    const next = numbers(37)
    let checked = 0
    while (checked < 100) {
      const page = randomColour(next)
      const colour = randomColour(next)
      const [pageL] = oklab(page)
      const [colourL] = oklab(colour)
      if (pageL < 0.5 ? colourL < pageL : colourL > pageL) continue
      checked += 1
      const light = asLight(colour, page, distance(colour, page))
      light.forEach((channel, i) => expect(channel).toBeCloseTo(colour[i], 3))
    }
  })
})
