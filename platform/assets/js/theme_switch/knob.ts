/**
 * Where the theme switch's knob is, as one number: 0 with the knob to the left
 * for night (the dark theme), 1 to the right for day (the light theme). The
 * picture, the still face and the theme all read it from here.
 */
import type {Theme} from "../theme"

export type Side = 0 | 1

/** How far a press must travel sideways, in CSS pixels, before it is a drag. */
const DRAG_START: Record<string, number> = {mouse: 3, pen: 4, touch: 6}

export const dragStart = (pointerType: string): number => DRAG_START[pointerType] ?? DRAG_START.touch

/** A press becomes a drag once it has moved far enough sideways. */
export const isDrag = (dx: number, pointerType: string): boolean => Math.abs(dx) >= dragStart(pointerType)

/**
 * The knob under a drag: where it started, moved by the pointer's travel as a
 * share of the knob's own travel, and never past either end.
 */
export function draggedPosition(start: number, dx: number, travel: number): number {
  if (!(travel > 0)) return start
  return Math.min(1, Math.max(0, start + dx / travel))
}

/** The side a released knob settles on: the nearer one, day from halfway. */
export const settleSide = (p: number): Side => (p >= 0.5 ? 1 : 0)

export const sideOf = (theme: Theme): Side => (theme === "light" ? 1 : 0)

export const themeOf = (side: Side): Theme => (side === 1 ? "light" : "dark")

/**
 * The light strip's place round the glass, in radians clockwise on screen from
 * straight right: below the knob at night, above it by day, passing round the
 * side it trails, as a ball rolling to the right turns.
 */
export const stripAngle = (p: number): number => Math.PI / 2 + Math.PI * Math.min(1, Math.max(0, p))
