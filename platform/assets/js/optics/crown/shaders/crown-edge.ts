// Purpose-built edge glass for the Techtree crown. The visible mesh remains
// the exact reviewed 13-cell geometry; this material keeps the broad faces
// dark and gives each disconnected cube a narrow cool-white optical rail.

const shader = (passStrength: number) => ({
  version: 1,
  wgsl: `
struct Glass {
  viewProjection: mat4x4f,
  environmentRotation: mat4x4f,
  cameraPosition: vec3f,
  absorption: vec3f,
  cellHalfSize: vec2f,
  resolution: vec2f,
  frontZ: f32,
  backZ: f32,
  wallZ: f32,
  ior: f32,
  reflectionStrength: f32,
  frostRadius: f32,
  dispersion: f32,
  iridescenceStrength: f32,
  iridescenceFrequency: f32,
  environmentExposure: f32,
};

@group(0) @binding(0) var<uniform> params: Glass;
@group(0) @binding(1) var sceneTexture: texture_2d<f32>;
@group(0) @binding(2) var sceneSampler: sampler;

struct VertexOut {
  @builtin(position) position: vec4f,
  @location(0) worldPosition: vec3f,
  @location(1) worldNormal: vec3f,
  @location(2) @interpolate(flat) cellCenter: vec2f,
};

@vertex
fn vs_main(
  @location(0) position: vec3f,
  @location(1) normal: vec3f,
  @location(2) cell_center: vec2f,
) -> VertexOut {
  var out: VertexOut;
  out.position = params.viewProjection * vec4f(position, 1.0);
  out.worldPosition = position;
  out.worldNormal = normal;
  out.cellCenter = cell_center;
  return out;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4f {
  let normal = normalize(in.worldNormal);
  let view = normalize(params.cameraPosition - in.worldPosition);
  let facing = clamp(abs(dot(normal, view)), 0.0, 1.0);
  let frontness = pow(abs(normal.z), 8.0);
  let local = abs(in.worldPosition.xy - in.cellCenter) / max(params.cellHalfSize, vec2f(0.0001));
  let envelope = max(local.x, local.y);
  let corner = min(local.x, local.y);
  let depthCenter = (params.frontZ + params.backZ) * 0.5;
  let depthHalf = max((params.frontZ - params.backZ) * 0.5, 0.0001);
  let depthEnvelope = abs(in.worldPosition.z - depthCenter) / depthHalf;

  // Only the cap perimeter, the front/back edge of each sidewall, and the
  // vertical corner rails catch strongly. Broad side faces stay dark.
  let capRail = smoothstep(0.88, 0.995, envelope) * frontness;
  let depthRail = smoothstep(0.86, 0.995, depthEnvelope);
  let cornerRail = smoothstep(0.84, 0.99, corner);
  let bevelRail = max(depthRail, cornerRail) * (1.0 - frontness);
  let grazingRail = pow(1.0 - facing, 2.4) * 0.14;

  let reflected = reflect(-view, normal);
  let coolCard = pow(max(0.0, dot(reflected, normalize(vec3f(0.58, 0.34, 0.74)))), 30.0);
  let warmCard = pow(max(0.0, dot(reflected, normalize(vec3f(-0.48, -0.56, 0.68)))), 44.0);
  let rail = capRail * (0.40 + coolCard * 1.65)
    + bevelRail * (0.28 + coolCard * 1.25)
    + grazingRail;

  let safeResolution = max(params.resolution, vec2f(1.0));
  let uv = clamp(in.position.xy / safeResolution, vec2f(0.0), vec2f(1.0));
  let through = textureSampleLevel(sceneTexture, sceneSampler, uv, 0.0).rgb * 0.018;
  let cool = vec3f(0.62, 0.80, 1.0) * rail;
  let warm = vec3f(1.0, 0.58, 0.28) * warmCard * (capRail + bevelRail) * 0.18;
  return vec4f(through + (cool + warm) * ${passStrength.toFixed(2)}, 1.0);
}
`,
}) as const

export const crownEdgeBackWgsl = shader(0.10)
export const crownEdgeFrontWgsl = shader(0.74)
