/**
 * One model of light for both themes. A light's colour is set a fixed distance
 * from the page it shines on, measured in OKLab: its lightness is carried away
 * from the page's, lighter on a dark page and deeper on a light one, while its
 * hue stays. The strip and its glow then stand out as boldly on the dark page
 * as on the light one, from the same numbers.
 *
 * Colourfulness counts double in that distance, because a vivid colour reads
 * as a brighter light than its lightness alone says (the Helmholtz-Kohlrausch
 * effect): a strong orange on a pale page needs less lightness apart than a
 * soft blue on a dark one to look as bold.
 */

/** Red, green and blue from 0 to 1, as the page states them (sRGB). */
export type Rgb = readonly [number, number, number]

type Lab = [number, number, number]

/** How far a light stands from its page, in OKLab units with colourfulness doubled. */
export const LIGHT_DISTANCE = 0.55
/** How much colourfulness counts against lightness in that distance. */
export const VIVID = 2

const toLinear = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
const toEncoded = (c: number) => (c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055)

export function oklab([red, green, blue]: Rgb): Lab {
  const [r, g, b] = [toLinear(red), toLinear(green), toLinear(blue)]
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

/** Linear red, green and blue, which may fall outside 0 to 1 when the screen cannot show it. */
function linearFromOklab([lightness, a, b]: Lab): Lab {
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ]
}

const shown = (linear: Lab) => linear.every(c => c >= -1e-6 && c <= 1 + 1e-6)

/** How far apart two colours stand as lights: OKLab, with colourfulness doubled. */
export function distance(one: Rgb, other: Rgb): number {
  const [a, b] = [oklab(one), oklab(other)]
  return Math.hypot(a[0] - b[0], VIVID * (a[1] - b[1]), VIVID * (a[2] - b[2]))
}

/** The most of its strength (chroma) a colour at this lightness keeps on screen, from 0 to 1. */
function strengthShown(lightness: number, a: number, b: number): number {
  if (shown(linearFromOklab([lightness, a, b]))) return 1
  let [low, high] = [0, 1]
  for (let i = 0; i < 24; i++) {
    const mid = (low + high) / 2
    if (shown(linearFromOklab([lightness, a * mid, b * mid]))) low = mid
    else high = mid
  }
  return low
}

/**
 * `colour` as light on `page`: `reach` away from it, its hue kept. Lightness
 * goes up from a dark page and down from a light one; what the colour's own
 * tint does not give, lightness makes up. A colour the screen cannot show
 * loses strength, and lightness makes up for that too.
 */
export function asLight(colour: Rgb, page: Rgb, reach: number = LIGHT_DISTANCE): Rgb {
  const [pageL, pageA, pageB] = oklab(page)
  let [, a, b] = oklab(colour)
  const up = pageL < 0.5
  const tintOf = () => VIVID * Math.hypot(a - pageA, b - pageB)
  let lab: Lab = [pageL, a, b]
  for (let round = 0; round < 8; round++) {
    // Too strong a tint on its own comes back towards the page's.
    const tint = tintOf()
    if (tint > reach) {
      a = pageA + ((a - pageA) * reach) / tint
      b = pageB + ((b - pageB) * reach) / tint
    }
    const rest = Math.sqrt(Math.max(reach * reach - tintOf() ** 2, 0))
    const lightness = Math.min(1, Math.max(0, pageL + (up ? rest : -rest)))
    const strength = strengthShown(lightness, a, b)
    a *= strength
    b *= strength
    lab = [lightness, a, b]
    if (strength === 1) break
  }
  // Losing strength on a tinted page can carry the light past its reach.
  const [l0, a0, b0] = [lab[0] - pageL, lab[1] - pageA, lab[2] - pageB]
  const far = Math.hypot(l0, VIVID * a0, VIVID * b0)
  if (far > reach) lab = [pageL + (l0 * reach) / far, pageA + (a0 * reach) / far, pageB + (b0 * reach) / far]

  const linear = linearFromOklab(lab)
  return linear.map(c => toEncoded(Math.min(1, Math.max(0, c)))) as unknown as Rgb
}
