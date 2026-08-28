/**
 * Deterministic scene graph, forked from the Vercel vgpu prism background. See
 * THIRD_PARTY_NOTICES.md.
 *
 * Every frame resolves the crown's inner and outer glass through two full-resolution
 * ping-pong HDR targets, then builds a four-level reduced-resolution bloom pyramid
 * before the sole tone-mapped presentation pass. There is no temporal history or
 * convergence state, so one frame is the final picture for a given camera.
 */

import {draw, effect, frame, sampler, target} from "vgpu"
import type {Draw, Effect, Geometry, Gpu, Surface, Target} from "vgpu"

import {cameraView, rotationMatrix, type CameraView} from "./camera"
import {crownLightGeometry, updateCrownLightGeometry} from "./crown-light"
import {crownGeometry} from "./crown-mesh"
import {
  CROWN_BACK_Z,
  CROWN_FRONT_Z,
  CROWN_GLASS,
  CROWN_HALF_SIZE,
  CROWN_LIGHT,
  CROWN_LIGHT_PLANE_Z,
  CROWN_POSTPROCESS,
  CROWN_VARIANTS,
  type CrownVariant,
  type Vec2,
} from "./crown-types"
import bloomUpsampleWgsl from "./shaders/bloom-upsample"
import bloomWgsl from "./shaders/bloom"
import copyLinearWgsl from "./shaders/copy-linear"
import crownGlassBackWgsl from "./shaders/crown-glass-back"
import crownGlassFrontWgsl from "./shaders/crown-glass-front"
import crownLightWgsl from "./shaders/crown-light"
import presentWgsl from "./shaders/present"

const BLOOM_LEVELS = 4
type BloomTargets = readonly [Target, Target, Target, Target]

export interface PrismScene {
  readonly gpu: Gpu
  outputSize: readonly [number, number]
  sceneTargets?: readonly [Target, Target]
  bloomTargets?: BloomTargets
  readonly copyToBack: Effect
  readonly copyToFront: Effect
  readonly bloomDownsample: readonly [Effect, Effect, Effect, Effect]
  readonly bloomUpsample: readonly [Effect, Effect, Effect]
  readonly present: Effect
  readonly glassBack: Draw
  readonly glassFront: Draw
  readonly light: Draw
  readonly crown: Geometry
  readonly lightSheet: Geometry
  readonly variant: CrownVariant
  readonly environmentRotation: Float32Array
  readonly sceneSampler: ReturnType<typeof sampler>
  orbit: Vec2
  lightAim: Vec2
  aspect: number
  view: CameraView
  readonly label: string
}

export function createScene(
  gpu: Gpu,
  output: readonly [number, number],
  variant: CrownVariant,
  label: string,
): PrismScene {
  const aspect = output[0] / Math.max(1, output[1])
  const bloomEffect = (name: string) => effect(gpu, bloomWgsl, {label: `${label}.bloom-${name}`})
  const bloomUpsampleEffect = (name: string) =>
    effect(gpu, bloomUpsampleWgsl, {label: `${label}.bloom-upsample-${name}`, blend: "additive"})
  const crown = crownGeometry(gpu, `${label}.crown`)
  const lightSheet = crownLightGeometry(gpu, variant, [0, 0], aspect, `${label}.light-sheet`)

  return {
    gpu,
    outputSize: output,
    copyToBack: effect(gpu, copyLinearWgsl, {label: `${label}.copy-to-back`}),
    copyToFront: effect(gpu, copyLinearWgsl, {label: `${label}.copy-to-front`}),
    bloomDownsample: [
      bloomEffect("half"),
      bloomEffect("quarter"),
      bloomEffect("eighth"),
      bloomEffect("sixteenth"),
    ],
    bloomUpsample: [
      bloomUpsampleEffect("eighth"),
      bloomUpsampleEffect("quarter"),
      bloomUpsampleEffect("half"),
    ],
    present: effect(gpu, presentWgsl, {label: `${label}.present`}),
    light: draw(gpu, {
      shader: crownLightWgsl,
      geometry: lightSheet,
      blend: "additive",
      cull: "none",
      depth: false,
      label: `${label}.light`,
    }),
    glassBack: draw(gpu, {
      shader: crownGlassBackWgsl,
      geometry: crown,
      cull: "front",
      depth: false,
      blend: "premultiplied",
      label: `${label}.glass-back`,
    }),
    glassFront: draw(gpu, {
      shader: crownGlassFrontWgsl,
      geometry: crown,
      cull: "back",
      depth: false,
      label: `${label}.glass-front`,
    }),
    crown,
    lightSheet,
    variant,
    environmentRotation: rotationMatrix(CROWN_VARIANTS[variant].environmentRotation),
    sceneSampler: sampler(gpu, {
      minFilter: "linear",
      magFilter: "linear",
      addressModeU: "clamp-to-edge",
      addressModeV: "clamp-to-edge",
    }),
    orbit: [0, 0],
    lightAim: [0, 0],
    aspect,
    view: cameraView(aspect),
    label,
  }
}

