/**
 * The home page's moving pictures, each one fragment shader over a shared
 * set of uniforms, drawn by `field.ts`:
 *
 * - `glow`: the light behind the hero's Results, a dot matrix whose dots swell
 *   where two slow lights drift and where the mouse is.
 * - `screen`: a dot screen that draws one shape, with a light sweeping down it.
 * - `mark`: square ripples spreading from the middle of the closing band, the
 *   shape of the mark's own squares.
 * - `backdrop`: contour lines that drift across the top of a service card.
 *
 * Every picture is laid out in CSS pixels and scaled to the canvas, so a phone
 * and a wide screen see the same picture. This file imports nothing, so the
 * unit tests read the same uniforms the page sends.
 */

export const SCENES = ["glow", "screen", "mark", "backdrop"] as const
export type Scene = (typeof SCENES)[number]

/** The shapes the dot screen draws, in the order of their numbers in the shader. */
export const SHAPES = ["ring", "pair", "steps", "check", "seal", "lines", "branch", "blocks", "peak"] as const
export type Shape = (typeof SHAPES)[number]

/** The picture's colours as `#rrggbb`: the ground, the ink it draws with, and its glow. */
export type Colours = {ground: string; ink: string; glow: string}

/** A hex colour as linear-light channels, which is what the shaders mix. */
export const linear = (hex: string): [number, number, number, number] => {
  const channel = (at: number) => {
    const value = Number.parseInt(hex.slice(at, at + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return [channel(1), channel(3), channel(5), 1]
}

/** One frame's state, as `field.ts` keeps it. */
export type Frame = {
  width: number
  height: number
  /** Canvas pixels for each CSS pixel. */
  scale: number
  seconds: number
  /** The pointer across the picture, each axis 0 to 1 with y down, and how present it is. */
  pointer: readonly [number, number, number]
  colours: Colours
  /** The number of the shape the dot screen draws (`SHAPES`). */
  shape: number
}

/** Every member of the shared uniform struct, for one frame. */
export const uniforms = (frame: Frame) => ({
  params: {
    size: [frame.width, frame.height, frame.scale, frame.seconds],
    pointer: [...frame.pointer, 0],
    ground: linear(frame.colours.ground),
    ink: linear(frame.colours.ink),
    glow: linear(frame.colours.glow),
    shape: [frame.shape, 0, 0, 0],
  },
})

const shared = /* wgsl */ `
// Size (width, height, canvas pixels per CSS pixel, seconds), the pointer (x, y
// with y down, how present it is), three colours in linear light, and the shape's
// number.
struct Params {
  size: vec4f,
  pointer: vec4f,
  ground: vec4f,
  ink: vec4f,
  glow: vec4f,
  shape: vec4f,
}
@group(0) @binding(0) var<uniform> params: Params;

fn sat(v: f32) -> f32 { return clamp(v, 0.0, 1.0); }
// A 0..1 value for a whole-numbered place, by integer arithmetic so every GPU agrees.
fn hash(p: vec2f) -> f32 {
  let q = vec2u(vec2i(floor(p)));
  var n = (q.x * 1597334677u) ^ (q.y * 3812015801u);
  n = (n ^ (n >> 16u)) * 2246822519u;
  n = n ^ (n >> 13u);
  return f32(n >> 8u) / 16777216.0;
}
fn noise(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2f(1.0, 0.0)), u.x), mix(hash(i + vec2f(0.0, 1.0)), hash(i + vec2f(1.0, 1.0)), u.x), u.y);
}
fn fbm(p: vec2f) -> f32 {
  var sum = 0.0;
  var amp = 0.5;
  var q = p;
  for (var i = 0; i < 4; i = i + 1) {
    sum = sum + amp * noise(q);
    q = q * 2.03 + vec2f(17.0, 9.0);
    amp = amp * 0.5;
  }
  return sum;
}
fn time() -> f32 { return params.size.w; }
fn scale() -> f32 { return params.size.z; }
// Scales a 0..1 offset so a circle stays round in a picture of any shape.
fn aspect() -> vec2f { return params.size.xy / min(params.size.x, params.size.y); }
// Linear light to the screen's sRGB.
fn toSrgb(c: vec3f) -> vec3f {
  return select(1.055 * pow(c, vec3f(1.0 / 2.4)) - vec3f(0.055), c * 12.92, c <= vec3f(0.0031308));
}
fn paint(c: vec3f) -> vec4f { return vec4f(toSrgb(clamp(c, vec3f(0.0), vec3f(1.0))), 1.0); }

fn sdBox(p: vec2f, half: vec2f, r: f32) -> f32 {
  let q = abs(p) - half + vec2f(r);
  return length(max(q, vec2f(0.0))) + min(max(q.x, q.y), 0.0) - r;
}
fn sdSeg(p: vec2f, a: vec2f, b: vec2f) -> f32 {
  let pa = p - a;
  let ba = b - a;
  return length(pa - ba * sat(dot(pa, ba) / dot(ba, ba)));
}

// One dot of a dot matrix: this pixel's cell of the given pitch in CSS pixels,
// and how far the pixel is from the cell's centre, in CSS pixels.
struct Cell { at: vec2f, off: f32 }
fn cell(uv: vec2f, pitch: f32) -> Cell {
  let px = uv * params.size.xy / scale();
  let id = floor(px / pitch);
  let centre = (id + vec2f(0.5)) * pitch;
  return Cell(centre * scale() / params.size.xy, length(px - centre));
}
// How much of a dot of radius r (CSS pixels) covers this pixel.
fn spot(c: Cell, r: f32) -> f32 {
  let edge = 0.6 / scale();
  return 1.0 - smoothstep(r - edge, r + edge, c.off);
}
`

const glow = /* wgsl */ `
@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let t = time();
  let a = aspect();
  let c = cell(uv, 7.0);
  let p = c.at;
  let one = vec2f(0.5 + 0.2 * sin(t * 0.21), 0.56 + 0.1 * cos(t * 0.17));
  let two = vec2f(0.5 + 0.3 * cos(t * 0.13 + 1.7), 0.42 + 0.16 * sin(t * 0.19 + 0.4));
  let hand = vec2f(params.pointer.x, params.pointer.y);
  let d1 = length((p - one) * a);
  let d2 = length((p - two) * a);
  let d3 = length((p - hand) * a);
  let grain = fbm(p * a * 3.0 + vec2f(t * 0.05, -t * 0.04));
  var light = 0.62 * exp(-d1 * d1 * 5.0) + 0.4 * exp(-d2 * d2 * 8.0) + 0.45 * params.pointer.z * exp(-d3 * d3 * 16.0);
  light = sat(light * (0.7 + 0.6 * grain));
  let r = 3.5 * (0.14 + 0.7 * light);
  let lit = spot(c, r);
  let haze = exp(-length((uv - vec2f(0.5, 0.5)) * a) * 2.2) * 0.22;
  let face = mix(params.glow.rgb, params.ink.rgb, smoothstep(0.35, 0.95, light));
  return paint(params.ground.rgb + params.glow.rgb * haze * (0.6 + 0.4 * light) + face * lit * (0.12 + 0.88 * light));
}
`

// The shapes, as signed distances in a square from -1 to 1 with y up.
const screen = /* wgsl */ `
fn shape(i: i32, p: vec2f) -> f32 {
  var d = 0.0;
  switch i {
    case 0: { d = abs(length(p) - 0.56) - 0.13; }
    case 1: {
      d = min(sdBox(p - vec2f(-0.34, -0.32), vec2f(0.2, 0.38), 0.0), sdBox(p - vec2f(0.34, -0.06), vec2f(0.2, 0.64), 0.0));
    }
    case 2: {
      d = sdBox(p - vec2f(-0.6, -0.5), vec2f(0.14, 0.2), 0.0);
      d = min(d, sdBox(p - vec2f(-0.2, -0.36), vec2f(0.14, 0.34), 0.0));
      d = min(d, sdBox(p - vec2f(0.2, -0.2), vec2f(0.14, 0.5), 0.0));
      d = min(d, sdBox(p - vec2f(0.6, -0.02), vec2f(0.14, 0.68), 0.0));
    }
    case 3: {
      d = min(sdSeg(p, vec2f(-0.62, 0.02), vec2f(-0.18, -0.42)), sdSeg(p, vec2f(-0.18, -0.42), vec2f(0.64, 0.46))) - 0.14;
    }
    case 4: {
      let outer = (abs(p.x) + abs(p.y) - 0.74) * 0.70710678;
      let inner = (abs(p.x) + abs(p.y) - 0.36) * 0.70710678;
      d = max(outer, -inner);
    }
    case 5: {
      d = sdBox(p - vec2f(0.0, 0.48), vec2f(0.66, 0.1), 0.0);
      d = min(d, sdBox(p - vec2f(-0.14, 0.12), vec2f(0.52, 0.1), 0.0));
      d = min(d, sdBox(p - vec2f(0.08, -0.24), vec2f(0.58, 0.1), 0.0));
      d = min(d, sdBox(p - vec2f(-0.22, -0.6), vec2f(0.44, 0.1), 0.0));
    }
    case 6: {
      d = length(p - vec2f(-0.42, -0.56)) - 0.17;
      d = min(d, length(p - vec2f(-0.42, 0.56)) - 0.17);
      d = min(d, length(p - vec2f(0.44, 0.24)) - 0.17);
      d = min(d, sdSeg(p, vec2f(-0.42, -0.56), vec2f(-0.42, 0.56)) - 0.07);
      d = min(d, sdSeg(p, vec2f(-0.42, -0.2), vec2f(0.44, 0.24)) - 0.07);
    }
    case 7: {
      // A block of nine squares, the mark's grid.
      let tile = abs(fract((p + vec2f(1.0)) * 1.5) - vec2f(0.5));
      d = max(sdBox(p, vec2f(0.72, 0.72), 0.0), max(tile.x, tile.y) - 0.34);
    }
    default: {
      let left = sdSeg(p, vec2f(-0.78, -0.58), vec2f(-0.12, 0.5));
      let right = sdSeg(p, vec2f(-0.12, 0.5), vec2f(0.32, -0.08));
      let far = sdSeg(p, vec2f(0.18, 0.12), vec2f(0.78, -0.58));
      d = min(min(left, right), far) - 0.1;
    }
  }
  return d;
}

@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let t = time();
  let a = aspect();
  let c = cell(uv, 9.0);
  let q = (c.at - vec2f(0.5)) * a * 2.3;
  let p = vec2f(q.x, -q.y);
  let d = shape(i32(params.shape.x), p);
  let inside = 1.0 - smoothstep(-0.04, 0.06, d);
  let rim = exp(-abs(d) * 9.0);
  let across = (c.at.y - fract(t * 0.09) * 1.4 + 0.2) * 6.0;
  let sweep = exp(-across * across);
  let reach = length((c.at - params.pointer.xy) * a) * 5.0;
  let hand = exp(-reach * reach) * params.pointer.z;
  let amount = sat(inside * (0.82 + 0.18 * sweep) + rim * 0.25 + hand * 0.3);
  let r = 4.5 * (0.12 + 0.78 * amount);
  let lit = spot(c, r);
  let face = mix(mix(params.ground.rgb, params.ink.rgb, 0.16), params.ink.rgb, smoothstep(0.2, 0.7, amount));
  let shine = params.glow.rgb * (sweep * inside * 0.35 + hand * 0.4);
  return paint(mix(params.ground.rgb, face + shine, lit));
}
`

const mark = /* wgsl */ `
@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let t = time();
  let a = aspect();
  let c = cell(uv, 10.0);
  let centre = mix(vec2f(0.5, 0.5), params.pointer.xy, 0.18 * params.pointer.z);
  let q = (c.at - centre) * a;
  // Square rings, the mark's own shape, leaving the middle one after another.
  let ring = max(abs(q.x), abs(q.y));
  let wave = fract(ring * 3.2 - t * 0.16);
  let band = smoothstep(0.0, 0.08, wave) * (1.0 - smoothstep(0.1, 0.45, wave));
  let fade = exp(-ring * 2.1);
  let flicker = 0.75 + 0.25 * hash(floor(c.at * params.size.xy / scale() / 10.0) + vec2f(floor(t * 2.0)));
  let amount = sat(band * fade * flicker * 1.6 + fade * 0.1);
  let r = 4.6 * (0.1 + 0.8 * amount);
  let lit = spot(c, r);
  let face = mix(params.glow.rgb, params.ink.rgb, smoothstep(0.3, 0.9, amount));
  return paint(params.ground.rgb + face * lit * (0.18 + 0.82 * amount));
}
`

const backdrop = /* wgsl */ `
@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let t = time();
  let a = aspect();
  let push = (uv - params.pointer.xy) * a;
  let bend = exp(-dot(push, push) * 6.0) * params.pointer.z;
  let p = uv * a * 2.2 + vec2f(t * 0.03, t * 0.02) + push * bend * 0.35;
  let h = fbm(p) + 0.35 * fbm(p * 2.0 - vec2f(t * 0.05, 0.0));
  // Lines of equal height, about one CSS pixel wide at any size.
  let level = h * 9.0;
  let near = min(fract(level), 1.0 - fract(level));
  let line = 1.0 - smoothstep(0.0, fwidth(level) * scale() * 1.2, near);
  // Every fourth line is drawn in the ink, the rest in the glow.
  let major = select(0.0, 1.0, i32(floor(level + 0.5)) % 4 == 0);
  let fall = 1.0 - smoothstep(0.15, 1.05, uv.y);
  let ink = mix(params.glow.rgb, params.ink.rgb, major);
  return paint(mix(params.ground.rgb, ink, line * fall * (0.55 + 0.45 * major)));
}
`

const bodies: Record<Scene, string> = {glow, screen, mark, backdrop}

/** The whole shader for a scene: the shared code, then the scene's own. */
export const shaderFor = (scene: Scene) => `${shared}${bodies[scene]}`
