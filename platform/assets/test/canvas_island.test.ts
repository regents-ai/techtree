// R-20261019-failed-start-lets-go: an island whose GPU never started kept every
// listener it had added, including whatever steered the picture, until the page
// left (found by the design lane in Keyfleet, 19 Oct).
// R-20261111-island-sizes-from-layout: an island that started inside a panel still
// growing in (the regents.sh home page's glass) drew at the panel's shrunken size
// and stayed blurred once it had grown, as a transform never reaches a
// ResizeObserver (found by the product tiles lane, 11 Nov).
import {afterEach, beforeEach, expect, it, vi} from "vitest"
import {createCanvasIsland, type IslandRenderer, type LoadRenderer} from "../js/canvas_island"

const drawing: IslandRenderer = {
  resize() {},
  step: () => false,
  present() {},
  settled: async () => {},
  dispose() {},
}

let disconnected = 0
let visibilityListeners = 0

beforeEach(() => {
  disconnected = 0
  visibilityListeners = 0
  vi.stubGlobal("document", {
    hidden: false,
    addEventListener: () => void (visibilityListeners += 1),
    removeEventListener: () => void (visibilityListeners -= 1),
  })
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    disconnect() { disconnected += 1 }
  })
  vi.stubGlobal("IntersectionObserver", class {
    constructor(private seen: (entries: {isIntersecting: boolean}[]) => void) {}
    observe() { this.seen([{isIntersecting: true}]) }
    disconnect() { disconnected += 1 }
  })
})

afterEach(() => vi.unstubAllGlobals())

// An island on screen in a showing tab, its first frame handed out at once. Its
// canvas is laid out at 300 by 200 inside a panel shrunk to 30% on screen. It
// answers how often what steered the picture was let go, and the root's flag.
async function runIsland(
  load: LoadRenderer<IslandRenderer>,
  screen: {devicePixelRatio?: number; maxDevicePixelRatio?: number} = {},
) {
  let released = 0
  const root = {dataset: {} as Record<string, string>, querySelector: () => ({
    clientWidth: 300,
    clientHeight: 200,
    getBoundingClientRect: () => ({width: 90, height: 60}),
  })} as unknown as HTMLElement

  createCanvasIsland(root, {
    requestFrame: callback => { queueMicrotask(() => callback(0)); return 1 },
    cancelFrame() {},
    devicePixelRatio: () => screen.devicePixelRatio ?? 1,
    motionQuery: () => ({matches: false, addEventListener() {}, removeEventListener() {}}),
    supportsWebGpu: () => true,
    loadRenderer: load,
  }, {
    canvasSelector: "canvas",
    readyFlag: "ready",
    browserLoad: load,
    motionSensitive: false,
    continuous: false,
    maxDevicePixelRatio: screen.maxDevicePixelRatio,
    interact: () => () => void (released += 1),
  }).mount()

  for (let turn = 0; turn < 20; turn += 1) await Promise.resolve()
  return {released, ready: root.dataset.ready}
}

it("lets go of everything it watches with, once, when its GPU does not start", async () => {
  const {released, ready} = await runIsland(() => Promise.reject(new Error("no device")))
  expect(ready).toBe("false")
  expect(released).toBe(1)
  expect(disconnected).toBe(2)
  expect(visibilityListeners).toBe(0)
})

it("draws at the canvas's laid-out size while a panel round it is shrunk", async () => {
  let size: readonly [number, number] | undefined
  await runIsland(async (_canvas, measured) => {
    size = measured
    return drawing
  })
  expect(size).toEqual([300, 200])
})

it("keeps hold of them while the picture draws", async () => {
  const {released, ready} = await runIsland(async () => drawing)
  expect(ready).toBe("true")
  expect(released).toBe(0)
  expect(visibilityListeners).toBe(1)
})

// Invariant: a small island may ask for more of a sharp screen than the default
// ceiling; one that does not keeps to it.
it("draws past the default ceiling only when an island asks for it", async () => {
  let size: readonly number[] = []
  await runIsland(async (_, given) => ((size = given), drawing), {devicePixelRatio: 3, maxDevicePixelRatio: 3})
  expect(size).toEqual([900, 600])
})

it("keeps to the default ceiling when an island does not ask for more", async () => {
  let size: readonly number[] = []
  await runIsland(async (_, given) => ((size = given), drawing), {devicePixelRatio: 3})
  expect(size).toEqual([450, 300])
})
