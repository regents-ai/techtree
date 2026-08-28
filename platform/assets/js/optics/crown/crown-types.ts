export type Vec2 = readonly [number, number];
export type Vec3 = readonly [number, number, number];

/**
 * Exact Regents mark, expressed as a 5-column grid.
 *
 * y grows upward in the prism scene. The top row occupies columns 0, 2 and 4;
 * the middle and bottom rows occupy all five columns.
 */
export const CROWN_GRID = [
  [-2, 1],
  [0, 1],
  [2, 1],

  [-2, 0],
  [-1, 0],
  [0, 0],
  [1, 0],
  [2, 0],

  [-2, -1],
  [-1, -1],
  [0, -1],
  [1, -1],
  [2, -1],
] as const satisfies readonly Vec2[];

export const CROWN_CELL_COUNT = 13;
export const CROWN_SCALE = 0.85;

/** Front-face width and height of one cube, in the prism scene's world units. */
export const CROWN_CELL_SIZE = 0.22 * CROWN_SCALE;
/** Air between adjacent cubes. This is about 11% of the cube face width. */
export const CROWN_GAP = 0.025 * CROWN_SCALE;
export const CROWN_PITCH = CROWN_CELL_SIZE + CROWN_GAP;

/** A true shallow cube: depth equals front-face width. */
export const CROWN_DEPTH = CROWN_CELL_SIZE;
/** Same anti-z-fighting gap used by the VGPU prism scene. */
export const CROWN_WALL_GAP = 0.015;
export const CROWN_BACK_Z = CROWN_WALL_GAP;
export const CROWN_FRONT_Z = CROWN_WALL_GAP + CROWN_DEPTH;
export const CROWN_LIGHT_PLANE_Z = (CROWN_BACK_Z + CROWN_FRONT_Z) * 0.5;

/**
 * The visible mesh is rounded inward, while the optical shader uses the ideal
 * square envelope. This is the same visual-mesh/analytic-envelope split used by
 * the original triangle prism.
 */
export const CROWN_XY_CORNER_RADIUS = 0.018 * CROWN_SCALE;
export const CROWN_Z_BEVEL_RADIUS = 0.014 * CROWN_SCALE;
export const CROWN_CORNER_SEGMENTS = 4;
export const CROWN_Z_BEVEL_SEGMENTS = 4;

export const CROWN_CELL_CENTERS = CROWN_GRID.map(
  ([column, row]) => [column * CROWN_PITCH, row * CROWN_PITCH] as const,
);

export const CROWN_HALF_SIZE = CROWN_CELL_SIZE * 0.5;

export const CROWN_BOUNDS = {
  halfWidth: 2 * CROWN_PITCH + CROWN_HALF_SIZE,
  halfHeight: CROWN_PITCH + CROWN_HALF_SIZE,
} as const;

/** All eight corners used to fit the complete three-dimensional crown. */
export const CROWN_AABB_CORNERS = [CROWN_BACK_Z, CROWN_FRONT_Z].flatMap((z) =>
  [-CROWN_BOUNDS.halfHeight, CROWN_BOUNDS.halfHeight].flatMap((y) =>
    [-CROWN_BOUNDS.halfWidth, CROWN_BOUNDS.halfWidth].map(
      (x) => [x, y, z] as const,
    ),
  ),
) satisfies readonly Vec3[];

/** Vertical field of view and preferred distance from the reviewed predecessor. */
export const CAMERA_FOV_DEGREES = 70;
export const CAMERA_DISTANCE = 1.31;
export const CAMERA_YAW_DEGREES = 0;
export const CAMERA_PITCH_DEGREES = 0;
export const CAMERA_ORBIT_DEGREES = 3.5;
export const CAMERA_ORBIT_LERP = 0.08;
export const CROWN_AIM_QUANTIZATION_STEP = 1 / 64;

export interface CrownGlassMaterial {
  readonly ior: number;
  readonly reflectionStrength: number;
  readonly absorption: readonly [number, number, number];
  readonly frostRadius: number;
  readonly dispersion: number;
  readonly iridescenceStrength: number;
  readonly iridescenceFrequency: number;
  readonly environmentExposure: number;
  readonly environmentRotation: readonly [number, number, number];
}

