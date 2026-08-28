/** Additive light sheet from the production VGPU prism pipeline. */
export default {
  version: 1,
  wgsl: `
struct LightParams {
  viewProjection: mat4x4f,
  lightPlaneZ: f32,
  edgeFalloff: f32,
  rainbowFalloffRate: f32,
  rainbowFalloffPower: f32,
  opacity: f32,
};

@group(0) @binding(0) var<uniform> params: LightParams;

struct VertexOut {
  @builtin(position) position: vec4f,
  @location(0) color: vec3f,
  @location(1) intensity: f32,
  @location(2) profile: f32,
  @location(3) travel: f32,
};

@vertex
fn vs_main(
  @location(0) position: vec2f,
  @location(1) color: vec3f,
  @location(2) intensity: f32,
  @location(3) profile: f32,
  @location(4) travel: f32,
) -> VertexOut {
  var out: VertexOut;
  out.position = params.viewProjection * vec4f(position, params.lightPlaneZ, 1.0);
  out.color = color;
  out.intensity = intensity;
  out.profile = profile;
  out.travel = travel;
  return out;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4f {
  let radius = abs(in.profile);
  let radialFalloff = exp(-params.edgeFalloff * radius * radius)
    * (1.0 - smoothstep(0.55, 1.0, radius));
  let attenuationDistance = max(params.rainbowFalloffRate, 0.0)
    * max(in.travel, 0.0);
  let longitudinalFalloff = 1.0 / pow(
    1.0 + attenuationDistance,
    max(params.rainbowFalloffPower, 0.0001),
  );
  return vec4f(
    in.color * in.intensity * radialFalloff * longitudinalFalloff
      * max(params.opacity, 0.0),
    0.0,
  );
}
`,
} as const
