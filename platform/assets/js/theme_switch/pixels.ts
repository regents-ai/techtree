/**
 * The theme switch's two pictures, the moon for night and the sun for day, as
 * blocks on a square grid. The server holds both and draws them in the still
 * face (`TechtreeWeb.Components.ThemeSwitch`); the browser reads the blocks back from there,
 * so there is one source of both pictures. Every block of the moon flies to the
 * block of the sun it is paired with, so the two must have as many blocks.
 */

/** A block of a picture: its column and row on the grid, from the top left. */
export type Cell = {readonly col: number; readonly row: number}

/** A block as a point, in cells from the grid's centre: x to the right, y down. */
export type Pixel = {
  readonly x: number
  readonly y: number
  /** Clockwise on screen from straight right, in [0, 2π); 0 at the centre itself. */
  readonly angle: number
  readonly radius: number
}

/** A block of the moon and the block of the sun it becomes. */
export type Pair = {readonly moon: Pixel; readonly sun: Pixel}

const TURN = Math.PI * 2

/** Folds any angle into [0, 2π). */
export const wrapAngle = (angle: number): number => ((angle % TURN) + TURN) % TURN

/** The shortest signed turn from `from` to `to`, in (-π, π]. */
export const turnBetween = (from: number, to: number): number => {
  const turn = wrapAngle(to - from)
  return turn > Math.PI ? turn - TURN : turn
}

/** A picture's blocks as pixels round the grid's centre, in the order given. */
export function pixelsOf(cells: readonly Cell[], grid: number): Pixel[] {
  const centre = (grid - 1) / 2
  return cells.map(({col, row}) => {
    const dx = col - centre
    const dy = row - centre
    return {x: dx, y: dy, angle: wrapAngle(Math.atan2(dy, dx)), radius: Math.hypot(dx, dy)}
  })
}

const byAngle = (a: Pixel, b: Pixel) => a.angle - b.angle || a.radius - b.radius

/**
 * Pairs every pixel of one picture with one of the other by angle round the
 * centre. Both are walked in clockwise order; the walk round the second starts
 * wherever the pairs, taken together, turn least. The result keeps the first
 * picture's clockwise order, so neighbours stay neighbours in flight.
 */
export function pairByAngle(from: readonly Pixel[], to: readonly Pixel[]): Pair[] {
  if (from.length !== to.length) {
    throw new Error(`the pictures differ in size: ${from.length} and ${to.length} pixels`)
  }
  const moons = [...from].sort(byAngle)
  const suns = [...to].sort(byAngle)
  const count = moons.length
  let start = 0
  let least = Infinity
  for (let shift = 0; shift < count; shift++) {
    let turn = 0
    for (let i = 0; i < count; i++) turn += Math.abs(turnBetween(moons[i].angle, suns[(i + shift) % count].angle))
    if (turn < least - 1e-9) {
      least = turn
      start = shift
    }
  }
  return moons.map((moon, i) => ({moon, sun: suns[(i + start) % count]}))
}

/**
 * How much of the glass's side the blocks' grid spans, behind the glass and in
 * the still face alike. The pictures keep the grid's outer ring clear, so what
 * is drawn sits in the glass's flat middle and the bevel never smears it.
 */
export const ICON_FILL = 0.65

/** Where the blocks sit, in canvas pixels: the grid's centre, one cell, and a block's half side in cells. */
export type IconGrid = {readonly x: number; readonly y: number; readonly cell: number; readonly half: number}

/**
 * The block grid for a lens `side` canvas pixels across, centred on `centre`.
 * A cell is a whole number of canvas pixels and a block a pixel or so short of
 * it, so a hairline shows between neighbours. At rest the block edges fall on
 * whole pixels, so they draw crisp; `rest` runs from 0 in flight to 1 at rest
 * and carries the grid smoothly from the lens's own centre to that place.
 */
export function iconGrid(centre: readonly [number, number], side: number, grid: number, rest: number): IconGrid {
  const cell = Math.max(1, Math.round((ICON_FILL * side) / grid))
  const gap = cell >= 3 ? Math.max(1, Math.round(cell * 0.1)) : 0
  const block = cell - gap
  // On an even grid the centre falls between blocks, half a cell from each.
  const shift = grid % 2 === 1 ? 0 : cell / 2
  const crisp = (at: number) => Math.round(at + shift - block / 2) - shift + block / 2
  const settle = Math.min(1, Math.max(0, rest))
  return {
    x: centre[0] + (crisp(centre[0]) - centre[0]) * settle,
    y: centre[1] + (crisp(centre[1]) - centre[1]) * settle,
    cell,
    half: block / (2 * cell),
  }
}
