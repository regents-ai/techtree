// The home page's motion kit (js/marketing): where each Result card sits as the
// carousel turns, how a figure is read and written again as it counts, and what
// every moving picture sends its shader.
import {prepareShader} from "@vgpu/wgsl/prepare"
import {describe, expect, it} from "vitest"
import {slotOf} from "../js/marketing/carousel"
import {SCENES, SHAPES, linear, shaderFor, uniforms} from "../js/marketing/scenes"
import {reading, written} from "../js/marketing/tally"

describe("the carousel's places", () => {
  it("puts exactly one card in the middle and its neighbours either side, for any count and turn", () => {
    for (const count of [2, 3, 4, 7]) {
      for (let current = 0; current < count; current += 1) {
        const slots = Array.from({length: count}, (_, index) => slotOf(index, current, count))
        expect(slots[current]).toBe("centre")
        expect(slots.filter(slot => slot === "centre")).toHaveLength(1)
        expect(slots[(current + 1) % count]).toBe("next")
        if (count > 2) expect(slots[(current - 1 + count) % count]).toBe("prev")
        expect(slots.filter(slot => slot === "next")).toHaveLength(1)
        expect(slots.filter(slot => slot === "prev")).toHaveLength(count > 2 ? 1 : 0)
      }
    }
  })
})

describe("a figure counting up", () => {
  it("reads the number, its decimals and its grouping from the text", () => {
    expect(reading("0.62")).toMatchObject({value: 0.62, decimals: 2, grouped: false})
    expect(reading("1,204 runs")).toMatchObject({value: 1204, decimals: 0, grouped: true})
    expect(reading("no figure")).toBeUndefined()
  })

  it("writes each step the way the figure was written, and ends on the very text it began with", () => {
    expect(written("0.62", 0.3)).toBe("0.30")
    expect(written("1,204 runs", 980.4)).toBe("980 runs")
    expect(written("12 of 14", 7.6)).toBe("8 of 14")
    for (const text of ["0.62", "1,204 runs", "12 of 14", "3"]) {
      expect(written(text, reading(text)!.value)).toBe(text)
    }
  })
})

describe("the moving pictures", () => {
  const frame = {
    width: 640,
    height: 360,
    scale: 1.5,
    seconds: 12,
    pointer: [0.25, 0.75, 1] as const,
    colours: {ground: "#0d1611", ink: "#c8f25c", glow: "#2fa866"},
    shape: [1, 3, 0.5] as const,
  }

  it("sends every uniform as four numbers, in the struct's order", () => {
    const {params} = uniforms(frame)
    expect(Object.keys(params)).toEqual(["size", "pointer", "ground", "ink", "glow", "shape"])
    for (const member of Object.values(params)) expect(member).toHaveLength(4)
    expect(params.size).toEqual([640, 360, 1.5, 12])
    expect(params.shape.slice(0, 3)).toEqual([1, 3, 0.5])
  })

  it("mixes colours in linear light", () => {
    expect(linear("#ffffff")).toEqual([1, 1, 1, 1])
    expect(linear("#000000")).toEqual([0, 0, 0, 1])
    expect(linear("#808080")[0]).toBeCloseTo(0.2158605, 6)
  })

  it("prepares each scene's shader with its one uniform and a fragment entry", () => {
    for (const scene of SCENES) {
      const shader = prepareShader(shaderFor(scene), `field_${scene}.wgsl`)
      const {bindings, entryPoints} = shader.reflection
      expect(entryPoints.map(entry => [entry.name, entry.stage])).toEqual([["fs_main", "fragment"]])
      expect(bindings.map(binding => [binding.group, binding.binding, binding.name, binding.addressSpace]))
        .toEqual([[0, 0, "params", "uniform"]])
      expect(entryPoints[0].bindings).toEqual([{group: 0, binding: 0}])
    }
  })

  it("has a shape in the dot screen for every shape it names", () => {
    const cases = shaderFor("screen").match(/case \d+:/g) ?? []
    // Every named shape but the last has its own case; the last is the default.
    expect(cases).toHaveLength(SHAPES.length - 1)
  })
})
