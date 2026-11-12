/**
 * The theme switch, drawn by one fullscreen shader on a clear canvas.
 *
 * Under the glass lies a small procedural scene: the track, the icon of tiny
 * square blocks and the light that washes over both and spills onto the page.
 * The scene is a function, so the lens reads it wherever it likes: inside the
 * square, every pixel looks at the scene through the bevel, bent
 * inwards along the square's edge normal, each colour bent a little
 * differently, and blurred and clouded a little like frosted glass. The flat
 * middle is clear, so the blocks behind it stay crisp. The light strip then
 * rides the glass's edge, below it at night and above it by day.
 *
 * Each block is a square on the grid at rest, edges on whole pixels. In flight
 * it shrinks a little and turns as it tumbles, and the edge that faces the
 * light strip catches its light. The renderer works out each block's turn and
 * size once a frame and hands the blocks over sorted top to bottom, so a pixel
 * looks only at the blocks in its own band, and the lighting is worked out
 * once, for the block that covers it.
 *
 * The page under the canvas is a flat colour the shader is told, and the
 * lights it is handed already stand a fixed distance from it (light.ts), so the
 * same strip and glow read as boldly on the dark page as on the light one.
 *
 * Everything is premultiplied: the canvas is clear wherever nothing is drawn.
 */

export const PIXEL_SLOTS = 96

/** How much smaller a block is halfway through its flight; whole again when it lands. */
export const FLIGHT_SHRINK = 0.28

/**
 * Lays the blocks out as the shader reads them, four floats apiece: into
 * `place` each block's x and y and the cosine and sine of its turn, into
 * `look` its half side in cells and its share of day. They go top to bottom,
 * so a pixel can find the blocks in its own band. `blocks` holds x, y, turn
 * and share of day for each, `stride` floats apiece; `half` is a block's half
 * side at rest. Slots past the last block are left empty.
 */
export function packBlocks(
  blocks: Float32Array,
  stride: number,
  count: number,
  half: number,
  place: Float32Array,
  look: Float32Array,
): void {
  place.fill(0)
  look.fill(0)
  const order = Array.from({length: count}, (_, i) => i)
  order.sort((a, b) => blocks[a * stride + 1] - blocks[b * stride + 1])
  order.forEach((block, i) => {
    const from = block * stride
    const turn = blocks[from + 2]
    const day = blocks[from + 3]
    place.set([blocks[from], blocks[from + 1], Math.cos(turn), Math.sin(turn)], i * 4)
    look.set([half * (1 - FLIGHT_SHRINK * Math.sin(Math.PI * day)), day], i * 4)
  })
}

