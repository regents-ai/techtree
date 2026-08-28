/**
 * Procedural Regents crown geometry for VGPU.
 *
 * This is a direct structural adaptation of VGPU's prism-mesh.ts:
 * - a rounded 2D contour is extruded along z;
 * - front/back bevel rings are generated inside an ideal optical envelope;
 * - caps are duplicated so they keep flat normals;
 * - all 13 disconnected solids are uploaded as one small Geometry.
 */

import type { Geometry, Gpu } from "vgpu";
import { geometry } from "vgpu";

import {
  CROWN_BACK_Z,
  CROWN_CELL_CENTERS,
  CROWN_CELL_COUNT,
  CROWN_CORNER_SEGMENTS,
  CROWN_FRONT_Z,
  CROWN_HALF_SIZE,
  CROWN_XY_CORNER_RADIUS,
  CROWN_Z_BEVEL_RADIUS,
  CROWN_Z_BEVEL_SEGMENTS,
  type Vec2,
} from "./crown-types";

type Vec3 = readonly [number, number, number];

interface ContourPoint {
  readonly position: Vec2;
  readonly normal: Vec2;
}

export interface CrownMeshData {
  /** position.xyz, normal.xyz, cellCenter.xy: 8 floats per vertex. */
  readonly vertices: Float32Array<ArrayBuffer>;
  readonly indices: Uint16Array<ArrayBuffer>;
  readonly cellCount: number;
  readonly verticesPerCell: number;
  readonly indicesPerCell: number;
}

export const CROWN_VERTEX_FLOATS = 8;
export const CROWN_VERTEX_STRIDE =
  CROWN_VERTEX_FLOATS * Float32Array.BYTES_PER_ELEMENT;

/**
 * Build all thirteen cubes as disconnected components in one indexed mesh.
 * Every triangle carries one constant cellCenter attribute, which lets the glass
 * shader intersect the correct ideal cube rather than treating the logo as one
 * fused solid.
 */
export function crownMeshData(): CrownMeshData {
  if (CROWN_CELL_CENTERS.length !== CROWN_CELL_COUNT) {
    throw new Error(
      `Regents crown requires ${CROWN_CELL_COUNT} cells; got ${CROWN_CELL_CENTERS.length}.`,
    );
  }

  const contour = roundedSquareContour(
    CROWN_HALF_SIZE,
    CROWN_XY_CORNER_RADIUS,
    CROWN_CORNER_SEGMENTS,
  );
  const vertices: number[] = [];
  const indices: number[] = [];

  let firstVerticesPerCell = 0;
  let firstIndicesPerCell = 0;

  for (let cellId = 0; cellId < CROWN_CELL_CENTERS.length; cellId++) {
    const center = CROWN_CELL_CENTERS[cellId]!;
    const vertexStart = vertices.length / CROWN_VERTEX_FLOATS;
    const indexStart = indices.length;
    appendRoundedCell(vertices, indices, contour, center);

    const verticesWritten =
      vertices.length / CROWN_VERTEX_FLOATS - vertexStart;
    const indicesWritten = indices.length - indexStart;
    if (cellId === 0) {
      firstVerticesPerCell = verticesWritten;
      firstIndicesPerCell = indicesWritten;
    } else if (
      verticesWritten !== firstVerticesPerCell ||
      indicesWritten !== firstIndicesPerCell
    ) {
      throw new Error("Every crown cell must have identical topology.");
    }
  }

  const vertexCount = vertices.length / CROWN_VERTEX_FLOATS;
  if (vertexCount > 65_535) {
    throw new Error(
      `Crown mesh has ${vertexCount} vertices; Uint16 indices support at most 65535.`,
    );
  }

  return {
    vertices: new Float32Array(vertices),
    indices: new Uint16Array(indices),
    cellCount: CROWN_CELL_CENTERS.length,
    verticesPerCell: firstVerticesPerCell,
    indicesPerCell: firstIndicesPerCell,
  };
}

/** Uploads the complete 13-cell crown. The caller owns and must destroy it. */
export function crownGeometry(gpu: Gpu, label = "regents-crown"): Geometry {
  const { vertices, indices } = crownMeshData();
  return geometry(gpu, {
    label,
    buffers: [
      {
        data: vertices,
        stride: CROWN_VERTEX_STRIDE,
        attributes: {
          position: { format: "float32x3", offset: 0, location: 0 },
          normal: { format: "float32x3", offset: 12, location: 1 },
          cell_center: { format: "float32x2", offset: 24, location: 2 },
        },
      },
    ],
    indices,
  });
}

