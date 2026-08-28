import {geometry, type Geometry, type Gpu} from "vgpu"

import {
  CROWN_CELL_CENTERS,
  CROWN_GLASS,
  CROWN_HALF_SIZE,
  CROWN_PITCH,
  CROWN_VARIANTS,
  type CrownVariant,
  type Vec2,
  type Vec3,
} from "./crown-types"

export const CROWN_LIGHT_VERTEX_FLOATS = 8
export const CROWN_LIGHT_VERTEX_STRIDE =
  CROWN_LIGHT_VERTEX_FLOATS * Float32Array.BYTES_PER_ELEMENT
export const CROWN_LIGHT_VERTEX_CAPACITY = 12_288

const EPSILON = 1e-4
const ROWS = [CROWN_PITCH, 0, -CROWN_PITCH] as const

interface LightVertex {
  readonly position: Vec2
  readonly color: Vec3
  readonly intensity: number
  readonly profile: number
  readonly travel: number
}

interface BoxHit {
  readonly cell: number
  readonly near: number
  readonly far: number
  readonly nearNormal: Vec2
  readonly farNormal: Vec2
}

interface TraceSegment {
  readonly start: Vec2
  readonly end: Vec2
  readonly inside: boolean
  readonly afterGlass: boolean
  readonly intensity: number
  readonly travel: number
}

interface CrownTrace {
  readonly segments: readonly TraceSegment[]
  readonly echoes: readonly TraceSegment[]
  readonly cells: readonly number[]
}

export interface CrownLightMeshData {
  readonly vertices: Float32Array<ArrayBuffer>
  readonly vertexCount: number
  readonly activeVertexCount: number
  readonly segmentCount: number
  readonly hitCellCount: number
}

type VariantConfig = (typeof CROWN_VARIANTS)[CrownVariant]

export function crownLightMeshData(
  variant: CrownVariant = 1,
  aim: Vec2 = [0, 0],
  aspect = 16 / 9,
): CrownLightMeshData {
  const config = CROWN_VARIANTS[variant]
  const wall: Vec2 = [Math.max(2.65, aspect * 1.82), 1.55]
  const output: number[] = []
  const hitCells = new Set<number>()

  for (const sourceSide of config.sourceSides) {
    const sourceWeight = 1 / config.sourceSides.length
    for (let rowIndex = 0; rowIndex < ROWS.length; rowIndex++) {
      const row = ROWS[rowIndex]!
      const rowWeight = (rowIndex === 1 ? 1 : 0.64) * sourceWeight
      const direction = beamDirection(row, aim, config, sourceSide)
      const target: Vec2 = [
        sourceSide * 2 * CROWN_PITCH,
        row + config.sourceYOffset - aim[1] * config.verticalTravel,
      ]
      const source = rayToBoundary(target, scale(direction, -1), wall)
      const middleTrace = traceCrown(source, direction, iorAt(550, config), config, wall)
      middleTrace.cells.forEach(cell => hitCells.add(cell))

      const firstEntry = middleTrace.segments.find(segment => !segment.afterGlass)?.end
      if (firstEntry) {
        pushBeam(
          output,
          source,
          firstEntry,
          config.beamHalfWidth,
          config.inputColor,
          config.inputIntensity * rowWeight,
        )
      }

      for (const segment of middleTrace.segments) {
        if (!segment.inside) continue
        pushBeam(
          output,
          segment.start,
          segment.end,
          config.beamHalfWidth * 0.72,
          config.internalColor,
          config.internalIntensity * rowWeight * segment.intensity,
          segment.travel,
        )
      }

      for (let sample = 0; sample < config.spectralSamples; sample++) {
        const position = sample / (config.spectralSamples - 1)
        const wavelength = 400 + position * 300
        const trace = traceCrown(
          source,
          direction,
          iorAt(wavelength, config),
          config,
          wall,
        )
        trace.cells.forEach(cell => hitCells.add(cell))
        const color = config.spectralColor ?? wavelengthToBeamRgb(wavelength)

        for (const segment of trace.segments) {
          if (!segment.afterGlass) continue
          pushBeam(
            output,
            segment.start,
            segment.end,
            config.spectralHalfWidth,
            color,
            config.spectralIntensity * rowWeight * segment.intensity,
            segment.travel,
          )
        }

        if (config.echoIntensity > 0 && sample % 4 === 0) {
          for (const segment of trace.echoes) {
            pushBeam(
              output,
              segment.start,
              segment.end,
              config.spectralHalfWidth * 0.72,
              color,
              config.echoIntensity * rowWeight * segment.intensity,
              segment.travel,
            )
          }
        }
      }
    }
  }

  const activeVertexCount = output.length / CROWN_LIGHT_VERTEX_FLOATS
  if (!output.every(Number.isFinite) || activeVertexCount > CROWN_LIGHT_VERTEX_CAPACITY) {
    throw new Error("Crown light geometry exceeded its finite vertex budget.")
  }
  const vertices = new Float32Array(CROWN_LIGHT_VERTEX_CAPACITY * CROWN_LIGHT_VERTEX_FLOATS)
  vertices.set(output)
  return {
    vertices,
    vertexCount: CROWN_LIGHT_VERTEX_CAPACITY,
    activeVertexCount,
    segmentCount: activeVertexCount / 6,
    hitCellCount: hitCells.size,
  }
}