/** Tilts the camera within the reviewed bounded orbit. */
export function setOrbit(scene: PrismScene, x: number, y: number): void {
  scene.orbit = [Math.min(1, Math.max(-1, x)), Math.min(1, Math.max(-1, y))]
  scene.view = cameraView(scene.aspect, scene.orbit[0], scene.orbit[1])
}

export function setLightAim(scene: PrismScene, x: number, y: number): void {
  scene.lightAim = [Math.min(1, Math.max(-1, x)), Math.min(1, Math.max(-1, y))]
  updateCrownLightGeometry(scene.lightSheet, scene.variant, scene.lightAim, scene.aspect)
}

export function resizeScene(scene: PrismScene, output: readonly [number, number]): void {
  scene.outputSize = output
  scene.aspect = output[0] / Math.max(1, output[1])
  scene.sceneTargets?.[0].resize(output)
  scene.sceneTargets?.[1].resize(output)
  scene.bloomTargets?.forEach((bloomTarget, level) => bloomTarget.resize(bloomLevelSize(output, level)))
  scene.view = cameraView(scene.aspect, scene.orbit[0], scene.orbit[1])
  updateCrownLightGeometry(scene.lightSheet, scene.variant, scene.lightAim, scene.aspect)
}

function glassUniforms(scene: PrismScene): Record<string, unknown> {
  const material = CROWN_VARIANTS[scene.variant]
  return {
    viewProjection: scene.view.viewProjection,
    environmentRotation: scene.environmentRotation,
    cameraPosition: scene.view.position,
    absorption: material.absorption,
    cellHalfSize: [CROWN_HALF_SIZE, CROWN_HALF_SIZE],
    resolution: scene.outputSize,
    frontZ: CROWN_FRONT_Z,
    backZ: CROWN_BACK_Z,
    wallZ: 0,
    ior: CROWN_GLASS.ior,
    reflectionStrength: material.reflectionStrength,
    frostRadius: CROWN_GLASS.frostRadius,
    dispersion: material.glassDispersion,
    iridescenceStrength: CROWN_GLASS.iridescenceStrength,
    iridescenceFrequency: CROWN_GLASS.iridescenceFrequency,
    environmentExposure: material.environmentExposure,
  }
}

export async function prepareScene(scene: PrismScene, output: Surface): Promise<void> {
  resizeScene(scene, output.size)
  const hdrTarget = (name: string, size: readonly [number, number]): Target =>
    target(scene.gpu, {size, format: "rgba16float", label: `${scene.label}.${name}`})
  scene.sceneTargets ??= [hdrTarget("scene-a", output.size), hdrTarget("scene-b", output.size)]
  scene.bloomTargets ??= (Array.from({length: BLOOM_LEVELS}, (_, level) =>
    hdrTarget(`bloom-${level}`, bloomLevelSize(output.size, level)),
  ) as unknown as BloomTargets)
  bind(scene)
  await Promise.all([
    scene.light.compile(scene.sceneTargets[0]),
    scene.copyToBack.compile(scene.sceneTargets[1]),
    scene.glassBack.compile(scene.sceneTargets[1]),
    scene.copyToFront.compile(scene.sceneTargets[0]),
    scene.glassFront.compile(scene.sceneTargets[0]),
    ...scene.bloomDownsample.map((bloom, level) => bloom.compile(scene.bloomTargets![level]!)),
    ...scene.bloomUpsample.map((bloom, index) => bloom.compile(scene.bloomTargets![2 - index]!)),
    scene.present.compile({colors: [output.format]}),
  ])
}

