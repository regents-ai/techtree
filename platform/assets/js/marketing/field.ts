/**
 * Draws one of the home page's moving pictures (`scenes.ts`) with WebGPU
 * through vgpu, on the device the page's pictures share (`gpu.ts`). Loaded only
 * once a picture is really going to be shown.
 */
import {prepareShader} from "@vgpu/wgsl/prepare"
import {effect, frame, surface} from "vgpu"

import type {IslandRenderer} from "../canvas_island"
import {device} from "./gpu"
import {shaderFor, uniforms, type Colours, type Scene} from "./scenes"

export type FieldRenderer = IslandRenderer & {
  /** The pointer's place across the picture, each axis 0 to 1, or null once it has left. */
  point(at: readonly [number, number] | null): void
  /** New colours, such as after the theme turned. */
  paint(colours: Colours): void
}

/** How much of the way to the pointer the picture moves each frame. */
const EASE = 0.12

export async function createFieldRenderer(
  canvas: HTMLCanvasElement,
  size: readonly [number, number],
  onDeviceLost: () => void,
  scene: Scene,
  colours: Colours,
  shape: number,
): Promise<FieldRenderer> {
  const shared = await device.join(onDeviceLost)
  const {gpu} = shared
  let stage: ReturnType<typeof surface> | undefined
  let shader: ReturnType<typeof effect> | undefined
  try {
    stage = surface(gpu, canvas, {autoResize: false, alphaMode: "opaque", label: `field-${scene}`})
    stage.resize([size[0], size[1]])
    const output = stage
    let width = size[0]
    let height = size[1]
    let paints = colours
    let disposed = false
    // A picture starts part way through its drift, so no two open on the same frame.
    let started: number | undefined
    let seconds = 40 + Math.random() * 40
    const now = {x: 0.5, y: 0.5, z: 0}
    const target = {x: 0.5, y: 0.5, z: 0}

    const state = () => uniforms({
      width,
      height,
      scale: width / Math.max(1, canvas.clientWidth),
      seconds,
      pointer: [now.x, now.y, now.z],
      colours: paints,
      shape,
    })

    const pass = effect(gpu, prepareShader(shaderFor(scene), `field_${scene}.wgsl`), {
      label: `field-${scene}.pass`,
      set: state(),
    })
    shader = pass
    await pass.compile(output)

    return {
      point(at) {
        if (!at) {
          target.z = 0
          return
        }
        if (now.z < 0.01) Object.assign(now, {x: at[0], y: at[1]})
        Object.assign(target, {x: at[0], y: at[1], z: 1})
      },
      paint(next) {
        paints = next
      },
      resize(nextWidth, nextHeight) {
        width = nextWidth
        height = nextHeight
        output.resize([width, height])
      },
      step() {
        for (const key of ["x", "y", "z"] as const) {
          const gap = target[key] - now[key]
          now[key] = Math.abs(gap) > 0.002 ? now[key] + gap * EASE : target[key]
        }
        started ??= performance.now() - seconds * 1000
        seconds = (performance.now() - started) / 1000
        return true
      },
      present() {
        pass.set(state())
        frame(gpu, current => current.pass(output, pass))
      },
      settled() {
        return gpu.settled()
      },
      dispose() {
        if (disposed) return
        disposed = true
        pass.dispose()
        output.dispose()
        device.leave(shared, onDeviceLost)
      },
    }
  } catch (error) {
    shader?.dispose()
    stage?.dispose()
    device.leave(shared, onDeviceLost)
    throw error
  }
}
