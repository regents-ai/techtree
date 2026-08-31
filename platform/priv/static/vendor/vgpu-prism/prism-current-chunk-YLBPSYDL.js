var s=[n("wall-material","Wall material / albedo","asset","srgb"),n("wall-normal","Wall normal","view","normal",[e("wall-material","unpack GB")]),n("wall-roughness","Wall roughness","view","scalar",[e("wall-material","unpack A")]),n("global-shadow","Ambient light blobs","asset","scalar"),n("prism-shadow","Prism cast shadow (analytic)","view","scalar"),n("prism-ao","Prism contact AO","asset","scalar"),n("raw-caustic","Raw spectral caustic","asset","hdr"),n("projected-caustic","Projected caustic","view","hdr",[e("raw-caustic","project onto wall")]),n("composed-wall","Composed wall","pass","hdr",[e("wall-material","base color"),e("wall-normal","shade normal"),e("wall-roughness","rough response"),e("global-shadow","multiply"),e("prism-shadow","draw core + penumbra"),e("prism-ao","multiply diffuse"),e("projected-caustic","add after AO")]),n("backdrop-hdr","Backdrop HDR","target","hdr",[e("composed-wall","Pass L0")]),n("front-glass","Front glass","pass","hdr",[e("backdrop-hdr","transmit / reflect")]),n("scene-hdr","Scene HDR","target","hdr",[e("backdrop-hdr","copy background"),e("front-glass","composite")]),n("final-output","Final output","target","srgb",[e("scene-hdr","tone map + sRGB")])],l=[n("dark-wall","Dark wall","pass","none"),n("dark-backdrop-hdr","Backdrop HDR","target","hdr",[e("dark-wall","base wall")]),n("dark-front-glass","Front glass","pass","hdr",[e("dark-backdrop-hdr","transmit / reflect")]),n("dark-scene-hdr","Scene HDR","target","hdr",[e("dark-backdrop-hdr","copy background"),e("dark-front-glass","composite")]),n("dark-bloom-0","Bloom 1/2","target","hdr",[e("dark-scene-hdr","threshold + blur")]),n("dark-bloom-1","Bloom 1/4","target","hdr",[e("dark-bloom-0","downsample + blur")]),n("dark-bloom-2","Bloom 1/8","target","hdr",[e("dark-bloom-1","downsample + blur")]),n("dark-bloom-composite","Bloom composite","target","hdr",[e("dark-bloom-0","near halo"),e("dark-bloom-1","medium halo"),e("dark-bloom-2","far halo")]),n("dark-particle-light","Particle light 1/16","target","hdr",[e("dark-scene-hdr","particle illumination")])];function e(t,r){return{source:t,operation:r}}function n(t,r,i,a,o=[]){return{id:t,label:r,kind:i,inputs:o,visualization:a}}var d={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/copy-linear.wgsl
// Raw resolved copy. The scene stays in linear HDR until presentation.

@group(0) @binding(0) var sceneTexture: texture_2d<f32>;

@fragment
fn fs_main(@builtin(position) position: vec4f) -> @location(0) vec4f {
  return textureLoad(sceneTexture, vec2i(position.xy), 0);
}
`};var f={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/glass-back.wgsl
// Inner/back interface of the prism.
//
// This is an environment-only background layer: it never reads the scene target.
// Premultiplied Fresnel blending supplies its reflection while the previously
// drawn wall and external light remain the transmitted component. Internal light
// is drawn afterwards. The front interface refracts this resolved composition.

 
  
  
  
  
  

@group(0) @binding(0) var<uniform> params: _vgsl_06a89b38__Glass;
@group(0) @binding(1) var studioEnvironment: texture_2d<f32>;
@group(0) @binding(2) var debugEnvironment: texture_2d<f32>;
@group(0) @binding(3) var environmentSampler: sampler;

struct _vgsl_f46c94db__VertexOut {
  @builtin(position) position: vec4f,
  @location(0) worldPosition: vec3f,
  @location(1) worldNormal: vec3f,
};

struct _vgsl_f46c94db__SurfaceHit {
  distance: f32,
  outwardNormal: vec3f,
};

struct _vgsl_f46c94db__ExitPath {
  position: vec3f,
  direction: vec3f,
  incidentDirection: vec3f,
  inwardNormal: vec3f,
  escaped: u32,
};

const _vgsl_f46c94db__NO_HIT: f32 = 100000.0;
const _vgsl_f46c94db__SURFACE_EPSILON: f32 = 0.0002;
const _vgsl_f46c94db__MAX_INTERNAL_BOUNCES: u32 = 3u;

fn _vgsl_f46c94db__sampleEnvironment(direction: vec3f) -> vec3f {
  return _vgsl_06a89b38__glassEnvironment(
    direction,
    params,
    studioEnvironment,
    debugEnvironment,
    environmentSampler,
    _vgsl_06a89b38__glassEnvironmentLod(direction, params),
  );
}

@vertex
fn vs_main(@location(0) position: vec3f, @location(1) normal: vec3f) -> _vgsl_f46c94db__VertexOut {
  var out: _vgsl_f46c94db__VertexOut;
  out.position = params.viewProjection * vec4f(position, 1.0);
  out.worldPosition = position;
  out.worldNormal = normal;
  return out;
}

fn _vgsl_f46c94db__planeHitDistance(origin: vec3f, direction: vec3f, plane: vec4f) -> f32 {
  let denominator = dot(plane.xyz, direction);
  if (denominator <= 0.00001) { return _vgsl_f46c94db__NO_HIT; }
  let distance = (plane.w - dot(plane.xyz, origin)) / denominator;
  return select(_vgsl_f46c94db__NO_HIT, distance, distance > _vgsl_f46c94db__SURFACE_EPSILON);
}

/** Nearest ideal prism plane reached by a ray already inside the glass. */
fn _vgsl_f46c94db__nextSurface(origin: vec3f, direction: vec3f) -> _vgsl_f46c94db__SurfaceHit {
  // Keep the old front -> back -> side comparison order for exact tie parity.
  let frontPlane = params.prismPlanes[3];
  let backPlane = params.prismPlanes[4];
  var nearest = _vgsl_f46c94db__planeHitDistance(origin, direction, frontPlane);
  var normal = frontPlane.xyz;

  let backDistance = _vgsl_f46c94db__planeHitDistance(origin, direction, backPlane);
  if (backDistance < nearest) {
    nearest = backDistance;
    normal = backPlane.xyz;
  }

  for (var index = 0u; index < 3u; index = index + 1u) {
    let plane = params.prismPlanes[index];
    let distance = _vgsl_f46c94db__planeHitDistance(origin, direction, plane);
    if (distance < nearest) {
      nearest = distance;
      normal = plane.xyz;
    }
  }
  return _vgsl_f46c94db__SurfaceHit(nearest, normal);
}

/**
 * Follow glass -> air transmission, continuing through real TIR bounces.
 *
 * The rasterized back face supplies the first interface normal. Subsequent hits
 * use the same five ideal planes as the outer shader and CPU tracer. Three
 * bounces are enough for this convex prism and match \`PRISM_MAX_INTERNAL_BOUNCES\`.
 */
fn _vgsl_f46c94db__traceExit(
  firstPosition: vec3f,
  firstDirection: vec3f,
  firstInwardNormal: vec3f,
) -> _vgsl_f46c94db__ExitPath {
  var position = firstPosition;
  var direction = firstDirection;
  var inwardNormal = firstInwardNormal;

  for (var bounce = 0u; bounce <= _vgsl_f46c94db__MAX_INTERNAL_BOUNCES; bounce = bounce + 1u) {
    let transmitted = refract(direction, inwardNormal, params.ior);
    if (length(transmitted) > 0.00001) {
      return _vgsl_f46c94db__ExitPath(position, normalize(transmitted), direction, inwardNormal, 1u);
    }

    direction = normalize(reflect(direction, inwardNormal));
    let hit = _vgsl_f46c94db__nextSurface(position + direction * _vgsl_f46c94db__SURFACE_EPSILON, direction);
    if (hit.distance >= 10.0) { break; }
    position = position + direction * (hit.distance + _vgsl_f46c94db__SURFACE_EPSILON);
    inwardNormal = -hit.outwardNormal;
  }

  return _vgsl_f46c94db__ExitPath(position, direction, direction, inwardNormal, 0u);
}

/**
 * An inner-face reflection remains inside the solid. Follow it to the next
 * interface (and through any subsequent TIR bounces) before using its direction
 * to sample the exterior studio environment.
 */
fn _vgsl_f46c94db__traceReflectedEnvironmentExit(
  surfacePosition: vec3f,
  incidentDirection: vec3f,
  inwardNormal: vec3f,
) -> _vgsl_f46c94db__ExitPath {
  let direction = normalize(reflect(incidentDirection, inwardNormal));
  let shiftedPosition = surfacePosition + direction * _vgsl_f46c94db__SURFACE_EPSILON;
  let hit = _vgsl_f46c94db__nextSurface(shiftedPosition, direction);
  if (hit.distance >= 10.0) {
    return _vgsl_f46c94db__ExitPath(surfacePosition, direction, direction, inwardNormal, 0u);
  }
  let position = shiftedPosition + direction * hit.distance;
  return _vgsl_f46c94db__traceExit(position, direction, -hit.outwardNormal);
}

@fragment
fn fs_main(in: _vgsl_f46c94db__VertexOut) -> @location(0) vec4f {
  let view = normalize(params.cameraPosition - in.worldPosition);
  let incident = -view;
  // Back-facing triangles expose their inward normal to the camera ray.
  let inwardNormal = -normalize(in.worldNormal);
  let exit = _vgsl_f46c94db__traceExit(in.worldPosition, incident, inwardNormal);

  let reflectedExit = _vgsl_f46c94db__traceReflectedEnvironmentExit(
    exit.position,
    exit.incidentDirection,
    exit.inwardNormal,
  );
  let reflectedFacing = clamp(
    -dot(reflectedExit.incidentDirection, reflectedExit.inwardNormal),
    0.0,
    1.0,
  );
  let reflectedExitTransmission = select(
    0.0,
    1.0 - _vgsl_06a89b38__dielectricFresnel(params.fresnelF0, reflectedFacing),
    reflectedExit.escaped != 0u,
  );
  let reflectedEnvironment = _vgsl_f46c94db__sampleEnvironment(reflectedExit.direction)
    * params.reflectionStrength
    * reflectedExitTransmission;
  let facing = clamp(-dot(exit.incidentDirection, exit.inwardNormal), 0.0, 1.0);
  let fresnel = _vgsl_06a89b38__dielectricFresnel(params.fresnelF0, facing);
  let reflectionWeight = select(
    1.0,
    fresnel,
    exit.escaped != 0u,
  );
  return vec4f(reflectedEnvironment * reflectionWeight, reflectionWeight);
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/glass-common.wgsl
// Uniform layout and optical helpers shared by the two glass interfaces.

      
     

struct _vgsl_06a89b38__Glass {
  viewProjection: mat4x4f,
  environmentRotation: mat4x4f,
  cameraPosition: vec3f,
  /** Beer-Lambert absorption per scene unit, in linear RGB. */
  absorption: vec3f,
  /** The cross-section, wound counter-clockwise, as \`types.ts\` derives it. */
  prismA: vec2f,
  prismB: vec2f,
  prismC: vec2f,
  environmentSize: vec2f,
  frontZ: f32,
  backZ: f32,
  ior: f32,
  reflectionStrength: f32,
  environmentExposure: f32,
  environmentDebug: f32,
  environmentTexelAngle: f32,
  /** Schlick reflectance at normal incidence, derived from \`ior\` on the CPU. */
  fresnelF0: f32,
  /** AB, BC, CA, front and back as \`(normal, offset)\`. */
  prismPlanes: array<vec4f, 5>,
}

fn _vgsl_06a89b38__glassEnvironment(
  direction: vec3f,
  params: _vgsl_06a89b38__Glass,
  studioEnvironment: texture_2d<f32>,
  debugEnvironment: texture_2d<f32>,
  environmentSampler: sampler,
  lod: f32,
) -> vec3f {
  let rotatedDirection = _vgsl_51c980fd__rotateEnvironmentDirection(
    direction,
    params.environmentRotation,
  );
  let maxLod = f32(textureNumLevels(studioEnvironment) - 1u);
  let safeLod = clamp(lod, 0.0, maxLod);
  if (params.environmentDebug > 0.5) {
    return _vgsl_757932e2__sample_env(
      debugEnvironment,
      environmentSampler,
      rotatedDirection,
      safeLod,
      params.environmentSize,
    ) * params.environmentExposure;
  }
  return _vgsl_757932e2__sample_env(
    studioEnvironment,
    environmentSampler,
    rotatedDirection,
    safeLod,
    params.environmentSize,
  ) * params.environmentExposure;
}

fn _vgsl_06a89b38__glassEnvironmentLod(direction: vec3f, params: _vgsl_06a89b38__Glass) -> f32 {
  return _vgsl_757932e2__env_lod(
    0.0,
    dpdx(direction),
    dpdy(direction),
    params.environmentTexelAngle,
  );
}

fn _vgsl_06a89b38__dielectricFresnel(f0: f32, facing: f32) -> f32 {
  let oneMinusFacing = 1.0 - clamp(facing, 0.0, 1.0);
  let squared = oneMinusFacing * oneMinusFacing;
  let fifth = squared * squared * oneMinusFacing;
  return f0 + (1.0 - f0) * fifth;
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-map-common.wgsl
const _vgsl_757932e2__PI: f32 = 3.141592653589793;

// Copied from the environment-map and transmission examples. Texture v=0 is
// the zenith and v=1 the nadir, so the direction-to-texture Y convention stays
// explicit and shared by every reflection/refraction path.
fn _vgsl_757932e2__equirect_uv(direction: vec3f) -> vec2f {
  let d = normalize(direction);
  return vec2f(
    atan2(d.z, d.x) / (2.0 * _vgsl_757932e2__PI) + 0.5,
    acos(clamp(d.y, -1.0, 1.0)) / _vgsl_757932e2__PI,
  );
}



/** Selects the prefiltered level matching the direction's angular footprint. */
fn _vgsl_757932e2__env_lod(
  cone: f32,
  ddx: vec3f,
  ddy: vec3f,
  texel_angle: f32,
) -> f32 {
  let footprint = max(length(ddx), length(ddy));
  return max(log2(max(cone, footprint) / texel_angle), 0.0);
}

/**
 * One texture fetch with the examples' smooth reconstruction. \`size\` is level
 * zero's extent and \`lod\` may be fractional for trilinear mip blending.
 */
fn _vgsl_757932e2__sample_env(
  env: texture_2d<f32>,
  env_samp: sampler,
  direction: vec3f,
  lod: f32,
  size: vec2f,
) -> vec3f {
  let level_size = max(size / exp2(lod), vec2f(2.0));
  let texel = _vgsl_757932e2__equirect_uv(direction) * level_size - 0.5;
  let corner = floor(texel);
  let f = fract(texel);
  let uv = (corner + f * f * (3.0 - 2.0 * f) + 0.5) / level_size;
  return textureSampleLevel(env, env_samp, uv, lod).rgb;
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment.wgsl
// The deliberately sparse studio the prism reflects.
//
// It started as \`glass-fractal\`'s nine-panel baked cubemap, but this shot only
// needs three intentional surfaces: a dark back-left wall, a cool right key and
// a neutral strip below the prism. Defining them here keeps the environment editable
// in one WGSL file; \`environment-bake.wgsl\` rasterizes it once into the same 360\xB0 HDR
// texture layout used by the environment-map and transmission examples.
//
// The final line replays the round trip the asset used to perform \u2014 encode to
// gamma 2.2, decode as sRGB \u2014 so the values a reflection reads here are the values
// a reflection reads there, including the small mismatch between those two curves.
//
// The glass has no material roughness cone, but its pixel footprint can still
// select a prefiltered mip when a reflection compresses this map on screen.

     



/** A back-left wall, soft center fill and dominant right key. */


/**
 * How much of \`panel\` a ray heading in \`direction\` sees: a rectangle projected
 * onto the sphere, feathered at its border so its edge does not alias in a
 * mirror-smooth reflection.
 */


/** Rotates a reflection into the studio's frame. Copied from \`glass-fractal\`. */
fn _vgsl_51c980fd__rotateEnvironmentDirection(direction: vec3f, rotation: mat4x4f) -> vec3f {
  return normalize((rotation * vec4f(direction, 0.0)).xyz);
}

/** Radiance arriving from \`direction\`, in linear RGB. */


// vgsl-module: /Users/sean/Documents/techtree-climb/techtree-ash/assets/node_modules/@vgpu/wgsl-std/src/color/index.wgsl





















`};var _={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/glass.wgsl
// Outer/front interface of the prism, based on \`glass-fractal\`'s
// \`hero-glass-transmission.wgsl\`.
//
// The material keeps that shader's dielectric response: one refracted scene
// lookup, one studio reflection, Beer-Lambert absorption over the distance
// travelled inside the solid, a thin-film tint that grows towards grazing
// angles, and an additive HDR highlight so a bright studio panel keeps its shape
// on a low-IOR frontal face. Geometric antialiasing belongs to the 4x MSAA target.
//
// Two things had to change, and both are simplifications. That example's glass is
// a shell around a fractal, so it approximates the interior with a nested
// tetrahedron and samples at the shell gap; this one is solid, so the refracted
// ray is followed to the face it actually leaves through \u2014 the intersection of
// the same three edges the CPU ray bundle refracts through, capped front and back.
// Environment reads use the same equirectangular texture path as the repository's
// environment-map and transmission examples.
//
// \`sceneTexture\` contains external light, the transparent back-side interface
// and internal light. The front shader follows air -> glass only as far as the
// first inner face and samples that resolved background there. The back-side
// material already owns glass -> air and TIR; tracing them again here would bend
// the same image twice.

 
  
  
  
  
  

/**
 * Returned instead of a distance when a plane cannot be the one a ray leaves
 * through. Large enough that \`min\` never picks it and the caller's \`< 10.0\` test
 * \u2014 the prism is under a unit across, so a real exit is always well inside that \u2014
 * reads it as a miss.
 */
const _vgsl_27d2e7e2__NO_EXIT: f32 = 100000.0;

@group(0) @binding(0) var<uniform> params: _vgsl_06a89b38__Glass;
@group(0) @binding(1) var sceneTexture: texture_2d<f32>;
@group(0) @binding(2) var sceneSampler: sampler;
@group(0) @binding(3) var studioEnvironment: texture_2d<f32>;
@group(0) @binding(4) var debugEnvironment: texture_2d<f32>;
@group(0) @binding(5) var environmentSampler: sampler;

struct _vgsl_27d2e7e2__VertexOut {
  @builtin(position) position: vec4f,
  @location(0) worldPosition: vec3f,
  @location(1) worldNormal: vec3f,
};

struct _vgsl_27d2e7e2__SurfaceHit {
  distance: f32,
  outwardNormal: vec3f,
};

struct _vgsl_27d2e7e2__InteriorHit {
  position: vec3f,
  distance: f32,
  valid: u32,
};

/** The mesh is built in world coordinates, so there is no model matrix to apply. */
@vertex
fn vs_main(@location(0) position: vec3f, @location(1) normal: vec3f) -> _vgsl_27d2e7e2__VertexOut {
  var out: _vgsl_27d2e7e2__VertexOut;
  out.position = params.viewProjection * vec4f(position, 1.0);
  out.worldPosition = position;
  out.worldNormal = normal;
  return out;
}

const _vgsl_27d2e7e2__SURFACE_EPSILON: f32 = 0.0002;

/** Distance to one outward plane \`dot(plane.xyz, p) = plane.w\`, or \`NO_EXIT\`. */
fn _vgsl_27d2e7e2__planeExitDistance(origin: vec3f, direction: vec3f, plane: vec4f) -> f32 {
  let denominator = dot(plane.xyz, direction);
  if (denominator <= 0.00001) { return _vgsl_27d2e7e2__NO_EXIT; }
  let distance = (plane.w - dot(plane.xyz, origin)) / denominator;
  return select(_vgsl_27d2e7e2__NO_EXIT, distance, distance > 0.0001);
}

/**
 * How far a ray inside the glass travels before it leaves.
 *
 * The prism is convex, so this is the nearest of its five bounding planes: three
 * from the cross-section's edges, rotated outward by the same rule \`optics.ts\`
 * uses, and the two caps the extrusion added.
 */
fn _vgsl_27d2e7e2__nextSurface(origin: vec3f, direction: vec3f) -> _vgsl_27d2e7e2__SurfaceHit {
  // Keep the old front -> back -> side comparison order. At a geometric tie,
  // strict \`<\` therefore selects the same surface as the previous derivation.
  let frontPlane = params.prismPlanes[3];
  let backPlane = params.prismPlanes[4];
  let frontDistance = _vgsl_27d2e7e2__planeExitDistance(origin, direction, frontPlane);
  let backDistance = _vgsl_27d2e7e2__planeExitDistance(origin, direction, backPlane);
  var nearest = frontDistance;
  var outwardNormal = frontPlane.xyz;
  if (backDistance < nearest) {
    nearest = backDistance;
    outwardNormal = backPlane.xyz;
  }
  for (var index = 0u; index < 3u; index = index + 1u) {
    let plane = params.prismPlanes[index];
    let distance = _vgsl_27d2e7e2__planeExitDistance(origin, direction, plane);
    if (distance < nearest) {
      nearest = distance;
      outwardNormal = plane.xyz;
    }
  }
  return _vgsl_27d2e7e2__SurfaceHit(nearest, outwardNormal);
}

fn _vgsl_27d2e7e2__traceInteriorHit(
  entryPosition: vec3f,
  insideDirection: vec3f,
) -> _vgsl_27d2e7e2__InteriorHit {
  let shiftedPosition = entryPosition + insideDirection * _vgsl_27d2e7e2__SURFACE_EPSILON;
  let hit = _vgsl_27d2e7e2__nextSurface(shiftedPosition, insideDirection);
  let valid = hit.distance < 10.0;
  let distance = select(0.0, hit.distance, valid);
  return _vgsl_27d2e7e2__InteriorHit(
    shiftedPosition + insideDirection * distance,
    distance,
    select(0u, 1u, valid),
  );
}

fn _vgsl_27d2e7e2__sampleEnvironment(direction: vec3f) -> vec3f {
  return _vgsl_06a89b38__glassEnvironment(
    direction,
    params,
    studioEnvironment,
    debugEnvironment,
    environmentSampler,
    _vgsl_06a89b38__glassEnvironmentLod(direction, params),
  );
}

fn _vgsl_27d2e7e2__projectToUv(point: vec3f) -> vec2f {
  let clip = params.viewProjection * vec4f(point, 1.0);
  let ndc = clip.xy / max(clip.w, 0.00001);
  return vec2f(ndc.x * 0.5 + 0.5, 0.5 - ndc.y * 0.5);
}

fn _vgsl_27d2e7e2__sampleBackground(uv: vec2f) -> vec3f {
  let resolution = max(vec2f(textureDimensions(sceneTexture)), vec2f(1.0));
  let halfTexel = 0.5 / resolution;
  let safeUv = clamp(uv, halfTexel, vec2f(1.0) - halfTexel);
  return textureSampleLevel(sceneTexture, sceneSampler, safeUv, 0.0).rgb;
}

@fragment
fn fs_main(in: _vgsl_27d2e7e2__VertexOut) -> @location(0) vec4f {
  let normal = normalize(in.worldNormal);
  let view = normalize(params.cameraPosition - in.worldPosition);
  let incident = -view;
  let facing = clamp(dot(view, normal), 0.0, 1.0);
  let reflectedEnvironment = _vgsl_27d2e7e2__sampleEnvironment(reflect(incident, normal));
  let fresnel = _vgsl_06a89b38__dielectricFresnel(params.fresnelF0, facing);
  let insideDirection = normalize(refract(incident, normal, 1.0 / params.ior));
  let interiorHit = _vgsl_27d2e7e2__traceInteriorHit(
    in.worldPosition,
    insideDirection,
  );
  let resolution = max(vec2f(textureDimensions(sceneTexture)), vec2f(1.0));
  let originalUv = in.position.xy / resolution;
  let refractedUv = select(
    originalUv,
    _vgsl_27d2e7e2__projectToUv(interiorHit.position),
    interiorHit.valid != 0u,
  );
  let background = _vgsl_27d2e7e2__sampleBackground(refractedUv);
  let transmittance = exp(-params.absorption * interiorHit.distance);
  let transmitted = select(
    vec3f(0.0),
    background * transmittance,
    interiorHit.valid != 0u,
  );
  let reflected = reflectedEnvironment * params.reflectionStrength;
  let grazingWeight = pow(1.0 - facing, 1.5);

  // Bright studio panels need a visible footprint even on a low-IOR frontal
  // face. Reuse the environment sample to isolate them; the darker room stays
  // governed by physical Fresnel.
  let environmentLuminance = dot(reflectedEnvironment, vec3f(0.2126, 0.7152, 0.0722));
  let studioPanelMask = smoothstep(0.5, 0.82, environmentLuminance);
  let physicalGlass = transmitted * (1.0 - fresnel) + reflected * fresnel;

  // An energy-conserving mix alone can make a white panel disappear when the
  // transmitted scene is also bright. Add the isolated panel in linear HDR so
  // its radiance survives until the final ACES pass, without another environment
  // sample or making the whole shell opaque.
  let studioPanelStrength = studioPanelMask
    * clamp(params.reflectionStrength * 0.4, 0.0, 0.7)
    * (0.65 + 0.35 * grazingWeight);
  let studioPanelHighlight = max(reflected * studioPanelStrength, vec3f(0.0));
  let finalGlass = max(physicalGlass, vec3f(0.0)) + studioPanelHighlight;
  return vec4f(finalGlass, 1.0);
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/glass-common.wgsl
// Uniform layout and optical helpers shared by the two glass interfaces.

      
     

struct _vgsl_06a89b38__Glass {
  viewProjection: mat4x4f,
  environmentRotation: mat4x4f,
  cameraPosition: vec3f,
  /** Beer-Lambert absorption per scene unit, in linear RGB. */
  absorption: vec3f,
  /** The cross-section, wound counter-clockwise, as \`types.ts\` derives it. */
  prismA: vec2f,
  prismB: vec2f,
  prismC: vec2f,
  environmentSize: vec2f,
  frontZ: f32,
  backZ: f32,
  ior: f32,
  reflectionStrength: f32,
  environmentExposure: f32,
  environmentDebug: f32,
  environmentTexelAngle: f32,
  /** Schlick reflectance at normal incidence, derived from \`ior\` on the CPU. */
  fresnelF0: f32,
  /** AB, BC, CA, front and back as \`(normal, offset)\`. */
  prismPlanes: array<vec4f, 5>,
}

fn _vgsl_06a89b38__glassEnvironment(
  direction: vec3f,
  params: _vgsl_06a89b38__Glass,
  studioEnvironment: texture_2d<f32>,
  debugEnvironment: texture_2d<f32>,
  environmentSampler: sampler,
  lod: f32,
) -> vec3f {
  let rotatedDirection = _vgsl_51c980fd__rotateEnvironmentDirection(
    direction,
    params.environmentRotation,
  );
  let maxLod = f32(textureNumLevels(studioEnvironment) - 1u);
  let safeLod = clamp(lod, 0.0, maxLod);
  if (params.environmentDebug > 0.5) {
    return _vgsl_757932e2__sample_env(
      debugEnvironment,
      environmentSampler,
      rotatedDirection,
      safeLod,
      params.environmentSize,
    ) * params.environmentExposure;
  }
  return _vgsl_757932e2__sample_env(
    studioEnvironment,
    environmentSampler,
    rotatedDirection,
    safeLod,
    params.environmentSize,
  ) * params.environmentExposure;
}

fn _vgsl_06a89b38__glassEnvironmentLod(direction: vec3f, params: _vgsl_06a89b38__Glass) -> f32 {
  return _vgsl_757932e2__env_lod(
    0.0,
    dpdx(direction),
    dpdy(direction),
    params.environmentTexelAngle,
  );
}

fn _vgsl_06a89b38__dielectricFresnel(f0: f32, facing: f32) -> f32 {
  let oneMinusFacing = 1.0 - clamp(facing, 0.0, 1.0);
  let squared = oneMinusFacing * oneMinusFacing;
  let fifth = squared * squared * oneMinusFacing;
  return f0 + (1.0 - f0) * fifth;
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-map-common.wgsl
const _vgsl_757932e2__PI: f32 = 3.141592653589793;

// Copied from the environment-map and transmission examples. Texture v=0 is
// the zenith and v=1 the nadir, so the direction-to-texture Y convention stays
// explicit and shared by every reflection/refraction path.
fn _vgsl_757932e2__equirect_uv(direction: vec3f) -> vec2f {
  let d = normalize(direction);
  return vec2f(
    atan2(d.z, d.x) / (2.0 * _vgsl_757932e2__PI) + 0.5,
    acos(clamp(d.y, -1.0, 1.0)) / _vgsl_757932e2__PI,
  );
}



/** Selects the prefiltered level matching the direction's angular footprint. */
fn _vgsl_757932e2__env_lod(
  cone: f32,
  ddx: vec3f,
  ddy: vec3f,
  texel_angle: f32,
) -> f32 {
  let footprint = max(length(ddx), length(ddy));
  return max(log2(max(cone, footprint) / texel_angle), 0.0);
}

/**
 * One texture fetch with the examples' smooth reconstruction. \`size\` is level
 * zero's extent and \`lod\` may be fractional for trilinear mip blending.
 */
fn _vgsl_757932e2__sample_env(
  env: texture_2d<f32>,
  env_samp: sampler,
  direction: vec3f,
  lod: f32,
  size: vec2f,
) -> vec3f {
  let level_size = max(size / exp2(lod), vec2f(2.0));
  let texel = _vgsl_757932e2__equirect_uv(direction) * level_size - 0.5;
  let corner = floor(texel);
  let f = fract(texel);
  let uv = (corner + f * f * (3.0 - 2.0 * f) + 0.5) / level_size;
  return textureSampleLevel(env, env_samp, uv, lod).rgb;
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment.wgsl
// The deliberately sparse studio the prism reflects.
//
// It started as \`glass-fractal\`'s nine-panel baked cubemap, but this shot only
// needs three intentional surfaces: a dark back-left wall, a cool right key and
// a neutral strip below the prism. Defining them here keeps the environment editable
// in one WGSL file; \`environment-bake.wgsl\` rasterizes it once into the same 360\xB0 HDR
// texture layout used by the environment-map and transmission examples.
//
// The final line replays the round trip the asset used to perform \u2014 encode to
// gamma 2.2, decode as sRGB \u2014 so the values a reflection reads here are the values
// a reflection reads there, including the small mismatch between those two curves.
//
// The glass has no material roughness cone, but its pixel footprint can still
// select a prefiltered mip when a reflection compresses this map on screen.

     



/** A back-left wall, soft center fill and dominant right key. */


/**
 * How much of \`panel\` a ray heading in \`direction\` sees: a rectangle projected
 * onto the sphere, feathered at its border so its edge does not alias in a
 * mirror-smooth reflection.
 */


/** Rotates a reflection into the studio's frame. Copied from \`glass-fractal\`. */
fn _vgsl_51c980fd__rotateEnvironmentDirection(direction: vec3f, rotation: mat4x4f) -> vec3f {
  return normalize((rotation * vec4f(direction, 0.0)).xyz);
}

/** Radiance arriving from \`direction\`, in linear RGB. */


// vgsl-module: /Users/sean/Documents/techtree-climb/techtree-ash/assets/node_modules/@vgpu/wgsl-std/src/color/index.wgsl





















`};var u={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/light-wireframe.wgsl
// Triangle topology of the generated light sheet. Every six vertices are one
// quad split into two triangles, so the diagonal is intentionally visible.

     

@group(0) @binding(0) var<uniform> scene: _vgsl_8a3a406a__Scene;

struct _vgsl_a6bd7dc2__VertexOut {
  @builtin(position) position: vec4f,
  @location(0) barycentric: vec3f,
  @location(1) @interpolate(flat, either) quadIndex: u32,
};

@vertex
fn vs_main(
  @builtin(vertex_index) index: u32,
  @location(0) position: vec2f,
) -> _vgsl_a6bd7dc2__VertexOut {
  var corners = array<vec3f, 3>(
    vec3f(1.0, 0.0, 0.0),
    vec3f(0.0, 1.0, 0.0),
    vec3f(0.0, 0.0, 1.0),
  );
  var out: _vgsl_a6bd7dc2__VertexOut;
  out.position = scene.viewProjection * vec4f(position, scene.lightPlaneZ, 1.0);
  out.barycentric = corners[index % 3u];
  out.quadIndex = index / 6u;
  return out;
}

@fragment
fn fs_main(in: _vgsl_a6bd7dc2__VertexOut) -> @location(0) vec4f {
  if in.quadIndex >= scene.lightWhiteQuads {
    let spectralQuad = in.quadIndex - scene.lightWhiteQuads;
    if spectralQuad < scene.lightInternalQuads {
      let ray = spectralQuad / scene.lightInternalSegments;
      let wavelength = ray / scene.lightBeamSlices;
      let profile = ray % scene.lightBeamSlices;
      // The full 128 x 24 internal grid is denser than a pixel.
      if wavelength % 8u != 0u || profile % 6u != 0u {
        discard;
      }
    } else {
      let outgoingCell = spectralQuad - scene.lightInternalQuads;
      let interval = outgoingCell / scene.lightBeamSlices;
      let profile = outgoingCell % scene.lightBeamSlices;
      if interval % 8u != 0u || profile % 6u != 0u {
        discard;
      }
    }
  }
  let closest = min(in.barycentric.x, min(in.barycentric.y, in.barycentric.z));
  let pixel = max(fwidth(closest), 1e-5);
  let line = 1.0 - smoothstep(pixel * 0.7, pixel * 1.7, closest);
  let alpha = line * 0.72;
  return vec4f(vec3f(0.08, 0.42, 0.46) * alpha, alpha);
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/scene.wgsl
// Uniforms shared by the wall and deterministic light-ribbon passes.

struct _vgsl_8a3a406a__Scene {
  viewProjection: mat4x4f,
  wallHalfExtent: vec2f,
  /** XY direction in which the white beam travels toward the prism. */
  inputBeamDirection: vec2f,
  /** User-selected sRGB wall color; the wall pass linearizes it before lighting. */
  wallColor: vec3f,
  /** 1 shows only the generated light over black. */
  causticOnly: u32,
  /** World-space depth of the emissive sheet between the glass interfaces. */
  lightPlaneZ: f32,
  /** Fixed layout metadata used to decimate the debug wireframe. */
  lightWhiteQuads: u32,
  lightBeamSlices: u32,
  lightInternalQuads: u32,
  lightInternalSegments: u32,
  /** User-controlled lateral and outgoing-distance falloff strengths. */
  lightOpacity: f32,
  lightEdgeFalloff: f32,
  rainbowFalloffRate: f32,
  rainbowFalloffPower: f32,
  /** Initial reveal aperture shared by white, internal, and spectral beams. */
  beamWidthReveal: f32,
}

/** Maps top-origin texture coordinates to the wall plane in world space. */

`};var h={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/wireframe.wgsl
struct _vgsl_a9484ca4__Params {
  viewProjection: mat4x4f,
}
@group(0) @binding(0) var<uniform> params: _vgsl_a9484ca4__Params;

@vertex
fn vs_main(
  @location(0) position: vec3f,
  @location(1) normal: vec3f,
) -> @builtin(position) vec4f {
  _ = normal;
  return params.viewProjection * vec4f(position, 1.0);
}

@fragment
fn fs_main() -> @location(0) vec4f {
  let alpha = 0.72;
  return vec4f(vec3f(0.24, 0.86, 1.0) * alpha, alpha);
}
`};export{s as a,l as b,d as c,f as d,_ as e,u as f,h as g};

