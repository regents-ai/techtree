// Invariant: the blocks reach the shader sorted top to bottom, each exactly
// once, so a pixel that looks only at the blocks in its own band still finds
// every block that can cover it; each turn arrives as its cosine and sine, and
// a block is whole at rest and smaller in flight.
import {describe, expect, it} from "vitest"
import {FLIGHT_SHRINK, packBlocks, PIXEL_SLOTS} from "../js/theme_switch/shader"

// x, y, turn and share of day for five blocks, in no order down the picture.
const BLOCKS = [
  [2, 3, 0, 0],
  [-1, -4, Math.PI / 2, 1],
  [0, 0.5, Math.PI / 4, 0.5],
  [3, -4, Math.PI, 0.25],
  [-2, 1, 0, 1],
]
const STRIDE = 4
const HALF = 0.4

function pack() {
  const place = new Float32Array(PIXEL_SLOTS * 4).fill(9)
  const look = new Float32Array(PIXEL_SLOTS * 4).fill(9)
  packBlocks(new Float32Array(BLOCKS.flat()), STRIDE, BLOCKS.length, HALF, place, look)
  const slot = (data: Float32Array, i: number) => [...data.subarray(i * 4, i * 4 + 4)]
  return {place, look, slot}
}

describe("the blocks as the shader reads them", () => {
  it("go top to bottom, each block once", () => {
    const {place, slot} = pack()
    const ys = BLOCKS.map((_, i) => slot(place, i)[1])
    expect(ys).toEqual([...ys].sort((a, b) => a - b))
    const sent = BLOCKS.map((_, i) => slot(place, i).slice(0, 2).join()).sort()
    expect(sent).toEqual(BLOCKS.map(([x, y]) => `${x},${y}`).sort())
  })

  it("carry each turn as its cosine and sine, and each block's look beside it", () => {
    const {place, look, slot} = pack()
    BLOCKS.forEach((_, i) => {
      const [x, y, cos, sin] = slot(place, i)
      const [, day] = slot(look, i)
      const block = BLOCKS.find(([bx, by]) => bx === x && by === y)!
      expect(cos).toBeCloseTo(Math.cos(block[2]), 6)
      expect(sin).toBeCloseTo(Math.sin(block[2]), 6)
      expect(day).toBeCloseTo(block[3], 6)
    })
  })

  it("keeps a block whole at rest and makes it smaller in flight", () => {
    const {look, slot} = pack()
    BLOCKS.forEach((_, i) => {
      const [half, day] = slot(look, i)
      if (day === 0 || day === 1) expect(half).toBeCloseTo(HALF, 6)
      else expect(half).toBeLessThan(HALF)
      if (day === 0.5) expect(half).toBeCloseTo(HALF * (1 - FLIGHT_SHRINK), 6)
    })
  })

  it("leaves the slots past the last block empty", () => {
    const {place, look} = pack()
    expect([...place.subarray(BLOCKS.length * 4)].every(v => v === 0)).toBe(true)
    expect([...look.subarray(BLOCKS.length * 4)].every(v => v === 0)).toBe(true)
  })
})