export function crownLightGeometry(
  gpu: Gpu,
  variant: CrownVariant,
  aim: Vec2,
  aspect: number,
  label = "regents-crown-light",
): Geometry {
  const {vertices, vertexCount} = crownLightMeshData(variant, aim, aspect)
  return geometry(gpu, {
    label,
    vertexCount,
    buffers: [
      {
        data: vertices,
        stride: CROWN_LIGHT_VERTEX_STRIDE,
        attributes: {
          position: {format: "float32x2", offset: 0, location: 0},
          color: {format: "float32x3", offset: 8, location: 1},
          intensity: {format: "float32", offset: 20, location: 2},
          profile: {format: "float32", offset: 24, location: 3},
          travel: {format: "float32", offset: 28, location: 4},
        },
      },
    ],
  })
}

export function updateCrownLightGeometry(
  light: Geometry,
  variant: CrownVariant,
  aim: Vec2,
  aspect: number,
): CrownLightMeshData {
  const mesh = crownLightMeshData(variant, aim, aspect)
  light.write(mesh.vertices)
  return mesh
}

function beamDirection(
  row: number,
  aim: Vec2,
  config: VariantConfig,
  sourceSide: 1 | -1,
): Vec2 {
  const rowPosition = row / CROWN_PITCH
  const angle = config.angleBase
    + aim[0] * config.angleRange
    - rowPosition * config.rowConvergence
  return normalize([-sourceSide * Math.cos(angle), Math.sin(angle)])
}

