// Invariant: the theme switch's two pictures of blocks, read from the still face,
// become points round the grid's centre; when they have as many blocks, every
// block of one is paired with exactly one of the other by angle, so the swarm
// neither loses nor doubles a block on its way across; and at rest every block
// sits square on whole canvas pixels with a hairline between neighbours.
import {describe, expect, it} from "vitest"
import {iconGrid, ICON_FILL, pairByAngle, pixelsOf, turnBetween, wrapAngle, type Cell, type Pixel} from "../js/theme_switch/pixels"

// A small, seeded source of numbers, so every run checks the same cases.
function numbers(seed: number) {
  let state = seed >>> 0
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0
    return state / 2 ** 32
  }
}

function randomPicture(next: () => number, count: number): Pixel[] {
  return Array.from({length: count}, () => {
    const x = Math.round(next() * 8 - 4)
    const y = Math.round(next() * 8 - 4)
    return {x, y, angle: wrapAngle(Math.atan2(y, x)), radius: Math.hypot(x, y)}
  })
}

const key = (pixel: Pixel) => `${pixel.x},${pixel.y}`

/** The blocks of a picture drawn row by row, "#" for a block. */
const cellsOf = (rows: readonly string[]): Cell[] =>
  rows.flatMap((line, row) => [...line].flatMap((mark, col) => (mark === "#" ? [{col, row}] : [])))

// Two little pictures with as many blocks: a crescent and a sun.
const CRESCENT = [".##....", "##.....", "#......", "#......", "#.....#", "##...##", ".#####."]
const SUNBURST = ["#..#..#", ".......", "..###..", "#.###.#", "..###..", ".......", "#..#..#"]

function expectOneToOne(from: readonly Pixel[], to: readonly Pixel[], pairs: readonly {moon: Pixel; sun: Pixel}[]) {
  expect(pairs).toHaveLength(from.length)
  expect(new Set(pairs.map(pair => pair.moon))).toEqual(new Set(from))
  expect(new Set(pairs.map(pair => pair.sun))).toEqual(new Set(to))
}

describe("a picture's blocks", () => {
  it("become points round the grid's centre, right and down from it", () => {
    const pixels = pixelsOf([{col: 0, row: 0}, {col: 3, row: 3}, {col: 6, row: 3}, {col: 3, row: 6}], 7)
    expect(pixels.map(pixel => [pixel.x, pixel.y])).toEqual([[-3, -3], [0, 0], [3, 0], [0, 3]])
    expect(pixels[2].angle).toBeCloseTo(0, 10)
    expect(pixels[3].angle).toBeCloseTo(Math.PI / 2, 10)
    expect(pixels[0].radius).toBeCloseTo(Math.hypot(3, 3), 10)
  })

  it("sit half a cell from the centre on an even grid", () => {
    const [pixel] = pixelsOf([{col: 2, row: 1}], 4)
    expect([pixel.x, pixel.y]).toEqual([0.5, -0.5])
  })

  it("of two pictures with as many blocks pair one to one", () => {
    const moon = pixelsOf(cellsOf(CRESCENT), 7)
    const sun = pixelsOf(cellsOf(SUNBURST), 7)
    expect(moon).toHaveLength(sun.length)
    const pairs = pairByAngle(moon, sun)
    expect(new Set(pairs.map(pair => key(pair.moon)))).toEqual(new Set(moon.map(key)))
    expect(new Set(pairs.map(pair => key(pair.sun)))).toEqual(new Set(sun.map(key)))
  })
})