export function presentScene(scene: PrismScene, output: Surface): void {
  const [readTarget, writeTarget] = scene.sceneTargets!
  const bloomTargets = scene.bloomTargets!
  const background = [...CROWN_VARIANTS[scene.variant].backgroundColor] as [number, number, number, number]
  bind(scene)
  frame(scene.gpu, current => {
    current.pass({target: readTarget, clear: background}, pass => {
      pass.draw(scene.light)
    })
    current.pass({target: writeTarget, clear: background}, pass => {
      pass.draw(scene.copyToBack)
      pass.draw(scene.glassBack)
    })
    current.pass({target: readTarget, clear: background}, pass => {
      pass.draw(scene.copyToFront)
      pass.draw(scene.glassFront)
    })
    bloomTargets.forEach((bloomTarget, level) => {
      current.pass({target: bloomTarget, clear: [0, 0, 0, 1]}, pass =>
        pass.draw(scene.bloomDownsample[level]!),
      )
    })
    scene.bloomUpsample.forEach((bloom, index) => {
      current.pass({target: bloomTargets[2 - index]!, clear: false}, pass => pass.draw(bloom))
    })
    current.pass({target: output}, pass => pass.draw(scene.present))
  })
}

function bind(scene: PrismScene): void {
  const [readTarget, writeTarget] = scene.sceneTargets!
  const bloomTargets = scene.bloomTargets!
  const material = CROWN_VARIANTS[scene.variant]
  scene.light.set({
    params: {
      viewProjection: scene.view.viewProjection,
      lightPlaneZ: CROWN_LIGHT_PLANE_Z,
      edgeFalloff: CROWN_LIGHT.edgeFalloff,
      rainbowFalloffRate: CROWN_LIGHT.rainbowFalloffRate,
      rainbowFalloffPower: CROWN_LIGHT.rainbowFalloffPower,
      opacity: CROWN_LIGHT.opacity,
    },
  })
  scene.copyToBack.set({sceneTexture: readTarget})
  scene.glassBack.set({
    params: glassUniforms(scene),
    sceneTexture: readTarget,
    sceneSampler: scene.sceneSampler,
  })
  scene.copyToFront.set({sceneTexture: writeTarget})
  scene.glassFront.set({
    params: glassUniforms(scene),
    sceneTexture: writeTarget,
    sceneSampler: scene.sceneSampler,
  })
  scene.bloomDownsample.forEach((bloom, level) => {
    const source = level === 0 ? readTarget : bloomTargets[level - 1]!
    bloom.set({
      sourceTexture: source,
      sourceSampler: scene.sceneSampler,
      params: {
        sourceTexelSize: [1 / source.size[0], 1 / source.size[1]],
        threshold: material.bloomThreshold,
        extractHighlights: level === 0 ? 1 : 0,
      },
    })
  })
  scene.bloomUpsample.forEach((bloom, index) => {
    const source = bloomTargets[3 - index]!
    bloom.set({
      sourceTexture: source,
      sourceSampler: scene.sceneSampler,
      params: {
        sourceTexelSize: [1 / source.size[0], 1 / source.size[1]],
        radius: CROWN_POSTPROCESS.bloomRadius,
        scatter: 0.65,
      },
    })
  })
  scene.present.set({
    sceneTexture: readTarget,
    bloomTexture: bloomTargets[0],
    bloomSampler: scene.sceneSampler,
    params: {bloomStrength: material.bloomStrength},
  })
}

function bloomLevelSize(
  size: readonly [number, number],
  level: number,
): readonly [number, number] {
  const divisor = 2 ** (level + 1)
  return [Math.max(1, Math.ceil(size[0] / divisor)), Math.max(1, Math.ceil(size[1] / divisor))]
}

const destroyTarget = (value: Target | undefined): void =>
  (value as (Target & {destroy?: () => void}) | undefined)?.destroy?.()

export function destroyScene(scene: PrismScene): void {
  scene.sceneTargets?.forEach(destroyTarget)
  scene.sceneTargets = undefined
  scene.bloomTargets?.forEach(destroyTarget)
  scene.bloomTargets = undefined
  scene.crown.destroy()
  scene.lightSheet.destroy()
}
