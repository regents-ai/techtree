// Invariant: dragging the theme switch's knob moves it with the finger and
// never past either end; let go, it settles on the nearer side, day from
// halfway; a press only becomes a drag once it has moved far enough sideways
// for the kind of pointer; and the light strip sits below the knob at night,
// above it by day, passing round the side it trails.
import {describe, expect, it} from "vitest"
import {dragStart, draggedPosition, isDrag, settleSide, sideOf, stripAngle, themeOf} from "../js/theme_switch/knob"

function numbers(seed: number) {
  let state = seed >>> 0
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0
    return state / 2 ** 32
  }
}

describe("a dragged knob", () => {
  it("stays between night and day however far the finger goes", () => {
    const next = numbers(3)
    for (let round = 0; round < 1000; round++) {
      const p = draggedPosition(next(), (next() - 0.5) * 400, next() * 60)
      expect(p).toBeGreaterThanOrEqual(0)
      expect(p).toBeLessThanOrEqual(1)
    }
  })

  it("follows the finger: further right is never further left", () => {
    const next = numbers(5)
    for (let round = 0; round < 300; round++) {
      const start = next()
      const travel = 1 + next() * 40
      const dx = (next() - 0.5) * 100
      expect(draggedPosition(start, dx + next() * 10, travel)).toBeGreaterThanOrEqual(draggedPosition(start, dx, travel))
    }
  })

  it("crosses the whole track when the finger crosses the knob's travel", () => {
    expect(draggedPosition(0, 22, 22)).toBe(1)
    expect(draggedPosition(1, -22, 22)).toBe(0)
    expect(draggedPosition(0, 11, 22)).toBeCloseTo(0.5, 10)
    expect(draggedPosition(0.3, 0, 22)).toBe(0.3)
  })

  it("stays put on a track with no room to travel", () => {
    expect(draggedPosition(0.4, 30, 0)).toBe(0.4)
    expect(draggedPosition(0.4, 30, -5)).toBe(0.4)
    expect(draggedPosition(0.4, 30, Number.NaN)).toBe(0.4)
  })
})

describe("a released knob", () => {
  it("settles on the nearer side, day from halfway", () => {
    expect(settleSide(0)).toBe(0)
    expect(settleSide(0.4999)).toBe(0)
    expect(settleSide(0.5)).toBe(1)
    expect(settleSide(1)).toBe(1)
    const next = numbers(9)
    for (let round = 0; round < 500; round++) {
      const p = next()
      expect(Math.abs(p - settleSide(p))).toBeLessThanOrEqual(0.5)
    }
  })

  it("names night dark and day light, both ways", () => {
    expect(themeOf(sideOf("dark"))).toBe("dark")
    expect(themeOf(sideOf("light"))).toBe("light")
    expect(sideOf("dark")).toBe(0)
    expect(sideOf("light")).toBe(1)
  })
})

describe("a press", () => {
  it("becomes a drag once it has gone far enough sideways for its pointer", () => {
    for (const [type, distance] of [["mouse", 3], ["pen", 4], ["touch", 6]] as const) {
      expect(dragStart(type)).toBe(distance)
      expect(isDrag(distance - 0.5, type)).toBe(false)
      expect(isDrag(distance, type)).toBe(true)
      expect(isDrag(-distance, type)).toBe(true)
    }
  })

  it("treats a pointer it does not know as a finger", () => {
    expect(dragStart("")).toBe(dragStart("touch"))
    expect(dragStart("stylus-of-the-future")).toBe(dragStart("touch"))
  })
})

describe("the light strip", () => {
  it("sits below at night, beside the trailing side halfway and above by day", () => {
    const down = (angle: number) => [Math.cos(angle), Math.sin(angle)]
    const [nightX, nightY] = down(stripAngle(0))
    expect(nightX).toBeCloseTo(0, 10)
    expect(nightY).toBeCloseTo(1, 10)
    const [halfX, halfY] = down(stripAngle(0.5))
    expect(halfX).toBeCloseTo(-1, 10)
    expect(halfY).toBeCloseTo(0, 10)
    const [dayX, dayY] = down(stripAngle(1))
    expect(dayX).toBeCloseTo(0, 10)
    expect(dayY).toBeCloseTo(-1, 10)
  })

  it("goes round one way only and stops at either end", () => {
    let last = stripAngle(0)
    for (let k = 1; k <= 100; k++) {
      const angle = stripAngle(k / 100)
      expect(angle).toBeGreaterThan(last)
      last = angle
    }
    expect(stripAngle(-1)).toBe(stripAngle(0))
    expect(stripAngle(2)).toBe(stripAngle(1))
  })
})