function traceCrown(
  source: Vec2,
  initialDirection: Vec2,
  ior: number,
  config: VariantConfig,
  wall: Vec2,
): CrownTrace {
  const segments: TraceSegment[] = []
  const echoes: TraceSegment[] = []
  const cells: number[] = []
  const visited = new Set<number>()
  let origin = source
  let direction = initialDirection
  let intensity = 1
  let travel = 0

  for (let interaction = 0; interaction < CROWN_CELL_CENTERS.length; interaction++) {
    const hit = nextCell(origin, direction, visited)
    if (!hit) break
    const entry = add(origin, scale(direction, hit.near))
    const airDistance = distance(origin, entry)
    segments.push({
      start: origin,
      end: entry,
      inside: false,
      afterGlass: cells.length > 0,
      intensity,
      travel: Math.min(0.18, travel * 0.04),
    })
    travel += airDistance

    if (config.echoIntensity > 0) {
      const reflected = normalize(reflect(direction, hit.nearNormal))
      echoes.push({
        start: entry,
        end: rayToBoundary(add(entry, scale(reflected, EPSILON)), reflected, wall),
        inside: false,
        afterGlass: true,
        intensity,
        travel: Math.min(0.18, travel * 0.04),
      })
    }

    intensity *= fresnelTransmittance(direction, hit.nearNormal, 1, ior)
    const insideDirection = refract(direction, hit.nearNormal, 1 / ior)
    if (!insideDirection) break
    const insideOrigin = add(entry, scale(insideDirection, EPSILON))
    const insideHit = intersectCell(insideOrigin, insideDirection, hit.cell)
    if (!insideHit) break
    const exit = add(insideOrigin, scale(insideDirection, insideHit.far))
    const insideDistance = distance(entry, exit)
    segments.push({
      start: entry,
      end: exit,
      inside: true,
      afterGlass: true,
      intensity,
      travel: Math.min(0.18, travel * 0.04),
    })
    travel += insideDistance
    cells.push(hit.cell)
    visited.add(hit.cell)

    const inwardNormal = rotate(
      scale(insideHit.farNormal, -1),
      cellWedge(hit.cell, config.wedgeStrength),
    )
    const escaped = refract(insideDirection, inwardNormal, ior)
    if (!escaped) break
    intensity *= fresnelTransmittance(insideDirection, inwardNormal, ior, 1)
    direction = normalize(escaped)
    origin = add(exit, scale(direction, EPSILON))
  }

  if (cells.length > 0) {
    const end = rayToBoundary(origin, direction, wall)
    segments.push({
      start: origin,
      end,
      inside: false,
      afterGlass: true,
      intensity,
      travel: Math.min(0.18, travel * 0.04),
    })
  }

  return {segments, echoes, cells}
}

function nextCell(origin: Vec2, direction: Vec2, visited: ReadonlySet<number>): BoxHit | undefined {
  let nearest: BoxHit | undefined
  for (let cell = 0; cell < CROWN_CELL_CENTERS.length; cell++) {
    if (visited.has(cell)) continue
    const hit = intersectCell(origin, direction, cell)
    if (!hit || hit.near <= EPSILON || (nearest && nearest.near <= hit.near)) continue
    nearest = hit
  }
  return nearest
}

function intersectCell(origin: Vec2, direction: Vec2, cell: number): BoxHit | undefined {
  const center = CROWN_CELL_CENTERS[cell]!
  let near = Number.NEGATIVE_INFINITY
  let far = Number.POSITIVE_INFINITY
  let nearNormal: Vec2 = [0, 0]
  let farNormal: Vec2 = [0, 0]

  for (let axis = 0; axis < 2; axis++) {
    const component = direction[axis]!
    const low = center[axis]! - CROWN_HALF_SIZE
    const high = center[axis]! + CROWN_HALF_SIZE
    if (Math.abs(component) < EPSILON) {
      if (origin[axis]! < low || origin[axis]! > high) return undefined
      continue
    }

    let first = (low - origin[axis]!) / component
    let second = (high - origin[axis]!) / component
    let firstNormal: Vec2 = axis === 0 ? [-1, 0] : [0, -1]
    let secondNormal: Vec2 = axis === 0 ? [1, 0] : [0, 1]
    if (first > second) {
      ;[first, second] = [second, first]
      ;[firstNormal, secondNormal] = [secondNormal, firstNormal]
    }
    if (first > near) {
      near = first
      nearNormal = firstNormal
    }
    if (second < far) {
      far = second
      farNormal = secondNormal
    }
    if (near > far) return undefined
  }

  if (far <= EPSILON) return undefined
  return {cell, near, far, nearNormal, farNormal}
}

function cellWedge(cell: number, strength: number): number {
  const alternating = cell % 2 === 0 ? 1 : -1
  return alternating * strength * 0.45
}

function iorAt(wavelength: number, config: VariantConfig): number {
  const micrometres = wavelength * 1e-3
  return CROWN_GLASS.ior + config.dispersionStrength / (micrometres * micrometres)
}

function refract(incident: Vec2, normal: Vec2, eta: number): Vec2 | undefined {
  const cosine = -dot(incident, normal)
  const transmittedSquared = eta * eta * (1 - cosine * cosine)
  if (transmittedSquared > 1) return undefined
  return normalize(add(
    scale(incident, eta),
    scale(normal, eta * cosine - Math.sqrt(1 - transmittedSquared)),
  ))
}