describe("pairing by angle", () => {
  it("is one to one for any two pictures of the same size", () => {
    const next = numbers(7)
    for (let round = 0; round < 200; round++) {
      const count = 1 + Math.floor(next() * 40)
      const from = randomPicture(next, count)
      const to = randomPicture(next, count)
      expectOneToOne(from, to, pairByAngle(from, to))
    }
  })

  it("keeps the first picture's clockwise order", () => {
    const next = numbers(11)
    for (let round = 0; round < 100; round++) {
      const count = 2 + Math.floor(next() * 30)
      const pairs = pairByAngle(randomPicture(next, count), randomPicture(next, count))
      for (let i = 1; i < pairs.length; i++) expect(pairs[i].moon.angle).toBeGreaterThanOrEqual(pairs[i - 1].moon.angle)
    }
  })

  it("turns no further, all told, than any other clockwise pairing", () => {
    const next = numbers(13)
    for (let round = 0; round < 100; round++) {
      const count = 1 + Math.floor(next() * 25)
      const from = randomPicture(next, count)
      const to = randomPicture(next, count)
      const total = (pairs: readonly {moon: Pixel; sun: Pixel}[]) =>
        pairs.reduce((sum, pair) => sum + Math.abs(turnBetween(pair.moon.angle, pair.sun.angle)), 0)
      const chosen = total(pairByAngle(from, to))
      const moons = [...from].sort((a, b) => a.angle - b.angle || a.radius - b.radius)
      const suns = [...to].sort((a, b) => a.angle - b.angle || a.radius - b.radius)
      for (let shift = 0; shift < count; shift++) {
        const other = moons.map((moon, i) => ({moon, sun: suns[(i + shift) % count]}))
        expect(chosen).toBeLessThanOrEqual(total(other) + 1e-9)
      }
    }
  })

  it("pairs a picture with itself pixel for pixel", () => {
    const moon = pixelsOf(cellsOf(CRESCENT), 7)
    for (const pair of pairByAngle(moon, moon)) expect(key(pair.sun)).toBe(key(pair.moon))
  })

  it("refuses two pictures of different sizes", () => {
    const next = numbers(17)
    expect(() => pairByAngle(randomPicture(next, 3), randomPicture(next, 4))).toThrow()
  })
})

describe("turns between angles", () => {
  it("are the shortest way round, never more than half a turn", () => {
    const next = numbers(19)
    for (let round = 0; round < 500; round++) {
      const from = next() * 20 - 10
      const to = next() * 20 - 10
      const turn = turnBetween(from, to)
      expect(Math.abs(turn)).toBeLessThanOrEqual(Math.PI + 1e-9)
      expect(Math.abs(turnBetween(from + turn, to))).toBeLessThan(1e-9)
    }
  })
})

describe("the block grid", () => {
  it("sets every block's edges on whole pixels at rest, a hairline apart", () => {
    const next = numbers(41)
    for (let round = 0; round < 500; round++) {
      const grid = 5 + Math.floor(next() * 12)
      const side = 20 + next() * 120
      const centre = [next() * 300, next() * 300] as const
      const {x, y, cell, half} = iconGrid(centre, side, grid, 1)
      expect(Number.isInteger(cell)).toBe(true)
      const block = 2 * half * cell
      expect(Math.abs(block - Math.round(block))).toBeLessThan(1e-9)
      if (cell >= 3) expect(cell - block).toBeGreaterThanOrEqual(1)
      for (const offset of [(grid - 1) / 2, -(grid - 1) / 2, ((grid - 1) / 2) % 1]) {
        for (const left of [x + offset * cell - block / 2, y + offset * cell - block / 2]) {
          expect(Math.abs(left - Math.round(left))).toBeLessThan(1e-6)
        }
      }
      // Never far from the glass's own centre, and the picture spans about the share it should.
      expect(Math.abs(x - centre[0])).toBeLessThanOrEqual(0.5 + 1e-9)
      expect(Math.abs(y - centre[1])).toBeLessThanOrEqual(0.5 + 1e-9)
      expect(Math.abs(cell * grid - ICON_FILL * side)).toBeLessThanOrEqual(grid / 2 + 1e-9)
    }
  })

  it("follows the glass's own centre in flight and moves smoothly to rest", () => {
    const centre = [101.37, 48.81] as const
    const flying = iconGrid(centre, 60, 13, 0)
    expect([flying.x, flying.y]).toEqual([centre[0], centre[1]])
    let last = flying.x
    for (let k = 1; k <= 20; k++) {
      const {x} = iconGrid(centre, 60, 13, k / 20)
      expect(Math.abs(x - last)).toBeLessThanOrEqual(0.5 / 20 + 1e-9)
      last = x
    }
  })
})
