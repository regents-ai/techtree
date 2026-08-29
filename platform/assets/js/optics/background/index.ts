import {effect, frame, init, surface, type Gpu} from "vgpu"

import {backgroundWgsl} from "./shader"

interface BackgroundRenderer {
  aim(x: number, y: number): void
  rest(): void
  resize(width: number, height: number): void
  step(snap: boolean): boolean
  present(): void
  settled(): Promise<void>
  dispose(): void
}

const THEMES = {
  orange: {
    baseColor: [0.9569, 0.9333, 0.8941, 1],
    antiColor: [0.105, 0.31, 0.37, 1],
    intensity: 0.09,
  },
  titanium: {
    baseColor: [0.0627, 0.0627, 0.0627, 1],
    antiColor: [0.92, 0.28, 0.08, 1],
    intensity: 0.1,
  },
} as const

function backgroundPreset(value: string | undefined): number {
  const parsed = Number.parseInt(value || "1", 10)
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 10 ? parsed : 1
}

async function equip(
  gpu: Gpu,
  canvas: HTMLCanvasElement,
  size: readonly [number, number],
) {
  const canvasSurface = surface(gpu, canvas, {
    autoResize: false,
    alphaMode: "opaque",
    label: "site-background",
  })
  canvasSurface.resize(size)
  const shader = effect(gpu, backgroundWgsl, {label: "site-background-field"})
  await shader.compile({colors: [canvasSurface.format]})
  return {canvasSurface, shader}
}

export async function createBackgroundRenderer(
  canvas: HTMLCanvasElement,
  size: readonly [number, number],
  onDeviceLost: () => void,
): Promise<BackgroundRenderer> {
  const gpu = await init()
  let disposed = false
  const {canvasSurface, shader} = await equip(gpu, canvas, size).catch(error => {
    gpu.dispose()
    throw error
  })

  void gpu.gpu.lost.then(() => {
    if (!disposed) onDeviceLost()
  })

  const setParameters = () => {
    const theme = canvas.dataset.backgroundTheme === "titanium" ? "titanium" : "orange"
    const palette = THEMES[theme]
    shader.set({
      params: {
        baseColor: palette.baseColor,
        antiColor: palette.antiColor,
        resolution: canvasSurface.size,
        preset: backgroundPreset(canvas.dataset.backgroundPreset),
        intensity: palette.intensity,
      },
    })
  }

  setParameters()

  return {
    aim(_x, _y) {},
    rest() {},
    resize(width, height) {
      canvasSurface.resize([width, height])
      setParameters()
    },
    step(_snap) {
      return false
    },
    present() {
      setParameters()
      frame(gpu, current => current.pass(canvasSurface, shader))
    },
    async settled() {
      await gpu.gpu.queue.onSubmittedWorkDone()
      await gpu.settled()
    },
    dispose() {
      if (disposed) return
      disposed = true
      canvasSurface.dispose()
      gpu.dispose()
    },
  }
}