export const themeSwitchWgsl = /* wgsl */ `
struct Params {
  // Canvas size in pixels, canvas pixels per CSS pixel, and the knob's
  // position: 0 at night, 1 by day.
  size: vec2f,
  scale: f32,
  p: f32,
  // Track centre and half size, in canvas pixels.
  track: vec4f,
  // Lens centre, half size and the width of its bevel, in canvas pixels. The
  // lens and the track are square, as every frame on the page is.
  lens: vec4f,
  // x is unused; the strip's angle (radians clockwise from straight right) and
  // how much of the light is day's.
  shape: vec4f,
  // The icon's centre and one grid cell, in canvas pixels; w is unused.
  icon: vec4f,
  page: vec4f,
  ink: vec4f,
  // The strip's light at night and by day, as light on this page.
  night: vec4f,
  day: vec4f,
  // The icon's colours at night and by day, kept clear of the page.
  icon_night: vec4f,
  icon_day: vec4f,
  count: u32,
  // Each block: x and y in cells from the icon's centre, and the cosine and
  // sine of its turn. Sorted by y, top first.
  place: array<vec4f, ${PIXEL_SLOTS}>,
  // Each block: its half side in cells and its share of day (how far along its
  // flight it is); z and w are unused.
  look: array<vec4f, ${PIXEL_SLOTS}>,
}

@group(0) @binding(0) var<uniform> params: Params;

const PI: f32 = 3.14159265359;
const TAPS: i32 = 7;
// How far from its centre, in cells, any part of a block can lie.
const REACH: f32 = 0.75;

fn round_box(q: vec2f, half: vec2f, r: f32) -> f32 {
  let d = abs(q) - half + vec2f(r);
  return length(max(d, vec2f(0.0))) + min(max(d.x, d.y), 0.0) - r;
}

// The outward edge normal of the rounded box. Within r of the edge it is
// continuous: straight out along the sides, turning round the corners.
fn round_box_normal(q: vec2f, half: vec2f, r: f32) -> vec2f {
  let d = abs(q) - half + vec2f(r);
  let s = select(vec2f(-1.0), vec2f(1.0), q >= vec2f(0.0));
  if (d.x > 0.0 && d.y > 0.0) {
    return normalize(d) * s;
  }
  if (d.x > d.y) {
    return vec2f(s.x, 0.0);
  }
  return vec2f(0.0, s.y);
}

fn over(top: vec4f, under: vec4f) -> vec4f {
  return top + under * (1.0 - top.a);
}

fn light_colour() -> vec3f {
  return mix(params.night.rgb, params.day.rgb, params.shape.z);
}

fn wrap_pi(a: f32) -> f32 {
  return a - 2.0 * PI * floor((a + PI) / (2.0 * PI));
}

// How near the direction of q, seen from the lens centre, lies to the strip.
// The centre itself has no direction and counts as straight right, as in
// pixels.ts: the angle of no direction is not a number on every GPU, and the
// sun's middle block sits exactly there.
fn toward_strip(q: vec2f, spread: f32) -> f32 {
  let angle = select(0.0, atan2(q.y, q.x), dot(q, q) > 0.0);
  let off = wrap_pi(angle - params.shape.y);
  return exp(-(off * off) / (2.0 * spread * spread));
}

fn lens_edge(x: vec2f) -> f32 {
  return round_box(x - params.lens.xy, vec2f(params.lens.z), 0.0);
}

// The strip's glow: strongest along the glass edge beside the strip, fading
// out over the track and the page, and into the glass.
fn glow(x: vec2f) -> f32 {
  let q = x - params.lens.xy;
  let s = params.scale;
  let edge = lens_edge(x);
  let ring = abs(edge - 1.6 * s);
  let reach = select(5.5 * s, 3.5 * s, edge < 0.0);
  return 0.8 * toward_strip(q, 0.95) * exp(-ring / reach);
}

fn track(x: vec2f) -> vec4f {
  let s = params.scale;
  let q = x - params.track.xy;
  let d = round_box(q, params.track.zw, 0.0);
  let cover = clamp(0.5 - d, 0.0, 1.0);
  if (cover <= 0.0) {
    return vec4f(0.0);
  }
  let page = params.page.rgb;
  let ink = params.ink.rgb;
  var c = mix(page, ink, 0.1);
  // A shade under the top edge sets the track into the page.
  let top = q.y + params.track.w;
  c = mix(c, mix(page, ink, 0.2), 0.6 * (1.0 - smoothstep(0.0, 3.5 * s, top)));
  // Its outline.
  c = mix(c, mix(page, ink, 0.32), 1.0 - smoothstep(0.4 * s, 1.4 * s, -d));
  return vec4f(c * cover, cover);
}

// The icon's blocks, behind the glass and only there.
fn icon(x: vec2f) -> vec4f {
  let cell = params.icon.z;
  let q = (x - params.icon.xy) / cell;
  if (dot(q, q) > 64.0) {
    return vec4f(0.0);
  }
  // A block, turned however far, lies within REACH of its centre, so only the
  // blocks whose centres lie in this band can cover the point. The first is
  // found by halving; the rest follow it, in order down the picture.
  var lo = 0u;
  var hi = params.count;
  while (lo < hi) {
    let mid = (lo + hi) / 2u;
    if (params.place[mid].y < q.y - REACH) {
      lo = mid + 1u;
    } else {
      hi = mid;
    }
  }
  // The block that covers this point most.
  var cover = 0.0;
  var best = 0u;
  var near = vec2f(0.0);
  for (var i = lo; i < params.count; i = i + 1u) {
    let place = params.place[i];
    let off = q - place.xy;
    if (off.y < -REACH) {
      break;
    }
    if (abs(off.x) > REACH) {
      continue;
    }
    let local = vec2f(place.z * off.x + place.w * off.y, place.z * off.y - place.w * off.x);
    let half = params.look[i].x;
    let a = clamp(0.5 - round_box(local, vec2f(half), 0.06 * half) * cell, 0.0, 1.0);
    if (a > cover) {
      cover = a;
      best = i;
      near = local;
    }
  }
  if (cover <= 0.0) {
    return vec4f(0.0);
  }
  let place = params.place[best];
  let look = params.look[best];
  let half = look.x;
  let corner = 0.06 * half;
  let edge = round_box(near, vec2f(half), corner) * cell;
  // The side that faces the strip catches its light, more so the nearer the strip.
  let toward = vec2f(cos(params.shape.y), sin(params.shape.y));
  let side = round_box_normal(near, vec2f(half), corner);
  let facing = vec2f(place.z * side.x - place.w * side.y, place.w * side.x + place.z * side.y);
  let rim = 1.0 - smoothstep(0.0, max(1.0, 0.45 * half * cell), -edge);
  let lit = rim * max(dot(facing, toward), 0.0) * (0.45 + 0.55 * toward_strip(place.xy, 1.1));
  let shown = cover * clamp(-lens_edge(x), 0.0, 1.0);
  var colour = mix(params.icon_night.rgb, params.icon_day.rgb, look.y);
  colour = mix(colour, mix(light_colour(), vec3f(1.0), 0.6), 0.85 * lit);
  return vec4f(colour * shown, shown);
}

// Everything under the glass, at one point.
fn scene(x: vec2f) -> vec4f {
  var c = track(x);
  c = over(icon(x), c);
  let g = glow(x);
  c = over(vec4f(light_colour() * g, g), c);
  return c;
}

// A point of a small disc, spread by the golden angle.
fn tap(k: i32) -> vec2f {
  if (k == 0) {
    return vec2f(0.0);
  }
  let f = f32(k);
  let r = sqrt(f / f32(TAPS - 1));
  let a = f * 2.39996323;
  return vec2f(cos(a), sin(a)) * r;
}

fn glass(x: vec2f, edge: f32) -> vec4f {
  let s = params.scale;
  let q = x - params.lens.xy;
  let half = vec2f(params.lens.z);
  let inside = max(-edge, 0.0);
  let bevel = 0.85 * params.lens.w;
  // 1 at the rim, 0 on the flat middle.
  let t = 1.0 - clamp(inside / bevel, 0.0, 1.0);
  let n = round_box_normal(q, half, 0.0);
  let bend = t * t * 0.6 * bevel;
  // Frost lives in the bevel; the flat middle is clear, and looked through once.
  let frost = 1.7 * t * s;

  var c = vec4f(0.0);
  if (t <= 0.01) {
    c = scene(x);
  } else {
    var acc = vec4f(0.0);
    for (var k = 0; k < TAPS; k = k + 1) {
      let at = x + tap(k) * frost;
      // Red bends least and blue most.
      let r = scene(at - n * bend * 0.84);
      let g = scene(at - n * bend);
      let b = scene(at - n * bend * 1.18);
      acc = acc + vec4f(r.r, g.g, b.b, max(g.a, max(r.a, b.a)));
    }
    c = acc / f32(TAPS);
  }

  // Frosted glass is a little milky, more so towards its edge.
  let milk = 0.08 + 0.1 * t;
  c = over(vec4f(vec3f(milk), milk), c);
  // Light from the strip scatters into the glass.
  let scatter = 0.5 * toward_strip(q, 0.85) * exp(-inside / (0.5 * params.lens.z));
  c = over(vec4f(light_colour() * scatter, scatter), c);
  // A highlight where the bevel faces up and to the left.
  let spec = 0.5 * pow(max(dot(n, normalize(vec2f(-0.55, -0.85))), 0.0), 2.0) * t * t;
  c = over(vec4f(vec3f(spec), spec), c);
  // The edge itself.
  let line = 0.5 * (1.0 - smoothstep(0.2 * s, 1.3 * s, inside));
  c = over(vec4f(mix(params.page.rgb, params.ink.rgb, 0.5) * line, line), c);
  return c;
}

// The strip of light hugging the glass edge.
fn strip(x: vec2f, edge: f32) -> vec4f {
  let s = params.scale;
  let along = toward_strip(x - params.lens.xy, 0.55);
  let width = (0.4 + 1.1 * sqrt(along)) * s;
  let ring = abs(edge - 1.6 * s);
  let a = along * (1.0 - smoothstep(width * 0.5, width * 0.5 + 0.9 * s, ring));
  return vec4f(light_colour() * a, a);
}

@fragment fn fs_main(@builtin(position) position: vec4f) -> @location(0) vec4f {
  let x = position.xy;
  let s = params.scale;
  let edge = lens_edge(x);
  var c = vec4f(0.0);
  if (edge < -0.5) {
    c = glass(x, edge);
  } else if (edge < 1.0) {
    c = mix(scene(x), glass(x, edge), clamp(0.5 - edge, 0.0, 1.0));
  } else {
    c = scene(x);
  }
  c = over(strip(x, edge), c);
  // Light that reaches the canvas's edge fades out before it.
  let room = min(min(x.x, params.size.x - x.x), min(x.y, params.size.y - x.y));
  return c * smoothstep(0.0, 3.0 * s, room);
}
`
