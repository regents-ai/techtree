/**
 * Draws one value card's panel with WebGPU through vgpu. Loaded only once a
 * card is really going to be shown. Every panel on the page draws on one
 * device (`shared_device.ts`); when the browser takes it away, each panel's
 * island hears of it and asks again.
 */
import {prepareShader} from "@vgpu/wgsl/prepare"
import {effect, frame, init, surface} from "vgpu"

import type {IslandRenderer} from "../canvas_island"
import {panels} from "./index"
import {shaderFor, uniforms} from "./panel"
import {shareDevice} from "./shared_device"

export type ValueCardRenderer = IslandRenderer & {
  /** The pointer's place across the panel, each axis 0 to 1, or null once it has left the card. */
  point(at: readonly [number, number] | null): void
}

/** How much of the way to the pointer the pattern moves each frame. */
const EASE = 0.14

const device = shareDevice(() => init())

export async function createValueCardRenderer(
  canvas: HTMLCanvasElement,
  size: readonly [number, number],
  onDeviceLost: () => void,
  name: string,
): Promise<ValueCardRenderer> {
  const panel = panels[name]
  if (!panel) throw new Error(`No value card panel is called ${name}.`)
  const shared = await device.join(onDeviceLost)
  const {gpu} = shared
  let stage: ReturnType<typeof surface> | undefined
  let shader: ReturnType<typeof effect> | undefined
  try {
    stage = surface(gpu, canvas, {autoResize: false, alphaMode: "opaque", label: `value-card-${name}`})
    stage.resize([size[0], size[1]])
    const output = stage
    let width = size[0]
    let height = size[1]
    let disposed = false
    // The moving picture carries on from the still frame's moment, from its first step.
    let started: number | undefined
    let seconds = panel.stillAt
    const now = {x: 0.5, y: 0.5, z: 0}
    const target = {x: 0.5, y: 0.5, z: 0}
    const pass = effect(gpu, prepareShader(shaderFor(panel), `value_card_${name}.wgsl`), {
      label: `value-card-${name}.pass`,
      set: uniforms(panel, width, height, seconds),
    })
    shader = pass
    await pass.compile(output)

    return {
      point(at) {
        if (!at) {
          target.z = 0
          return
        }
        // A pointer arriving starts where it is; only one already here is eased towards.
        if (now.z < 0.01) Object.assign(now, {x: at[0], y: at[1]})
        Object.assign(target, {x: at[0], y: at[1], z: 1})
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
        pass.set(uniforms(panel, width, height, seconds, [now.x, now.y, now.z]))
        frame(gpu, current => current.pass(output, pass))
      },
      settled() {
        return gpu.settled()
      },
      dispose() {
        if (disposed) return
        disposed = true
        // The device outlives this panel, so the panel gives back what it made on it.
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
