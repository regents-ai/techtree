/**
 * The one camera in the scene. Forked from the Vercel vgpu prism background. See
 * THIRD_PARTY_NOTICES.md.
 *
 * Its distance is derived from the complete crown AABB. Every aspect ratio gets one
 * distance that fits all eight 3D corners at every permitted orbit extreme, leaving
 * the same deliberate screen-space breathing room through pointer motion and resize.
 */

import {perspectiveCamera, type SceneCamera} from "vgpu/scene"

import {
  CROWN_AABB_CORNERS,
  CAMERA_DISTANCE,
  CAMERA_FOV_DEGREES,
  CAMERA_ORBIT_DEGREES,
  CAMERA_PITCH_DEGREES,
  CAMERA_YAW_DEGREES,
  type Vec3,
} from "./crown-types"

/** At least eight percent of each screen dimension remains clear around the crown. */
export const CROWN_FRAME_MARGIN = 0.08
const CAMERA_FIT_SAFETY = 1.005

export interface CameraView {
  readonly camera: SceneCamera
  /** Projection shifted in clip space without changing the physical view ray. */
  readonly viewProjection: Float32Array
  readonly position: Vec3
  /** Orthonormal basis: where the camera looks, and the frame's axes. */
  readonly forward: Vec3
  readonly right: Vec3
  readonly up: Vec3
}

const radians = (degrees: number): number => (degrees * Math.PI) / 180
const clamp = (value: number, low: number, high: number): number =>
  Math.min(high, Math.max(low, value))

const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
]

const normalize = (value: Vec3): Vec3 => {
  const length = Math.hypot(value[0], value[1], value[2]) || 1
  return [value[0] / length, value[1] / length, value[2] / length]
}

/**
 * The camera for a pointer position, both components in [-1, 1] with 0 at rest.
 *
 * It swings on a sphere around the origin and keeps looking at it. A clip-space
 * offset composes the crown in the right-hand field on wide screens without
 * changing the physical view ray that creates its reflections.
 */
export function cameraView(aspect: number, orbitX = 0, orbitY = 0): CameraView {
  const distance = crownCameraDistance(aspect)
  const yaw = radians(CAMERA_YAW_DEGREES + clamp(orbitX, -1, 1) * CAMERA_ORBIT_DEGREES)
  const pitch = radians(CAMERA_PITCH_DEGREES - clamp(orbitY, -1, 1) * CAMERA_ORBIT_DEGREES)
  const cosPitch = Math.cos(pitch)
  const position: Vec3 = [
    Math.sin(yaw) * cosPitch * distance,
    Math.sin(pitch) * distance,
    Math.cos(yaw) * cosPitch * distance,
  ]
  const forward = normalize([-position[0], -position[1], -position[2]])
  const right = normalize(cross(forward, [0, 1, 0]))
  const camera = perspectiveCamera({
    fov: CAMERA_FOV_DEGREES,
    aspect,
    // The whole scene sits between the wall at z = 0 and the glass in front of it,
    // so the depth range only has to bracket a couple of units.
    near: 0.05,
    far: 4 * distance,
    position,
    target: [0, 0, 0],
  })
  return {
    camera,
    viewProjection: shiftedViewProjection(
      camera.viewProjection,
      crownFrameOffsetNdc(aspect, camera.viewProjection),
    ),
    position,
    forward,
    right,
    up: cross(right, forward),
  }
}

/**
 * Camera distance that fits every AABB corner at every orbit extreme.
 *
 * For a point projected onto one camera axis, screen occupancy is
 * `axis / ((distance + forwardDepth) * tanHalfFov)`. Rearranging that expression
 * gives the minimum distance directly, without viewport-name branches or search.
 */
export function crownCameraDistance(aspect: number): number {
  const safeAspect = Math.max(0.01, aspect)
  const tanHalfFov = Math.tan(radians(CAMERA_FOV_DEGREES) / 2)
  const usableNdc = 1 - CROWN_FRAME_MARGIN * 2
  let required = 0

  for (const orbitX of [-1, 0, 1]) {
    for (const orbitY of [-1, 0, 1]) {
      const yaw = radians(CAMERA_YAW_DEGREES + orbitX * CAMERA_ORBIT_DEGREES)
      const pitch = radians(CAMERA_PITCH_DEGREES - orbitY * CAMERA_ORBIT_DEGREES)
      const cosPitch = Math.cos(pitch)
      const forward = normalize([
        -Math.sin(yaw) * cosPitch,
        -Math.sin(pitch),
        -Math.cos(yaw) * cosPitch,
      ])
      const right = normalize(cross(forward, [0, 1, 0]))
      const up = cross(right, forward)

      for (const corner of CROWN_AABB_CORNERS) {
        const forwardDepth = dot(corner, forward)
        required = Math.max(
          required,
          Math.abs(dot(corner, right)) / (usableNdc * tanHalfFov * safeAspect) - forwardDepth,
          Math.abs(dot(corner, up)) / (usableNdc * tanHalfFov) - forwardDepth,
        )
      }
    }
  }

  return Math.max(CAMERA_DISTANCE, required * CAMERA_FIT_SAFETY)
}

/** Keeps narrow layouts low and centred, then composes wide layouts at 70%. */
export function crownFrameOffsetNdc(
  aspect: number,
  centeredViewProjection?: Float32Array,
): readonly [number, number] {
  const landscapeProgress = clamp((aspect - 1.35) / 0.2, 0, 1)
  const narrowProgress = clamp((1.45 - aspect) / 0.6, 0, 1)
  const desiredX = 0.46 * landscapeProgress
  const desiredY = -0.55 * narrowProgress
  if (!centeredViewProjection) return [desiredX, desiredY]

  const bounds = projectedCrownBounds(centeredViewProjection)
  const usableNdc = 1 - CROWN_FRAME_MARGIN * 2
  return [
    Math.min(desiredX, usableNdc - bounds.maxX),
    Math.max(desiredY, -usableNdc - bounds.minY),
  ]
}

function projectedCrownBounds(matrix: Float32Array) {
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  for (const [x, y, z] of CROWN_AABB_CORNERS) {
    const clipX = matrix[0]! * x + matrix[4]! * y + matrix[8]! * z + matrix[12]!
    const clipY = matrix[1]! * x + matrix[5]! * y + matrix[9]! * z + matrix[13]!
    const clipW = matrix[3]! * x + matrix[7]! * y + matrix[11]! * z + matrix[15]!
    maxX = Math.max(maxX, clipX / clipW)
    minY = Math.min(minY, clipY / clipW)
  }
  return {maxX, minY}
}

function shiftedViewProjection(
  matrix: Float32Array,
  [offsetX, offsetY]: readonly [number, number],
): Float32Array {
  const shifted = new Float32Array(matrix)
  for (let column = 0; column < 4; column++) {
    shifted[column * 4] += offsetX * matrix[column * 4 + 3]!
    shifted[column * 4 + 1] += offsetY * matrix[column * 4 + 3]!
  }
  return shifted
}

const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

/** Column-major XYZ rotation, used for the studio environment's orientation. */
export function rotationMatrix(degrees: readonly [number, number, number]): Float32Array {
  const [x, y, z] = degrees.map(radians) as [number, number, number]
  const [sx, cx] = [Math.sin(x), Math.cos(x)]
  const [sy, cy] = [Math.sin(y), Math.cos(y)]
  const [sz, cz] = [Math.sin(z), Math.cos(z)]
  return new Float32Array([
    cy * cz, cy * sz, -sy, 0,
    sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy, 0,
    cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy, 0,
    0, 0, 0, 1,
  ])
}
