/**
 * What a value card's panel is made of, and the shader code every panel shares.
 *
 * A panel is a grid of small glyphs (squares, pills, dots, slashes, diamonds,
 * plus signs, chevrons) lit from the card's own three-colour gradient. Each
 * panel is one file in `panels/`: its colours, its grid, the moment its still
 * frame shows, and the body of its fragment shader. `shaderFor` joins the body
 * to the shared code below.
 *
 * This file imports nothing, so the script that draws the still frames
 * (`stills.mjs`, beside it) reads the same colours and shaders the site does.
 * After changing a panel or anything here, draw the stills again:
 * `npm run stills:value-cards`.
 */

export type ValuePanel = {
  /** The gradient the glyphs are lit from: deep, main, bright. */
  readonly colours: readonly [string, string, string]
  /** One cell's width and height in CSS pixels, in a panel `ACROSS` wide. */
  readonly pitch: readonly [number, number]
  /** The second the still frame shows; the moving panel carries on from it. */
  readonly stillAt: number
  /**
   * The body of the fragment shader. It starts with the grid `g`, the pointer
   * `p` (x, y up, how present it is), the seconds `t` and the cell's place `x`,
   * `y` (0 to 1, y up), and ends by painting the cell with `emit`.
   */
  readonly body: string
}

/** The panel's ground. The card's stylesheet paints the same colour behind it. */
export const ground = "#08080a"

/**
 * Every panel is laid out as if it were this many CSS pixels across, and
 * scaled from there, so it is the same picture at any size and its still frame
 * always matches it.
 */
export const ACROSS = 340

