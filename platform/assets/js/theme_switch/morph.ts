/**
 * The swarm between the moon and the sun: one Anime.js timeline over plain
 * objects, one for each block, built paused and moved only by seeking it to the
 * knob's position. Holding the knob halfway holds the swarm halfway, some blocks
 * home, some in flight, some still waiting.
 *
 * Each block leaves in turn, clockwise from the bottom where the night light
 * sits, swirls once round the centre on its way (a polar path: its angle and
 * its distance from the centre each ride their own tween) and lands on its own
 * spring, so no two land quite alike. It tumbles as it goes, a whole number of
 * quarter turns on a springier spring of its own, so it lands square on the
 * grid after a wobble.
 *
 * A spring does most of its moving early and spends the rest of its time
 * settling, so the knob does not map straight onto the timeline's clock: it maps
 * onto how far the swarm has come, measured once when the timeline is built.
 * Halfway along the track the swarm is halfway there.
 */
import {createTimeline, spring, stagger, type Timeline} from "animejs"
import {turnBetween, wrapAngle, type Pair} from "./pixels"

/** Extra whole turns each block swirls on its way, clockwise from night to day. */
export const SWIRL_TURNS = 1
/** Timeline milliseconds from the first block's departure to the last's, however many there are. */
export const DEPARTURE_SPREAD = 720
/** The most quarter turns a block tumbles on its way; each tumbles at least one. */
export const MOST_QUARTER_TURNS = 3
/** Floats written per block: x and y in cells from the centre, its turn, share of day. */
export const PIXEL_STRIDE = 4
/** Points along the timeline where the swarm's progress is measured. */
const PROGRESS_SAMPLES = 240

/** One block in flight. Anime.js writes these fields; nothing else does. */
type Flight = {angle: number; radius: number; spin: number}

export type Morph = {
  readonly pairs: readonly Pair[]
  /** For each pair, its place in the departure order: 0 leaves first. */
  readonly departures: readonly number[]
  /** For each pair, the quarter turns its block tumbles on the way, clockwise. */
  readonly tumbles: readonly number[]
  readonly timeline: Timeline
  /** Moves every block to where knob position `p` (0 night, 1 day) puts it. */
  seek(p: number): void
  /** Writes each block as x, y, turn and share of day, PIXEL_STRIDE floats apiece. */
  write(out: Float32Array): void
}

const clampUnit = (value: number) => Math.min(1, Math.max(0, value))

// A stable spread in [0, 1) for block `i`, so each spring is its own but the
// picture is the same on every page.
const spread = (i: number) => {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453
  return x - Math.floor(x)
}

/** Departure order: clockwise from straight down, by where the moon block sits. */
export function departureOrder(pairs: readonly Pair[]): number[] {
  const fromBottom = pairs.map(pair => wrapAngle(pair.moon.angle - Math.PI / 2))
  const order = pairs.map((_, i) => i).sort((a, b) => fromBottom[a] - fromBottom[b] || a - b)
  const departures = new Array<number>(pairs.length)
  order.forEach((pair, rank) => {
    departures[pair] = rank
  })
  return departures
}

export function createMorph(pairs: readonly Pair[]): Morph {
  const departures = departureOrder(pairs)
  const turns = pairs.map(pair => turnBetween(pair.moon.angle, pair.sun.angle) + SWIRL_TURNS * Math.PI * 2)
  const tumbles = pairs.map((_, i) => 1 + Math.floor(spread(i + 57) * MOST_QUARTER_TURNS))
  const flights: Flight[] = pairs.map(pair => ({angle: pair.moon.angle, radius: pair.moon.radius, spin: 0}))
  const leave = stagger(DEPARTURE_SPREAD / Math.max(1, pairs.length - 1), {total: pairs.length})

  const timeline = createTimeline({autoplay: false})
  pairs.forEach((pair, i) => {
    const at = Number(leave(flights[i], departures[i]))
    timeline.add(
      flights[i],
      {
        angle: {from: pair.moon.angle, to: pair.moon.angle + turns[i]},
        radius: {from: pair.moon.radius, to: pair.sun.radius},
        // A spring's settling time is the tween's length, so each lands in its own time.
        ease: spring({bounce: 0.18 + 0.16 * spread(i), duration: 360 + 120 * spread(i + 31)}),
      },
      at,
    )
    timeline.add(
      flights[i],
      {
        spin: {from: 0, to: (tumbles[i] * Math.PI) / 2},
        ease: spring({bounce: 0.42, duration: 420 + 120 * spread(i + 13)}),
      },
      at,
    )
  })

  // How far the swarm has come at each sample, from 0 to 1. A block past its
  // place on a spring's overshoot counts as short of it, and the count never
  // goes back, so the knob only ever moves the clock forward.
  const progress: number[] = []
  for (let k = 0; k <= PROGRESS_SAMPLES; k++) {
    timeline.seek((k / PROGRESS_SAMPLES) * timeline.duration)
    const come = flights.reduce((sum, flight, i) => sum + 1 - Math.abs(1 - (flight.angle - pairs[i].moon.angle) / turns[i]), 0)
    progress.push(Math.max(progress.at(-1) ?? 0, k === PROGRESS_SAMPLES ? 1 : come / Math.max(1, pairs.length)))
  }
  timeline.seek(0)

  /** The timeline's clock at which the swarm has come `share` of the way. */
  const clockAt = (share: number) => {
    if (share <= 0) return 0
    if (share >= 1) return timeline.duration
    let k = 1
    while (progress[k] < share) k += 1
    const before = progress[k - 1]
    const within = progress[k] > before ? (share - before) / (progress[k] - before) : 0
    return ((k - 1 + within) / PROGRESS_SAMPLES) * timeline.duration
  }

  return {
    pairs,
    departures,
    tumbles,
    timeline,
    seek(p) {
      timeline.seek(clockAt(p))
    },
    write(out) {
      flights.forEach((flight, i) => {
        const at = i * PIXEL_STRIDE
        out[at] = Math.cos(flight.angle) * flight.radius
        out[at + 1] = Math.sin(flight.angle) * flight.radius
        out[at + 2] = flight.spin
        out[at + 3] = clampUnit((flight.angle - pairs[i].moon.angle) / turns[i])
      })
    },
  }
}