/** The current production dark-prism transmission and reflection controls. */
export const CROWN_GLASS: CrownGlassMaterial = {
  ior: 1.645,
  reflectionStrength: 2.14,
  absorption: [1, 1, 0.54],
  frostRadius: 0,
  dispersion: 0,
  iridescenceStrength: 0,
  iridescenceFrequency: 2,
  environmentExposure: 2.3,
  environmentRotation: [0, 0, 0],
};

/** HDR operations carried forward unchanged from the reviewed prism renderer. */
export const CROWN_POSTPROCESS = {
  bloomStrength: 0.7,
  bloomThreshold: 0.1,
  bloomRadius: 0.25,
} as const;

/** Exact light-falloff controls from the production dark prism shot. */
export const CROWN_LIGHT = {
  opacity: 1,
  edgeFalloff: 16,
  rainbowFalloffRate: 3.8,
  rainbowFalloffPower: 3.7,
} as const;

export type CrownVariant = 1 | 2 | 3 | 4;

const GRAZE_LIGHT = {
  sourceSides: [1],
  sourceYOffset: 0,
  angleBase: -0.065,
  angleRange: 0.075,
  rowConvergence: 0.032,
  verticalTravel: 0.055,
  dispersionStrength: 0.04,
  wedgeStrength: 0.14,
  spectralSamples: 32,
  beamHalfWidth: 0.032,
  spectralHalfWidth: 0.0075,
  inputIntensity: 3.5,
  internalIntensity: 0.1,
  spectralIntensity: 2.35,
  echoIntensity: 0,
  inputColor: [1, 1, 1],
  internalColor: [1, 1, 1],
  spectralColor: null,
} as const;

export const CROWN_VARIANTS = {
  1: {
    ...GRAZE_LIGHT,
    backgroundColor: [0, 0, 0, 1],
    absorption: [1, 1, 0.54],
    glassDispersion: 0.02,
    reflectionStrength: 0.9,
    environmentExposure: 1.15,
    environmentRotation: [0, -18, 0],
    bloomThreshold: 0.1,
    bloomStrength: 0.7,
  },
  2: {
    ...GRAZE_LIGHT,
    backgroundColor: [0.38, 0.035, 0.003, 1],
    absorption: [1, 0.82, 0.42],
    glassDispersion: 0.02,
    reflectionStrength: 0.7,
    environmentExposure: 0.92,
    environmentRotation: [0, -30, 0],
    bloomThreshold: 0.85,
    bloomStrength: 0.45,
  },
  3: {
    ...GRAZE_LIGHT,
    backgroundColor: [0.002, 0.002, 0.0025, 1],
    absorption: [0.12, 0.12, 0.12],
    glassDispersion: 0.016,
    reflectionStrength: 1.25,
    environmentExposure: 1.3,
    environmentRotation: [0, 14, 0],
    bloomThreshold: 0.12,
    bloomStrength: 0.5,
  },
  4: {
    ...GRAZE_LIGHT,
    backgroundColor: [0.055, 0.065, 0.075, 1],
    absorption: [0.45, 0.48, 0.52],
    spectralSamples: 20,
    beamHalfWidth: 0.044,
    spectralHalfWidth: 0.01,
    inputIntensity: 3.9,
    internalIntensity: 0.1,
    spectralIntensity: 0.72,
    inputColor: [1, 0.17, 0.004],
    internalColor: [1, 0.14, 0.002],
    spectralColor: [1, 0.11, 0.001],
    glassDispersion: 0.012,
    reflectionStrength: 0.85,
    environmentExposure: 1.05,
    environmentRotation: [0, -28, 0],
    bloomThreshold: 0.7,
    bloomStrength: 0.85,
  },
} as const;

export function crownVariant(value: string | number | undefined): CrownVariant {
  const parsed = Number(value);
  return parsed === 2 || parsed === 3 || parsed === 4 ? parsed : 1;
}

export function quantizeCrownAim(aim: Vec2): Vec2 {
  const quantize = (value: number): number => {
    const clamped = Math.min(1, Math.max(-1, Number.isFinite(value) ? value : 0));
    return Math.round(clamped / CROWN_AIM_QUANTIZATION_STEP)
      * CROWN_AIM_QUANTIZATION_STEP;
  };

  return [quantize(aim[0]), quantize(aim[1])];
}