function reflect(incident: Vec2, normal: Vec2): Vec2 {
  return sub(incident, scale(normal, 2 * dot(incident, normal)))
}

function fresnelTransmittance(
  incident: Vec2,
  normal: Vec2,
  incidentIor: number,
  transmittedIor: number,
): number {
  const cosineIncident = Math.min(1, Math.max(0, -dot(incident, normal)))
  const eta = incidentIor / transmittedIor
  const transmittedSquared = eta * eta * (1 - cosineIncident * cosineIncident)
  if (transmittedSquared >= 1) return 0
  const cosineTransmitted = Math.sqrt(1 - transmittedSquared)
  const sTop = incidentIor * cosineIncident - transmittedIor * cosineTransmitted
  const sBottom = incidentIor * cosineIncident + transmittedIor * cosineTransmitted
  const pTop = incidentIor * cosineTransmitted - transmittedIor * cosineIncident
  const pBottom = incidentIor * cosineTransmitted + transmittedIor * cosineIncident
  return 1 - 0.5 * ((sTop / sBottom) ** 2 + (pTop / pBottom) ** 2)
}

function rayToBoundary(origin: Vec2, direction: Vec2, halfExtent: Vec2): Vec2 {
  let nearest = Number.POSITIVE_INFINITY
  for (let axis = 0; axis < 2; axis++) {
    const component = direction[axis]!
    if (Math.abs(component) < EPSILON) continue
    for (const side of [-halfExtent[axis]!, halfExtent[axis]!] as const) {
      const candidate = (side - origin[axis]!) / component
      if (candidate <= EPSILON || candidate >= nearest) continue
      const other = 1 - axis
      const otherPosition = origin[other]! + direction[other]! * candidate
      if (Math.abs(otherPosition) <= halfExtent[other]! + EPSILON) nearest = candidate
    }
  }
  return Number.isFinite(nearest) ? add(origin, scale(direction, nearest)) : origin
}

function pushBeam(
  output: number[],
  start: Vec2,
  end: Vec2,
  halfWidth: number,
  color: Vec3,
  intensity: number,
  travel = 0,
): void {
  const direction = sub(end, start)
  const length = Math.hypot(direction[0], direction[1])
  if (length <= EPSILON || intensity <= 0) return
  const normal: Vec2 = [(-direction[1] / length) * halfWidth, (direction[0] / length) * halfWidth]
  pushQuad(
    output,
    {position: sub(start, normal), color, intensity, profile: -1, travel: 0},
    {position: add(start, normal), color, intensity, profile: 1, travel: 0},
    {position: sub(end, normal), color, intensity, profile: -1, travel},
    {position: add(end, normal), color, intensity, profile: 1, travel},
  )
}

function pushQuad(
  output: number[],
  lowerStart: LightVertex,
  upperStart: LightVertex,
  lowerEnd: LightVertex,
  upperEnd: LightVertex,
): void {
  for (const vertex of [lowerStart, upperStart, upperEnd, lowerStart, upperEnd, lowerEnd]) {
    output.push(
      vertex.position[0],
      vertex.position[1],
      vertex.color[0],
      vertex.color[1],
      vertex.color[2],
      vertex.intensity,
      vertex.profile,
      vertex.travel,
    )
  }
}

const add = (a: Vec2, b: Vec2): Vec2 => [a[0] + b[0], a[1] + b[1]]
const sub = (a: Vec2, b: Vec2): Vec2 => [a[0] - b[0], a[1] - b[1]]
const scale = (value: Vec2, amount: number): Vec2 => [value[0] * amount, value[1] * amount]
const dot = (a: Vec2, b: Vec2): number => a[0] * b[0] + a[1] * b[1]
const distance = (a: Vec2, b: Vec2): number => Math.hypot(a[0] - b[0], a[1] - b[1])
const normalize = (value: Vec2): Vec2 => {
  const length = Math.hypot(value[0], value[1]) || 1
  return [value[0] / length, value[1] / length]
}
const rotate = (value: Vec2, angle: number): Vec2 => {
  const cosine = Math.cos(angle)
  const sine = Math.sin(angle)
  return [value[0] * cosine - value[1] * sine, value[0] * sine + value[1] * cosine]
}