/** A hex colour as linear-light channels, which is what the shaders mix. */
export const linear = (hex: string): [number, number, number, number] => {
  const channel = (at: number) => {
    const value = Number.parseInt(hex.slice(at, at + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return [channel(1), channel(3), channel(5), 1]
}

/** Every member of the panel's uniform struct, for a frame of this size at this second. */
export const uniforms = (
  panel: ValuePanel,
  width: number,
  height: number,
  seconds: number,
  pointer: readonly [number, number, number] = [0.5, 0.5, 0],
) => ({
  params: {
    ground: linear(ground),
    a: linear(panel.colours[0]),
    b: linear(panel.colours[1]),
    c: linear(panel.colours[2]),
    pointer: [...pointer, 0],
    size: [width, height, width / ACROSS, seconds],
  },
})

const shared = /* wgsl */ `
// One card's panel: a ground, a three-stop colour gradient (deep, main, bright),
// the pointer (x, y, how present it is) and the size (width, height, frame
// pixels for each pixel of the layout, seconds).
struct Params {
  ground: vec4f,
  a: vec4f,
  b: vec4f,
  c: vec4f,
  pointer: vec4f,
  size: vec4f,
}
@group(0) @binding(0) var<uniform> params: Params;

const TAU = 6.2831853;

fn sq(v: f32) -> f32 { return v * v; }
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
fn time() -> f32 { return params.size.w; }
// The pointer across the frame with y up, and how present it is.
fn pointer() -> vec3f { return vec3f(params.pointer.x, 1.0 - params.pointer.y, params.pointer.z); }
// Scales a 0..1 offset so a circle stays round in a panel of any shape.
fn aspect() -> vec2f { return params.size.xy / min(params.size.x, params.size.y); }

// Linear sRGB to OKLab and back (Björn Ottosson's matrices).
fn toOklab(c: vec3f) -> vec3f {
  let l = 0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b;
  let m = 0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b;
  let s = 0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b;
  let r = pow(max(vec3f(l, m, s), vec3f(0.0)), vec3f(1.0 / 3.0));
  return vec3f(
    0.2104542553 * r.x + 0.7936177850 * r.y - 0.0040720468 * r.z,
    1.9779984951 * r.x - 2.4285922050 * r.y + 0.4505937099 * r.z,
    0.0259040371 * r.x + 0.7827717662 * r.y - 0.8086757660 * r.z,
  );
}
fn fromOklab(lab: vec3f) -> vec3f {
  let l = lab.x + 0.3963377774 * lab.y + 0.2158037573 * lab.z;
  let m = lab.x - 0.1055613458 * lab.y - 0.0638541728 * lab.z;
  let s = lab.x - 0.0894841775 * lab.y - 1.2914855480 * lab.z;
  let c = vec3f(l * l * l, m * m * m, s * s * s);
  return vec3f(
    4.0767416621 * c.x - 3.3077115913 * c.y + 0.2309699292 * c.z,
    -1.2684380046 * c.x + 2.6097574011 * c.y - 0.3413193965 * c.z,
    -0.0041960863 * c.x - 0.7034186147 * c.y + 1.7076147010 * c.z,
  );
}
// The card's gradient, deep through main to bright, mixed in OKLab so it never
// dips through grey on the way.
fn ramp(t: f32) -> vec3f {
  let u = sat(t) * 2.0;
  if (u < 1.0) { return fromOklab(mix(toOklab(params.a.rgb), toOklab(params.b.rgb), u)); }
  return fromOklab(mix(toOklab(params.b.rgb), toOklab(params.c.rgb), u - 1.0));
}
// Linear light to the screen's sRGB.
fn toSrgb(c: vec3f) -> vec3f {
  return select(1.055 * pow(c, vec3f(1.0 / 2.4)) - vec3f(0.055), c * 12.92, c <= vec3f(0.0031308));
}

// Glyph shapes: signed distances in CSS pixels from the cell's centre, y up.
fn sdBox(p: vec2f, half: vec2f, r: f32) -> f32 {
  let q = abs(p) - half + vec2f(r);
  return length(max(q, vec2f(0.0))) + min(max(q.x, q.y), 0.0) - r;
}
fn sdPlus(p: vec2f, arm: f32, thick: f32) -> f32 {
  return min(sdBox(p, vec2f(arm, thick), 0.0), sdBox(p, vec2f(thick, arm), 0.0));
}
fn sdDiamond(p: vec2f, r: f32) -> f32 { return (abs(p.x) + abs(p.y) - r) * 0.70710678; }
// A slash leaning right (dir 1) or left (dir -1).
fn sdSlash(p: vec2f, len: f32, thick: f32, dir: f32) -> f32 {
  let along = (p.x + dir * p.y) * 0.70710678;
  let across = (p.y - dir * p.x) * 0.70710678;
  return sdBox(vec2f(along, across), vec2f(len, thick), thick);
}

// The distance to a line from a to b.
fn sdSeg(p: vec2f, a: vec2f, b: vec2f) -> f32 {
  let pa = p - a;
  let ba = b - a;
  return length(pa - ba * sat(dot(pa, ba) / dot(ba, ba)));
}
// A chevron pointing right (dir 1) or left (dir -1).
fn sdAngle(p: vec2f, size: f32, thick: f32, dir: f32) -> f32 {
  let q = vec2f(p.x * dir, abs(p.y));
  return sdSeg(q, vec2f(-size * 0.5, size), vec2f(size * 0.5, 0.0)) - thick;
}

struct Grid { id: vec2f, count: vec2f, at: vec2f, local: vec2f, mask: f32 }
// The grid of cells inside an inset frame: which cell this pixel is in, how many
// there are, the cell's centre as 0..1 across the frame (y up), and this pixel's
// offset from that centre in CSS pixels (y up).
fn grid(uv: vec2f, pitch: vec2f) -> Grid {
  let s = params.size.z;
  let inset = 10.0 * s;
  let area = params.size.xy - vec2f(inset * 2.0);
  let count = max(floor(area / (pitch * s)), vec2f(1.0));
  let room = area / count;
  let px = uv * params.size.xy - vec2f(inset);
  let id = clamp(floor(px / room), vec2f(0.0), count - vec2f(1.0));
  let off = (px - (id + vec2f(0.5)) * room) / s;
  let mask = step(0.0, px.x) * step(0.0, px.y) * step(px.x, area.x) * step(px.y, area.y);
  let at = vec2f((id.x + 0.5) / count.x, 1.0 - (id.y + 0.5) / count.y);
  return Grid(id, count, at, vec2f(off.x, -off.y), mask);
}
// Ordered dither across cells, by the 4x4 Bayer matrix: is this cell on, for a value 0..1.
fn dith(id: vec2f, v: f32) -> f32 {
  var bayer = array<f32, 16>(0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
  let at = vec2u(id) & vec2u(3u);
  return step((bayer[at.y * 4u + at.x] + 0.5) / 16.0, v);
}

// Paints one cell: an unlit glyph is a faint tint of the card's deep colour, a
// lit one takes its colour and glows a little into the gap.
fn emit(g: Grid, d: f32, colour: vec3f, amount: f32) -> vec4f {
  let s = params.size.z;
  let k = sat(amount);
  let cover = (1.0 - smoothstep(-0.6 / s, 0.6 / s, d)) * g.mask;
  let halo = exp(-max(d, 0.0) / 2.4) * (1.0 - cover) * g.mask;
  let ground = params.ground.rgb;
  let unlit = mix(ground, params.a.rgb, 0.2);
  let face = mix(ground, mix(unlit, colour, k), cover);
  return vec4f(toSrgb(clamp(face + colour * halo * k * k * 0.1, vec3f(0.0), vec3f(1.0))), 1.0);
}
`

/** The panel's whole shader: the shared code and the panel's own body. */
export const shaderFor = (panel: ValuePanel) => `${shared}
@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let g = grid(uv, vec2f(${panel.pitch[0].toFixed(1)}, ${panel.pitch[1].toFixed(1)}));
  let p = pointer();
  let t = time();
  let x = g.at.x;
  let y = g.at.y;
${panel.body}
}
`