function appendRoundedCell(
  vertices: number[],
  indices: number[],
  contour: readonly ContourPoint[],
  center: Vec2,
): void {
  const rings: number[][] = [];
  const zRadius = Math.min(
    CROWN_Z_BEVEL_RADIUS,
    (CROWN_FRONT_Z - CROWN_BACK_Z) * 0.45,
  );

  const push = (position: Vec3, normal: Vec3): number => {
    const index = vertices.length / CROWN_VERTEX_FLOATS;
    vertices.push(
      position[0],
      position[1],
      position[2],
      normal[0],
      normal[1],
      normal[2],
      center[0],
      center[1],
    );
    return index;
  };

  const addRing = (theta: number, z: number, zNormal: number): number[] => {
    const inset = zRadius * (1 - Math.cos(theta));
    const xyWeight = Math.cos(theta);
    const ring = contour.map(({ position, normal }) =>
      push(
        [
          center[0] + position[0] - normal[0] * inset,
          center[1] + position[1] - normal[1] * inset,
          z,
        ],
        [normal[0] * xyWeight, normal[1] * xyWeight, zNormal],
      ),
    );
    rings.push(ring);
    return ring;
  };

  // Stop just short of pi/2 so cap boundary triangles retain positive area.
  const maxTheta = Math.PI / 2 - 0.06;
  const maxSine = Math.sin(maxTheta);

  for (let step = CROWN_Z_BEVEL_SEGMENTS; step >= 0; step--) {
    const theta = (maxTheta * step) / CROWN_Z_BEVEL_SEGMENTS;
    addRing(
      theta,
      CROWN_BACK_Z + zRadius - (zRadius * Math.sin(theta)) / maxSine,
      -Math.sin(theta),
    );
  }

  for (let step = 0; step <= CROWN_Z_BEVEL_SEGMENTS; step++) {
    const theta = (maxTheta * step) / CROWN_Z_BEVEL_SEGMENTS;
    addRing(
      theta,
      CROWN_FRONT_Z - zRadius + (zRadius * Math.sin(theta)) / maxSine,
      Math.sin(theta),
    );
  }

  for (let band = 0; band < rings.length - 1; band++) {
    const current = rings[band]!;
    const next = rings[band + 1]!;
    for (let point = 0; point < contour.length; point++) {
      const following = (point + 1) % contour.length;
      indices.push(
        current[point]!,
        current[following]!,
        next[following]!,
        current[point]!,
        next[following]!,
        next[point]!,
      );
    }
  }

  addCap(rings[0]!, [0, 0, -1], true);
  addCap(rings[rings.length - 1]!, [0, 0, 1], false);

  function addCap(
    sourceRing: readonly number[],
    normal: Vec3,
    reverse: boolean,
  ): void {
    const cap = sourceRing.map((source) => {
      const base = source * CROWN_VERTEX_FLOATS;
      return push(
        [vertices[base]!, vertices[base + 1]!, vertices[base + 2]!],
        normal,
      );
    });
    const z = vertices[cap[0]! * CROWN_VERTEX_FLOATS + 2]!;
    const centerIndex = push([center[0], center[1], z], normal);
    for (let point = 0; point < cap.length; point++) {
      const following = (point + 1) % cap.length;
      if (reverse) indices.push(centerIndex, cap[following]!, cap[point]!);
      else indices.push(centerIndex, cap[point]!, cap[following]!);
    }
  }
}

/**
 * Rounded square, wound counter-clockwise. Adjacent corner arc endpoints have
 * matching edge normals, so the straight runs between arcs remain flat.
 */
function roundedSquareContour(
  halfSize: number,
  radius: number,
  segments: number,
): ContourPoint[] {
  const safeRadius = Math.min(Math.max(radius, 0), halfSize * 0.49);
  const safeSegments = Math.max(1, Math.floor(segments));
  const inner = halfSize - safeRadius;

  const corners = [
    { center: [inner, -inner] as const, start: -Math.PI / 2 },
    { center: [inner, inner] as const, start: 0 },
    { center: [-inner, inner] as const, start: Math.PI / 2 },
    { center: [-inner, -inner] as const, start: Math.PI },
  ] as const;

  return corners.flatMap(({ center, start }) =>
    Array.from({ length: safeSegments + 1 }, (_, step): ContourPoint => {
      const angle = start + (Math.PI / 2) * (step / safeSegments);
      const normal: Vec2 = [Math.cos(angle), Math.sin(angle)];
      return {
        position: [
          center[0] + normal[0] * safeRadius,
          center[1] + normal[1] * safeRadius,
        ],
        normal,
      };
    }),
  );
}