function cieX(wavelength: number): number {
  const t1 = (wavelength - 442) * (wavelength < 442 ? 0.0624 : 0.0374)
  const t2 = (wavelength - 599.8) * (wavelength < 599.8 ? 0.0264 : 0.0323)
  const t3 = (wavelength - 501.1) * (wavelength < 501.1 ? 0.049 : 0.0382)
  return 0.362 * Math.exp(-0.5 * t1 * t1)
    + 1.056 * Math.exp(-0.5 * t2 * t2)
    - 0.065 * Math.exp(-0.5 * t3 * t3)
}

function cieY(wavelength: number): number {
  const t1 = (wavelength - 568.8) * (wavelength < 568.8 ? 0.0213 : 0.0247)
  const t2 = (wavelength - 530.9) * (wavelength < 530.9 ? 0.0613 : 0.0322)
  return 0.821 * Math.exp(-0.5 * t1 * t1) + 0.286 * Math.exp(-0.5 * t2 * t2)
}

function cieZ(wavelength: number): number {
  const t1 = (wavelength - 437) * (wavelength < 437 ? 0.0845 : 0.0278)
  const t2 = (wavelength - 459) * (wavelength < 459 ? 0.0385 : 0.0725)
  return 1.217 * Math.exp(-0.5 * t1 * t1) + 0.681 * Math.exp(-0.5 * t2 * t2)
}

const D65_SPECTRAL_POWER = [
  82.7549, 91.486, 93.4318, 86.6823, 104.865, 117.008, 117.812, 114.861,
  115.923, 108.811, 109.354, 107.802, 104.79, 107.689, 104.405, 104.046,
  100, 96.3342, 95.788, 88.6856, 90.0062, 89.5991, 87.6987, 83.2886,
  83.6992, 80.0268, 80.2146, 82.2778, 78.2842, 69.7213, 71.6091,
] as const
const D65_PHOTOPIC_PEAK = 1.0347
const SPECTRAL_EXPOSURE = 4.5
const SPECTRAL_WHITE_BALANCE: Vec3 = [1.1868, 1, 2.2495]

function d65SpectralPower(wavelength: number): number {
  const coordinate = Math.min(D65_SPECTRAL_POWER.length - 1, Math.max(0, (wavelength - 400) / 10))
  const lower = Math.min(D65_SPECTRAL_POWER.length - 2, Math.floor(coordinate))
  const fraction = coordinate - lower
  return ((D65_SPECTRAL_POWER[lower]! * (1 - fraction))
    + D65_SPECTRAL_POWER[lower + 1]! * fraction) / 100
}

export function wavelengthToBeamRgb(wavelengthInput: number): Vec3 {
  const wavelength = Math.min(700, Math.max(400, wavelengthInput))
  const x = cieX(wavelength)
  const y = cieY(wavelength)
  const z = cieZ(wavelength)
  const linear: Vec3 = [
    3.2406 * x - 1.5372 * y - 0.4986 * z,
    -0.9689 * x + 1.8758 * y + 0.0415 * z,
    0.0557 * x - 0.204 * y + 1.057 * z,
  ]
  const offset = Math.min(0, ...linear)
  const positive: Vec3 = [linear[0] - offset, linear[1] - offset, linear[2] - offset]
  const peak = Math.max(...positive, Number.EPSILON)
  const photopic = (d65SpectralPower(wavelength) * y) / D65_PHOTOPIC_PEAK
  const power = (1 - Math.exp(-SPECTRAL_EXPOSURE * photopic))
    / (1 - Math.exp(-SPECTRAL_EXPOSURE))
  return [
    (positive[0] / peak) * power * SPECTRAL_WHITE_BALANCE[0],
    (positive[1] / peak) * power * SPECTRAL_WHITE_BALANCE[1],
    (positive[2] / peak) * power * SPECTRAL_WHITE_BALANCE[2],
  ]
}
