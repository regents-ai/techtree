/**
 * A quiet procedural field behind the crown.
 *
 * The base remains the selected site color. Sparse square cells borrow the
 * opposing theme color and fade out away from one diagonal band.
 */
export const backgroundWgsl = /* wgsl */ `
struct BackgroundParams {
  baseColor: vec4f,
  antiColor: vec4f,
  resolution: vec2f,
  intensity: f32,
};

@group(0) @binding(0) var<uniform> params: BackgroundParams;

fn hash21(point: vec2f) -> f32 {
  var value = fract(point * vec2f(0.1031, 0.1030));
  value = value + dot(value, value.yx + vec2f(33.33));
  return fract((value.x + value.y) * value.x);
}

fn composition(uv: vec2f) -> f32 {
  let diagonal = abs((uv.x * 0.82 + 0.12) - uv.y);
  return 1.0 - smoothstep(0.02, 0.48, diagonal);
}

fn squareField(uv: vec2f, aspect: f32) -> vec2f {
  let scale = 12.05;
  let plane = vec2f((uv.x - 0.5) * aspect + 0.5, uv.y) * scale;
  let cell = floor(plane);
  let local = fract(plane) - vec2f(0.5);
  let squareDistance = max(abs(local.x), abs(local.y));
  let body = 1.0 - smoothstep(0.36, 0.4, squareDistance);
  let edge = 1.0 - smoothstep(0.012, 0.032, abs(squareDistance - 0.38));
  let face = mix(0.76, 1.04, clamp((local.x - local.y) * 0.72 + 0.5, 0.0, 1.0));
  let occupancy = hash21(cell + vec2f(170.0, 70.0));
  return vec2f(body * step(occupancy, 0.58), mix(face, 1.18, edge));
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let safeResolution = max(params.resolution, vec2f(1.0));
  let aspect = safeResolution.x / safeResolution.y;
  let field = clamp(composition(uv), 0.0, 1.0);
  let square = squareField(uv, aspect);
  let density = smoothstep(0.04, 0.96, field);
  let squareAmount = square.x * density * params.intensity * square.y;
  let baseGradient = 1.0 + (uv.y - 0.5) * 0.022 + (uv.x - 0.5) * 0.008;
  let base = clamp(params.baseColor.rgb * baseGradient, vec3f(0.0), vec3f(1.0));
  let color = mix(base, params.antiColor.rgb, clamp(squareAmount, 0.0, 0.26));
  return vec4f(color, 1.0);
}
`
