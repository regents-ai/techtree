import{b as ne,c as ie,d as le,e as ce,f as fe,g as pe}from"./prism-current-chunk-YLBPSYDL.js";import{a as re,c as te,d as ae}from"./prism-current-chunk-3CVLT4UH.js";import{a as oe,b as U,c as se}from"./prism-current-chunk-35KT4CX3.js";import{g as me}from"./prism-current-chunk-YSQPETP6.js";import{a as y,b as O,c as j,d as Q,e as X,h as Z}from"./prism-current-chunk-5OW3BIRH.js";import{n as ee}from"./prism-current-chunk-4ND3A2V2.js";import{g as _,h as u,i as $,m as x,t as T,u as S,v as P,w as k,x as E}from"./prism-current-chunk-SQQEIMQF.js";import{A as Y,B as J,k as z,q as B}from"./prism-current-chunk-XRW3X5NJ.js";var C={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/bloom-blur-paired.wgsl
// One axis of the Gaussian blur with adjacent positive/negative taps paired
// through bilinear filtering. CPU-precomputed weights and fractional offsets
// reconstruct the same discrete kernel with fewer texture samples.

const _vgsl_01e4649c__MAX_PAIR_TAPS: u32 = 11u;

struct _vgsl_01e4649c__BlurParams {
  direction: vec2f,
  texelSize: vec2f,
  // x = center weight, y = active pair count.
  kernel: vec4f,
  weights0: vec4f,
  weights1: vec4f,
  weights2: vec4f,
  offsets0: vec4f,
  offsets1: vec4f,
  offsets2: vec4f,
}

@group(0) @binding(0) var sourceTexture: texture_2d<f32>;
@group(0) @binding(1) var sourceSampler: sampler;
@group(0) @binding(2) var<uniform> params: _vgsl_01e4649c__BlurParams;

fn _vgsl_01e4649c__pair_weight(index: u32) -> f32 {
  let values = array<f32, 12>(
    params.weights0.x,
    params.weights0.y,
    params.weights0.z,
    params.weights0.w,
    params.weights1.x,
    params.weights1.y,
    params.weights1.z,
    params.weights1.w,
    params.weights2.x,
    params.weights2.y,
    params.weights2.z,
    params.weights2.w,
  );
  return values[index];
}

fn _vgsl_01e4649c__pair_offset(index: u32) -> f32 {
  let values = array<f32, 12>(
    params.offsets0.x,
    params.offsets0.y,
    params.offsets0.z,
    params.offsets0.w,
    params.offsets1.x,
    params.offsets1.y,
    params.offsets1.z,
    params.offsets1.w,
    params.offsets2.x,
    params.offsets2.y,
    params.offsets2.z,
    params.offsets2.w,
  );
  return values[index];
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  var color = textureSampleLevel(sourceTexture, sourceSampler, uv, 0.0).rgb
    * params.kernel.x;
  let pairCount = min(_vgsl_01e4649c__MAX_PAIR_TAPS, u32(max(params.kernel.y, 0.0)));
  for (var pair = 0u; pair < _vgsl_01e4649c__MAX_PAIR_TAPS; pair = pair + 1u) {
    if (pair >= pairCount) { break; }
    let offset = params.direction * params.texelSize * _vgsl_01e4649c__pair_offset(pair);
    color += (
      textureSampleLevel(sourceTexture, sourceSampler, uv + offset, 0.0).rgb
      + textureSampleLevel(sourceTexture, sourceSampler, uv - offset, 0.0).rgb
    ) * _vgsl_01e4649c__pair_weight(pair);
  }
  return vec4f(max(color, vec3f(0.0)), 1.0);
}
`};var G={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/bloom-blur.wgsl
// One axis of an energy-normalized Gaussian blur. The same shader serves every
// pyramid level; coefficients beyond each level's kernel are zero-padded.

const _vgsl_da4f4919__MAX_KERNEL_TAPS: u32 = 22u;

struct _vgsl_da4f4919__BlurParams {
  direction: vec2f,
  texelSize: vec2f,
  tapCount: f32,
  coefficients0: vec4f,
  coefficients1: vec4f,
  coefficients2: vec4f,
  coefficients3: vec4f,
  coefficients4: vec4f,
  coefficients5: vec4f,
}

@group(0) @binding(0) var sourceTexture: texture_2d<f32>;
@group(0) @binding(1) var sourceSampler: sampler;
@group(0) @binding(2) var<uniform> params: _vgsl_da4f4919__BlurParams;

fn _vgsl_da4f4919__coefficient(index: u32) -> f32 {
  let values = array<f32, 24>(
    params.coefficients0.x,
    params.coefficients0.y,
    params.coefficients0.z,
    params.coefficients0.w,
    params.coefficients1.x,
    params.coefficients1.y,
    params.coefficients1.z,
    params.coefficients1.w,
    params.coefficients2.x,
    params.coefficients2.y,
    params.coefficients2.z,
    params.coefficients2.w,
    params.coefficients3.x,
    params.coefficients3.y,
    params.coefficients3.z,
    params.coefficients3.w,
    params.coefficients4.x,
    params.coefficients4.y,
    params.coefficients4.z,
    params.coefficients4.w,
    params.coefficients5.x,
    params.coefficients5.y,
    params.coefficients5.z,
    params.coefficients5.w,
  );
  return values[index];
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  var color = textureSampleLevel(sourceTexture, sourceSampler, uv, 0.0).rgb
    * _vgsl_da4f4919__coefficient(0u);
  let tapCount = min(_vgsl_da4f4919__MAX_KERNEL_TAPS, u32(max(params.tapCount, 1.0)));
  for (var tap = 1u; tap < _vgsl_da4f4919__MAX_KERNEL_TAPS; tap = tap + 1u) {
    if (tap >= tapCount) { break; }
    let offset = params.direction * params.texelSize * f32(tap);
    let weight = _vgsl_da4f4919__coefficient(tap);
    color += (
      textureSampleLevel(sourceTexture, sourceSampler, uv + offset, 0.0).rgb
      + textureSampleLevel(sourceTexture, sourceSampler, uv - offset, 0.0).rgb
    ) * weight;
  }
  return vec4f(max(color, vec3f(0.0)), 1.0);
}
`};var de={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/bloom-composite.wgsl
// Recombines the three detailed scales reserved for visible bloom. Increasing
// radius transfers weight toward the broadest of those scales without
// enlarging discrete taps.

struct _vgsl_c92c508d__CompositeParams {
  radius: f32,
  factors: vec4f,
}

@group(0) @binding(0) var level0Texture: texture_2d<f32>;
@group(0) @binding(1) var level1Texture: texture_2d<f32>;
@group(0) @binding(2) var level2Texture: texture_2d<f32>;
@group(0) @binding(3) var levelSampler: sampler;
@group(0) @binding(4) var<uniform> params: _vgsl_c92c508d__CompositeParams;

fn _vgsl_c92c508d__factor(index: u32) -> f32 {
  let nearToFar = array<f32, 4>(
    params.factors.x,
    params.factors.y,
    params.factors.z,
    params.factors.w,
  );
  return mix(
    nearToFar[index],
    nearToFar[2u - index],
    clamp(params.radius, 0.0, 1.0),
  );
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let weight0 = _vgsl_c92c508d__factor(0u);
  let weight1 = _vgsl_c92c508d__factor(1u);
  let weight2 = _vgsl_c92c508d__factor(2u);
  let color = (
    textureSampleLevel(level0Texture, levelSampler, uv, 0.0).rgb * weight0
    + textureSampleLevel(level1Texture, levelSampler, uv, 0.0).rgb * weight1
    + textureSampleLevel(level2Texture, levelSampler, uv, 0.0).rgb * weight2
  ) / max(weight0 + weight1 + weight2, 0.0001);
  return vec4f(max(color, vec3f(0.0)), 1.0);
}
`};var ue={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/bloom-extract.wgsl
// Softly isolates HDR highlights before the blur pyramid.

struct _vgsl_c0961198__ExtractParams {
  threshold: f32,
}

@group(0) @binding(0) var sourceTexture: texture_2d<f32>;
@group(0) @binding(1) var sourceSampler: sampler;
@group(0) @binding(2) var<uniform> params: _vgsl_c0961198__ExtractParams;

fn _vgsl_c0961198__brightContribution(color: vec3f) -> vec3f {
  let brightness = max(max(color.r, color.g), color.b);
  let threshold = max(params.threshold, 0.0);
  let knee = max(threshold * 0.5, 0.0001);
  var soft = clamp(brightness - threshold + knee, 0.0, 2.0 * knee);
  soft = soft * soft / (4.0 * knee + 0.0001);
  let contribution = max(brightness - threshold, soft)
    / max(brightness, 0.0001);
  return color * contribution;
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let color = textureSampleLevel(sourceTexture, sourceSampler, uv, 0.0).rgb;
  return vec4f(_vgsl_c0961198__brightContribution(max(color, vec3f(0.0))), 1.0);
}
`};var A=[{horizontal:"bilinear-pairs",vertical:"bilinear-pairs"},{horizontal:"raw",vertical:"bilinear-pairs"},{horizontal:"raw",vertical:"bilinear-pairs"},{horizontal:"bilinear-pairs",vertical:"bilinear-pairs"}],Be=12;function ve(e,n,r=Be){let o=Math.min(e.length,Math.max(1,Math.floor(n))),t=Math.ceil((o-1)/2);if(t>r)throw new RangeError(`Bloom paired kernel needs ${t} slots.`);let l=Array(r).fill(0),a=Array(r).fill(0);for(let i=0;i<t;i++){let c=1+i*2,s=c+1,p=e[c]??0,f=s<o?e[s]??0:0,m=p+f;l[i]=m,a[i]=m>0?(c*p+s*f)/m:c}return{centerWeight:e[0]??0,pairCount:t,weights:l,offsets:a}}var ge={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/dust.wgsl
// Sparse volumetric dust, composited after tone mapping.
//
// Every instance is a screen-facing quad whose deterministic index selects one
// of four physical-looking populations: mostly pinprick grains, some visible
// flakes, rare soft motes and exceptional out-of-focus bokeh. One broad,
// unthresholded light level reveals them independently of visible bloom.

      

struct _vgsl_22e9e4f0__DustParams {
  viewProjection: mat4x4f,
  fieldHalfExtent: vec2f,
  outputSize: vec2f,
  time: f32,
  cameraDistance: f32,
  lightPlaneZ: f32,
  prismA: vec2f,
  prismB: vec2f,
  prismC: vec2f,
  prismFrontZ: f32,
  revealProgress: f32,
}

@group(0) @binding(0) var<uniform> params: _vgsl_22e9e4f0__DustParams;
@group(0) @binding(1) var colorTexture: texture_2d<f32>;
@group(0) @binding(2) var lightTexture: texture_2d<f32>;
@group(0) @binding(3) var lightSampler: sampler;

struct _vgsl_22e9e4f0__VertexOut {
  @builtin(position) position: vec4f,
  @location(0) pointCoord: vec2f,
  @location(1) lightUv: vec2f,
  @location(2) @interpolate(flat, either) sparkle: f32,
  @location(3) @interpolate(flat, either) softness: f32,
  @location(4) @interpolate(flat, either) prismUvA: vec2f,
  @location(5) @interpolate(flat, either) prismUvB: vec2f,
  @location(6) @interpolate(flat, either) prismUvC: vec2f,
  @location(7) @interpolate(flat, either) opacity: f32,
};

const _vgsl_22e9e4f0__TAU: f32 = 6.28318530718;
const _vgsl_22e9e4f0__LIGHT_RESPONSE: f32 = 82.0;
const _vgsl_22e9e4f0__LIGHT_FALLOFF_POWER: f32 = 5.5;
const _vgsl_22e9e4f0__DUST_EXPOSURE: f32 = 0.72;

fn _vgsl_22e9e4f0__hash11(value: f32) -> f32 {
  return fract(sin(value * 127.1) * 43758.5453);
}

// Integer hashing keeps respawn positions stable for long-running sessions.
// Growing f32 inputs eventually lose the low bits that distinguish particles,
// especially before a trigonometric hash.
fn _vgsl_22e9e4f0__hashU32(value: u32) -> f32 {
  var mixed = value;
  mixed = mixed ^ (mixed >> 16u);
  mixed = mixed * 0x7feb352du;
  mixed = mixed ^ (mixed >> 15u);
  mixed = mixed * 0x846ca68bu;
  mixed = mixed ^ (mixed >> 16u);
  return f32(mixed & 0x00ffffffu) / 16777216.0;
}

fn _vgsl_22e9e4f0__quadCorner(vertexIndex: u32) -> vec2f {
  let cornerIndex = array<u32, 6>(0u, 1u, 2u, 2u, 1u, 3u)[vertexIndex % 6u];
  switch (cornerIndex) {
    case 0u: { return vec2f(-1.0, -1.0); }
    case 1u: { return vec2f( 1.0, -1.0); }
    case 2u: { return vec2f(-1.0,  1.0); }
    default: { return vec2f( 1.0,  1.0); }
  }
}

fn _vgsl_22e9e4f0__projectUv(point: vec3f) -> vec2f {
  let clip = params.viewProjection * vec4f(point, 1.0);
  let ndc = clip.xy / max(clip.w, 0.00001);
  return vec2f(ndc.x * 0.5 + 0.5, 0.5 - ndc.y * 0.5);
}

fn _vgsl_22e9e4f0__edgeSide(start: vec2f, end: vec2f, point: vec2f) -> f32 {
  let edge = end - start;
  let offset = point - start;
  return edge.x * offset.y - edge.y * offset.x;
}

fn _vgsl_22e9e4f0__insideTriangle(
  point: vec2f,
  a: vec2f,
  b: vec2f,
  c: vec2f,
) -> bool {
  let sideA = _vgsl_22e9e4f0__edgeSide(a, b, point);
  let sideB = _vgsl_22e9e4f0__edgeSide(b, c, point);
  let sideC = _vgsl_22e9e4f0__edgeSide(c, a, point);
  let hasNegative = sideA < 0.0 || sideB < 0.0 || sideC < 0.0;
  let hasPositive = sideA > 0.0 || sideB > 0.0 || sideC > 0.0;
  return !(hasNegative && hasPositive);
}

/** Diameter and profile softness for one progressively rarer dust population. */
fn _vgsl_22e9e4f0__dustAppearance(classSeed: f32, sizeSeed: f32) -> vec2f {
  if (classSeed < 0.82) {
    // Most of the field is stable, just-resolved airborne powder.
    return vec2f(mix(1.05, 1.75, sizeSeed * sizeSeed), 0.04);
  }
  if (classSeed < 0.95) {
    // A small number of flakes carry the readable sparkles.
    return vec2f(mix(1.8, 3.8, pow(sizeSeed, 1.4)), 0.18);
  }
  if (classSeed < 0.99) {
    // Rare larger motes are softer and much less energetic.
    return vec2f(mix(4.2, 9.0, pow(sizeSeed, 0.75)), 0.58);
  }
  if (classSeed < 0.996) {
    // Less than one percent becomes visible defocused bokeh.
    return vec2f(mix(12.0, 28.0, pow(sizeSeed, 0.8)), 1.0);
  }
  // Only a handful of instances become very large foreground bokeh. Their
  // opacity is derived from diameter below, so they remain atmospheric rather
  // than turning into opaque blobs.
  return vec2f(mix(32.0, 72.0, pow(sizeSeed, 0.8)), 1.0);
}

@vertex
fn vs_main(
  @builtin(vertex_index) vertexIndex: u32,
  @builtin(instance_index) instanceIndex: u32,
) -> _vgsl_22e9e4f0__VertexOut {
  let id = f32(instanceIndex) + 1.0;
  let seedLife = _vgsl_22e9e4f0__hash11(id * 19.127 + 71.0);
  let seedPhase = _vgsl_22e9e4f0__hash11(id * 23.417 + 83.0);
  let lifeDuration = mix(1.0, 7.0, seedLife);
  let lifeClock = params.time + seedPhase * lifeDuration;
  let lifeGeneration = floor(lifeClock / lifeDuration);
  let lifePhase = fract(lifeClock / lifeDuration);

  // A completed lifecycle creates a new particle rather than reviving the old
  // one. The position changes only at the zero-opacity seam between cycles.
  let spawnKey = (instanceIndex + 1u)
    ^ (u32(lifeGeneration) * 0x9e3779b9u);
  let seedX = _vgsl_22e9e4f0__hashU32(spawnKey ^ 0xa511e9b3u);
  let seedY = _vgsl_22e9e4f0__hashU32(spawnKey ^ 0x63d83595u);
  let seedZ = _vgsl_22e9e4f0__hashU32(spawnKey ^ 0x9e3779b9u);
  let seedDepth = _vgsl_22e9e4f0__hashU32(spawnKey ^ 0xc2b2ae35u);
  let seedSize = _vgsl_22e9e4f0__hash11(id * 7.731 + 31.0);
  let seedClass = _vgsl_22e9e4f0__hash11(id * 9.173 + 37.0);
  let seedEnergy = _vgsl_22e9e4f0__hash11(id * 11.917 + 43.0);
  let seedShape = _vgsl_22e9e4f0__hash11(id * 13.531 + 47.0);
  let seedAngle = _vgsl_22e9e4f0__hash11(id * 17.273 + 59.0);

  // A triangular depth distribution concentrates most motes around the same
  // plane as the light sheet. The small remaining spread still reads as volume,
  // without the strong parallax caused by particles close to the camera.
  let dustZ = params.lightPlaneZ + (seedZ + seedDepth - 1.0) * 0.14;
  var worldPosition = vec3f(
    (seedX * 2.0 - 1.0) * params.fieldHalfExtent.x,
    (seedY * 2.0 - 1.0) * params.fieldHalfExtent.y,
    dustZ,
  );
  // \`fieldHalfExtent\` describes the wall plane. Narrow it towards the camera
  // so every depth slice fills approximately the same visible frustum instead
  // of wasting most of the close particles outside the viewport.
  let depthScale = clamp(
    (params.cameraDistance - worldPosition.z) / max(params.cameraDistance, 0.001),
    0.08,
    1.0,
  );
  worldPosition.x *= depthScale;
  worldPosition.y *= depthScale;
  worldPosition += vec3f(
    sin(params.time * mix(0.09, 0.17, seedY) + seedZ * _vgsl_22e9e4f0__TAU) * mix(0.008, 0.035, seedSize),
    sin(params.time * mix(0.07, 0.14, seedZ) + seedX * _vgsl_22e9e4f0__TAU) * mix(0.01, 0.04, seedY),
    sin(params.time * mix(0.05, 0.1, seedX) + seedY * _vgsl_22e9e4f0__TAU) * mix(0.006, 0.025, seedZ),
  );

  let projected = params.viewProjection * vec4f(worldPosition, 1.0);
  let ndc = projected.xy / max(projected.w, 0.00001);
  let unsnappedUv = vec2f(ndc.x * 0.5 + 0.5, 0.5 - ndc.y * 0.5);
  // Anchor every billboard at a physical pixel centre. A one-pixel mote can
  // now move between pixels, but it cannot sit between them and alternate its
  // raster coverage from frame to frame.
  let pixelCenter = floor(
    unsnappedUv * max(params.outputSize, vec2f(1.0)),
  ) + vec2f(0.5);
  let lightUv = pixelCenter / max(params.outputSize, vec2f(1.0));
  let snappedNdc = vec2f(lightUv.x * 2.0 - 1.0, 1.0 - lightUv.y * 2.0);
  let corner = _vgsl_22e9e4f0__quadCorner(vertexIndex);
  let appearance = _vgsl_22e9e4f0__dustAppearance(seedClass, seedSize);
  let radiusPixels = appearance.x * 0.5;

  // Powder is not made of perfect discs. Tiny flakes get mild anisotropy and
  // arbitrary orientation; large bokeh stays circular like a defocused lens
  // footprint.
  let rawAspect = mix(0.68, 1.32, seedShape);
  let aspect = mix(rawAspect, 1.0, appearance.y);
  let angle = seedAngle * _vgsl_22e9e4f0__TAU;
  let axisX = vec2f(cos(angle), sin(angle));
  let axisY = vec2f(-axisX.y, axisX.x);
  let shapedCorner = axisX * corner.x * aspect
    + axisY * corner.y / max(aspect, 0.001);
  let clipOffset = shapedCorner * radiusPixels * 2.0
    / max(params.outputSize, vec2f(1.0));

  // A continuous inverse-size response is the governing rule: every larger
  // mote is dimmer than an equivalently oriented smaller one. Tiny grains keep
  // a useful energy floor so subpixel coverage cannot make them blink out.
  let opacityBySize = min(
    1.0,
    pow(1.5 / max(appearance.x, 1.5), 0.9),
  );
  let energyVariation = 0.3 + 1.1 * pow(seedEnergy, 3.0);
  // Orientation changes are almost imperceptible on the small population and
  // only slightly stronger on soft bokeh; motion, not flicker, carries life.
  let twinkleAmount = mix(0.015, 0.06, appearance.y);
  let twinkle = 1.0 + twinkleAmount * sin(
    params.time * mix(0.12, 0.28, seedShape) + seedAngle * _vgsl_22e9e4f0__TAU,
  );
  // Each mote has an independent, long visibility cycle. Both ends of the
  // cycle are zero, so wrapping is seamless; the slow smoothsteps make dust
  // materialise and dissolve instead of blinking. Random lifetimes keep the
  // field continuously changing without synchronising its particles.
  let fadeFraction = mix(0.14, 0.24, seedShape);
  let lifecycle = smoothstep(0.0, fadeFraction, lifePhase)
    * (1.0 - smoothstep(1.0 - fadeFraction, 1.0, lifePhase));

  var out: _vgsl_22e9e4f0__VertexOut;
  out.position = vec4f(
    (snappedNdc + clipOffset) * projected.w,
    projected.z,
    projected.w,
  );
  out.pointCoord = corner;
  out.lightUv = lightUv;
  out.sparkle = opacityBySize * energyVariation * twinkle;
  out.softness = appearance.y;
  out.prismUvA = _vgsl_22e9e4f0__projectUv(vec3f(params.prismA, params.prismFrontZ));
  out.prismUvB = _vgsl_22e9e4f0__projectUv(vec3f(params.prismB, params.prismFrontZ));
  out.prismUvC = _vgsl_22e9e4f0__projectUv(vec3f(params.prismC, params.prismFrontZ));
  out.opacity = lifecycle;
  return out;
}

@fragment
fn fs_main(in: _vgsl_22e9e4f0__VertexOut) -> @location(0) vec4f {
  let radiusSquared = dot(in.pointCoord, in.pointCoord);
  if (radiusSquared > 1.0) { discard; }
  let fragmentUv = in.position.xy / max(params.outputSize, vec2f(1.0));
  if (_vgsl_22e9e4f0__insideTriangle(
    fragmentUv,
    in.prismUvA,
    in.prismUvB,
    in.prismUvC,
  )) { discard; }

  let colorLight = max(textureSampleLevel(
    colorTexture,
    lightSampler,
    in.lightUv,
    0.0,
  ).rgb, vec3f(0.0));
  let light = max(textureSampleLevel(
    lightTexture,
    lightSampler,
    in.lightUv,
    0.0,
  ).rgb, vec3f(0.0));
  let brightness = max(max(light.r, light.g), light.b);
  if (all(light == vec3f(0.0))) { discard; }

  // No threshold is used: weak blurred samples fade continuously instead of
  // making a hard particle halo around the light volume.
  let lightResponse = 1.0
    - exp(-brightness * _vgsl_22e9e4f0__LIGHT_RESPONSE);
  let illumination = pow(
    clamp(lightResponse, 0.0, 1.0),
    _vgsl_22e9e4f0__LIGHT_FALLOFF_POWER,
  );

  let edgeFade = 1.0 - smoothstep(0.62, 1.0, radiusSquared);
  let core = exp(-radiusSquared * mix(6.5, 1.8, in.softness));
  let halo = exp(-radiusSquared * 1.25) * in.softness * 0.2;
  let radial = (core + halo) * edgeFade;
  let colorBrightness = max(max(colorLight.r, colorLight.g), colorLight.b);
  let hueSource = select(light, colorLight, colorBrightness > 0.0000001);
  let hueBrightness = max(max(hueSource.r, hueSource.g), hueSource.b);
  let normalizedLight = hueSource / max(hueBrightness, 0.000001);
  let lightColor = _vgsl_b50c27e4__linearToSrgb3(clamp(normalizedLight, vec3f(0.0), vec3f(1.0)));
  let energy = illumination * radial * in.sparkle * _vgsl_22e9e4f0__DUST_EXPOSURE;
  let displayEnergy = _vgsl_b50c27e4__linearToSrgb3(_vgsl_b50c27e4__tonemapAces(vec3f(energy))).r;
  let reveal = clamp(params.revealProgress, 0.0, 1.0);
  if (reveal <= 0.0) { discard; }
  return vec4f(lightColor * displayEnergy * in.opacity * reveal, 0.0);
}

// vgsl-module: /Users/sean/Documents/techtree-climb/techtree-ash/assets/node_modules/@vgpu/wgsl-std/src/color/index.wgsl










fn _vgsl_b50c27e4__linearToSrgb(value: f32) -> f32 {
  if (value <= 0.0031308) {
    return value * 12.92;
  }
  return 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

fn _vgsl_b50c27e4__linearToSrgb3(value: vec3f) -> vec3f {
  return vec3f(_vgsl_b50c27e4__linearToSrgb(value.r), _vgsl_b50c27e4__linearToSrgb(value.g), _vgsl_b50c27e4__linearToSrgb(value.b));
}



fn _vgsl_b50c27e4__tonemapAces(value: vec3f) -> vec3f {
  let a = 2.51;
  let b = 0.03;
  let c = 2.43;
  let d = 0.59;
  let e = 0.14;
  return clamp((value * (a * value + b)) / (value * (c * value + d) + e), vec3f(0.0), vec3f(1.0));
}




`};var _e={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/light.wgsl
// Additive rasterization of the deterministic CPU ray bundle as a world-space
// sheet halfway through the prism's depth.
//
// Inside the prism, every sampled wavelength is a finite-width strip spanning
// adjacent beam boundaries, so all colors overlap into white at entry and
// separate continuously as they travel. The outgoing fan connects neighbouring
// wavelengths. The fragment stage only applies intensity and beam falloff.

     
     
     
     

@group(0) @binding(0) var<uniform> scene: _vgsl_8a3a406a__Scene;

struct _vgsl_32cfe6f8__VertexOut {
  @builtin(position) position: vec4f,
  @location(0) color: vec3f,
  @location(1) profile: f32,
  @location(2) intensity: f32,
  @location(3) travel: f32,
  @location(4) revealProfile: f32,
};

@vertex
fn vs_main(
  @builtin(vertex_index) vertexIndex: u32,
  @location(0) position: vec2f,
  @location(3) rawIntensity: f32,
) -> _vgsl_32cfe6f8__VertexOut {
  var out: _vgsl_32cfe6f8__VertexOut;
  out.position = scene.viewProjection * vec4f(position, scene.lightPlaneZ, 1.0);
  let metadata = _vgsl_ad52036d__decodeLightVertex(
    vertexIndex,
    scene.lightWhiteQuads,
    scene.lightBeamSlices,
    scene.lightInternalQuads,
    scene.lightInternalSegments,
  );
  out.color = vec3f(1.0);
  // Empty quads carry a negative intensity sentinel and never fetch the LUT.
  if metadata.white == 0u && rawIntensity >= 0.0 {
    out.color = _vgsl_33cc580b__spectralSample(metadata.spectralIndex).rgb;
  }
  out.profile = metadata.profile;
  out.intensity = max(rawIntensity, 0.0);
  out.travel = metadata.travel;
  out.revealProfile = metadata.revealProfile;
  return out;
}

@fragment
fn fs_main(in: _vgsl_32cfe6f8__VertexOut) -> @location(0) vec4f {
  let radius = abs(in.profile);
  let radialFalloff = exp(-scene.lightEdgeFalloff * radius * radius)
    * (1.0 - smoothstep(0.55, 1.0, radius));
  let widthReveal = _vgsl_2bcabc90__beamWidthReveal(
    in.revealProfile,
    scene.beamWidthReveal,
  );
  // Geometric dilution falls quickly near the effective source, then leaves a
  // progressively softer tail. Unlike the previous exponential plus cutoff,
  // this never introduces a second abrupt fade near the wall.
  let attenuationDistance = max(scene.rainbowFalloffRate, 0.0)
    * max(in.travel, 0.0);
  let longitudinalFalloff = 1.0 / pow(
    1.0 + attenuationDistance,
    max(scene.rainbowFalloffPower, 0.0001),
  );
  return vec4f(
    in.color * in.intensity * radialFalloff * widthReveal * longitudinalFalloff
      * max(scene.lightOpacity, 0.0),
    0.0,
  );
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


// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/materials/shared/beam-reveal.wgsl
/**
 * Opens a finite-width ray bundle from its center line. The uniform branches
 * keep the settled frame exact and avoid leaving a residual line at zero.
 */
fn _vgsl_2bcabc90__beamWidthReveal(profile: f32, progress: f32) -> f32 {
  let reveal = clamp(progress, 0.0, 1.0);
  if reveal <= 0.0 {
    return 0.0;
  }
  if reveal >= 1.0 {
    return 1.0;
  }
  // Outgoing spectral cells carry one flat profile per beam slice, so the
  // minimum feather lets adjacent rainbow slices join without visible steps.
  let antialias = max(fwidth(profile) * 1.5, 0.04);
  return 1.0 - smoothstep(
    max(reveal - antialias, 0.0),
    min(reveal + antialias, 1.0),
    abs(profile),
  );
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/materials/shared/light-vertex.wgsl
// Static light-ribbon attributes decoded from the retained global vertex
// index. The CPU uploads only position.xy and intensity; vertex counts and
// first-vertex ranges remain identical to the original interleaved mesh.

const _vgsl_ad52036d__QUAD_UPPER = array<u32, 6>(0u, 1u, 1u, 0u, 1u, 0u);
const _vgsl_ad52036d__QUAD_END_TRAVEL = array<f32, 6>(0.0, 0.0, 1.0, 0.0, 1.0, 1.0);

// Exact Float32 results of \`-1 + 2 * boundary / 24\` from the CPU mesh.
const _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES = array<f32, 25>(
  -1.0, -0.9166666865348816, -0.8333333134651184, -0.75,
  -0.6666666865348816, -0.5833333134651184, -0.5,
  -0.4166666567325592, -0.3333333432674408, -0.25,
  -0.1666666716337204, -0.0833333358168602, 0.0,
  0.0833333358168602, 0.1666666716337204, 0.25,
  0.3333333432674408, 0.4166666567325592, 0.5,
  0.5833333134651184, 0.6666666865348816, 0.75,
  0.8333333134651184, 0.9166666865348816, 1.0,
);

struct _vgsl_ad52036d__LightVertexMetadata {
  profile: f32,
  travel: f32,
  spectralIndex: u32,
  white: u32,
  revealProfile: f32,
}

fn _vgsl_ad52036d__decodeLightVertex(
  vertexIndex: u32,
  whiteQuads: u32,
  beamSlices: u32,
  internalQuads: u32,
  internalSegments: u32,
) -> _vgsl_ad52036d__LightVertexMetadata {
  let quad = vertexIndex / 6u;
  let corner = vertexIndex % 6u;
  let upper = _vgsl_ad52036d__QUAD_UPPER[corner];

  if quad < whiteQuads {
    return _vgsl_ad52036d__LightVertexMetadata(
      _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES[quad + upper],
      0.0,
      0u,
      1u,
      _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES[quad + upper],
    );
  }

  let spectralQuad = quad - whiteQuads;
  if spectralQuad < internalQuads {
    let quadsPerWavelength = beamSlices * internalSegments;
    let spectralIndex = spectralQuad / quadsPerWavelength;
    let slice = (spectralQuad % quadsPerWavelength) / internalSegments;
    return _vgsl_ad52036d__LightVertexMetadata(
      _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES[slice + upper],
      0.0,
      spectralIndex,
      0u,
      _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES[slice + upper],
    );
  }

  let outgoingQuad = spectralQuad - internalQuads;
  let outgoingSlice = outgoingQuad % beamSlices;
  return _vgsl_ad52036d__LightVertexMetadata(
    0.0,
    _vgsl_ad52036d__QUAD_END_TRAVEL[corner],
    outgoingQuad / beamSlices + upper,
    0u,
    0.5 * (
      _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES[outgoingSlice]
        + _vgsl_ad52036d__BEAM_BOUNDARY_PROFILES[outgoingSlice + 1u]
    ),
  );
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/materials/shared/spectral.wgsl
// Generated Float32 checkpoint of \`wavelengthToBeamRgb\` for the fixed
// 128-sample light mesh. Alpha retains the exact uploaded wavelength so the
// projected caustic preserves its former interpolation and profile lookup.
const _vgsl_33cc580b__SPECTRAL_LUT = array<vec4f, 128>(
  vec4f(0.0009276652708649635, 0.0, 0.01045608427375555, 400.0),
  vec4f(0.001637425273656845, 0.0, 0.012818877585232258, 402.3622131347656),
  vec4f(0.002453181426972151, 0.0, 0.015664873644709587, 404.7243957519531),
  vec4f(0.0033296814654022455, 0.0, 0.01908119209110737, 407.08660888671875),
  vec4f(0.004219147376716137, 0.0, 0.023167869076132774, 409.4488220214844),
  vec4f(0.005016450770199299, 0.0, 0.02767137996852398, 411.81103515625),
  vec4f(0.005726693198084831, 0.0, 0.03282611444592476, 414.1732177734375),
  vec4f(0.0063720447942614555, 0.0, 0.038834281265735626, 416.5354309082031),
  vec4f(0.00697797816246748, 0.0, 0.045814741402864456, 418.89764404296875),
  vec4f(0.007500954903662205, 0.0, 0.05327555537223816, 421.2598571777344),
  vec4f(0.007993110455572605, 0.0, 0.06114164739847183, 423.6220397949219),
  vec4f(0.008597604930400848, 0.0, 0.06995505839586258, 425.9842529296875),
  vec4f(0.00939855445176363, 0.0, 0.07979211956262589, 428.3464660644531),
  vec4f(0.010702796280384064, 0.0, 0.09255003929138184, 430.7086486816406),
  vec4f(0.013043251819908619, 0.0, 0.11191345751285553, 433.07086181640625),
  vec4f(0.016207652166485786, 0.0, 0.13458603620529175, 435.4330749511719),
  vec4f(0.02036980912089348, 0.0, 0.16097605228424072, 437.7952880859375),
  vec4f(0.02453680895268917, 0.0, 0.19133983552455902, 440.157470703125),
  vec4f(0.02762519381940365, 0.0, 0.223611980676651, 442.5196838378906),
  vec4f(0.030124200507998466, 0.0, 0.2601846754550934, 444.88189697265625),
  vec4f(0.03208434209227562, 0.0, 0.30138635635375977, 447.24407958984375),
  vec4f(0.03319524973630905, 0.0, 0.34751778841018677, 449.6062927246094),
  vec4f(0.032500505447387695, 0.0, 0.39206168055534363, 451.968505859375),
  vec4f(0.030062656849622726, 0.0, 0.43913084268569946, 454.3307189941406),
  vec4f(0.02549462579190731, 0.0, 0.4899933636188507, 456.6929016113281),
  vec4f(0.01816663332283497, 0.0, 0.5446479916572571, 459.05511474609375),
  vec4f(0.007985850796103477, 0.0, 0.6007148623466492, 461.4173278808594),
  vec4f(0.0, 0.004250565078109503, 0.6583616137504578, 463.779541015625),
  vec4f(0.0, 0.01778329908847809, 0.7188571095466614, 466.1417236328125),
  vec4f(0.0, 0.03469391539692879, 0.7820181250572205, 468.5039367675781),
  vec4f(0.0, 0.056442294269800186, 0.8496572971343994, 470.86614990234375),
  vec4f(0.0, 0.08500456809997559, 0.9234520792961121, 473.22833251953125),
  vec4f(0.0, 0.12223964929580688, 0.9998624920845032, 475.5905456542969),
  vec4f(0.0, 0.17022110521793365, 1.0786155462265015, 477.9527587890625),
  vec4f(0.0, 0.23043279349803925, 1.1576675176620483, 480.3149719238281),
  vec4f(0.0, 0.3013739287853241, 1.2265548706054688, 482.6771545410156),
  vec4f(0.0, 0.3849429190158844, 1.2962673902511597, 485.03936767578125),
  vec4f(0.0, 0.48050656914711, 1.3667092323303223, 487.4015808105469),
  vec4f(0.0, 0.5868926048278809, 1.4377244710922241, 489.7637939453125),
  vec4f(0.0, 0.6764097213745117, 1.4525021314620972, 492.1259765625),
  vec4f(0.0, 0.7141680717468262, 1.364959478378296, 494.4881896972656),
  vec4f(0.0, 0.7513074278831482, 1.2944350242614746, 496.85040283203125),
  vec4f(0.0, 0.7872423529624939, 1.235427737236023, 499.21258544921875),
  vec4f(0.0, 0.820360541343689, 1.182457685470581, 501.5747985839844),
  vec4f(0.0, 0.8506588339805603, 1.1340235471725464, 503.93701171875),
  vec4f(0.0, 0.8781104683876038, 1.0891823768615723, 506.2992248535156),
  vec4f(0.0, 0.9023182392120361, 1.0468008518218994, 508.6614074707031),
  vec4f(0.0, 0.9227785468101501, 1.0058692693710327, 511.02362060546875),
  vec4f(0.0, 0.9395197033882141, 0.9660518169403076, 513.3858032226562),
  vec4f(0.0, 0.9531605243682861, 0.9274855852127075, 515.748046875),
  vec4f(0.0, 0.9640098214149475, 0.889782726764679, 518.1102294921875),
  vec4f(0.0, 0.972785234451294, 0.8527419567108154, 520.472412109375),
  vec4f(0.0, 0.9806240200996399, 0.8162780404090881, 522.8346557617188),
  vec4f(0.0, 0.9864705204963684, 0.7782756686210632, 525.1968383789062),
  vec4f(0.0, 0.9907678961753845, 0.7377868294715881, 527.55908203125),
  vec4f(0.0, 0.9938809871673584, 0.6935604810714722, 529.9212646484375),
  vec4f(0.0, 0.9953005313873291, 0.6437165141105652, 532.283447265625),
  vec4f(0.0, 0.9963739514350891, 0.5885664820671082, 534.6456909179688),
  vec4f(0.0, 0.9972034096717834, 0.5267602801322937, 537.0078735351562),
  vec4f(0.0, 0.9978204369544983, 0.45638740062713623, 539.3700561523438),
  vec4f(0.0, 0.9985225200653076, 0.3750465512275696, 541.7322998046875),
  vec4f(0.0, 0.9991394281387329, 0.27924177050590515, 544.094482421875),
  vec4f(0.0, 0.9995918869972229, 0.16423428058624268, 546.4566650390625),
  vec4f(0.0, 0.9998977184295654, 0.023272335529327393, 548.8189086914062),
  vec4f(0.07590825855731964, 0.9998574256896973, 0.0, 551.1810913085938),
  vec4f(0.172451451420784, 0.999469518661499, 0.0, 553.5433349609375),
  vec4f(0.2783505618572235, 0.9989391565322876, 0.0, 555.905517578125),
  vec4f(0.3948717415332794, 0.9982571601867676, 0.0, 558.2677001953125),
  vec4f(0.5234453082084656, 0.9974250197410583, 0.0, 560.6299438476562),
  vec4f(0.6656978130340576, 0.996455729007721, 0.0, 562.9921264648438),
  vec4f(0.8234602808952332, 0.9952938556671143, 0.0, 565.3543090820312),
  vec4f(0.9988605976104736, 0.9939171075820923, 0.0, 567.716552734375),
  vec4f(1.177673578262329, 0.9781429767608643, 0.0, 570.0787353515625),
  vec4f(1.1760860681533813, 0.8224363327026367, 0.0, 572.44091796875),
  vec4f(1.1741501092910767, 0.6952834129333496, 0.0, 574.8031616210938),
  vec4f(1.171817421913147, 0.5896721482276917, 0.0, 577.1653442382812),
  vec4f(1.169029712677002, 0.50070720911026, 0.0, 579.527587890625),
  vec4f(1.1640989780426025, 0.4242915213108063, 0.0, 581.8897705078125),
  vec4f(1.157752513885498, 0.35835379362106323, 0.0, 584.251953125),
  vec4f(1.1501755714416504, 0.3011019229888916, 0.0, 586.6141967773438),
  vec4f(1.1411696672439575, 0.2510553002357483, 0.0, 588.9763793945312),
  vec4f(1.1330195665359497, 0.20752595365047455, 0.0, 591.3385620117188),
  vec4f(1.125596284866333, 0.16939160227775574, 0.0, 593.7008056640625),
  vec4f(1.1170347929000854, 0.13555681705474854, 0.0, 596.06298828125),
  vec4f(1.1071977615356445, 0.10544843226671219, 0.0, 598.4251708984375),
  vec4f(1.0955544710159302, 0.07866207510232925, 0.0, 600.7874145507812),
  vec4f(1.081459641456604, 0.05545935034751892, 0.0, 603.1495971679688),
  vec4f(1.0654693841934204, 0.03556278720498085, 0.0, 605.5118408203125),
  vec4f(1.047431468963623, 0.018554607406258583, 0.0, 607.8740234375),
  vec4f(1.0270756483078003, 0.004095226991921663, 0.0, 610.2362060546875),
  vec4f(1.003137469291687, 0.0, 0.018001360818743706, 612.5984497070312),
  vec4f(0.9766530394554138, 0.0, 0.0400092750787735, 614.9606323242188),
  vec4f(0.9475923776626587, 0.0, 0.05749110132455826, 617.3228149414062),
  vec4f(0.9159792065620422, 0.0, 0.07103116810321808, 619.68505859375),
  vec4f(0.8794039487838745, 0.0, 0.08088549971580505, 622.0472412109375),
  vec4f(0.8399484753608704, 0.0, 0.08758203685283661, 624.409423828125),
  vec4f(0.7982639074325562, 0.0, 0.09153829514980316, 626.7716674804688),
  vec4f(0.7547056078910828, 0.0, 0.09311319887638092, 629.1338500976562),
  vec4f(0.7135004997253418, 0.0, 0.09314297139644623, 631.4960327148438),
  vec4f(0.6734148263931274, 0.0, 0.09178439527750015, 633.8582763671875),
  vec4f(0.6325734257698059, 0.0, 0.08902440220117569, 636.220458984375),
  vec4f(0.5913266539573669, 0.0, 0.08510835468769073, 638.5827026367188),
  vec4f(0.5482004880905151, 0.0, 0.08000007271766663, 640.9448852539062),
  vec4f(0.5029013156890869, 0.0, 0.07381634414196014, 643.3070678710938),
  vec4f(0.45871591567993164, 0.0, 0.06719779968261719, 645.6693115234375),
  vec4f(0.41603878140449524, 0.0, 0.06035161763429642, 648.031494140625),
  vec4f(0.3757951259613037, 0.0, 0.05354269593954086, 650.3936767578125),
  vec4f(0.3403148949146271, 0.0, 0.04720335081219673, 652.7559204101562),
  vec4f(0.30665019154548645, 0.0, 0.04099609702825546, 655.1181030273438),
  vec4f(0.27495285868644714, 0.0, 0.03501851484179497, 657.4802856445312),
  vec4f(0.2453300952911377, 0.0, 0.029347775503993034, 659.842529296875),
  vec4f(0.21886122226715088, 0.0, 0.024153901264071465, 662.2047119140625),
  vec4f(0.19440701603889465, 0.0, 0.01932777278125286, 664.5669555664062),
  vec4f(0.17189663648605347, 0.0, 0.014888244681060314, 666.9291381835938),
  vec4f(0.1513083279132843, 0.0, 0.01084998156875372, 669.2913208007812),
  vec4f(0.1310787945985794, 0.0, 0.007133417297154665, 671.653564453125),
  vec4f(0.11246760934591293, 0.0, 0.0038684343453496695, 674.0157470703125),
  vec4f(0.09605303406715393, 0.0, 0.001074651489034295, 676.3779296875),
  vec4f(0.08166374266147614, 0.0005675656720995903, 0.0, 678.7401733398438),
  vec4f(0.06869003921747208, 0.001405493007041514, 0.0, 681.1023559570312),
  vec4f(0.05708758533000946, 0.0020403882954269648, 0.0, 683.4645385742188),
  vec4f(0.04721240699291229, 0.002504299860447645, 0.0, 685.8267822265625),
  vec4f(0.03885701671242714, 0.0028238212689757347, 0.0, 688.18896484375),
  vec4f(0.032088425010442734, 0.0030484620947390795, 0.0, 690.5512084960938),
  vec4f(0.027107372879981995, 0.0032661701552569866, 0.0, 692.9133911132812),
  vec4f(0.02281401865184307, 0.0034154034219682217, 0.0, 695.2755737304688),
  vec4f(0.019129568710923195, 0.003507711226120591, 0.0, 697.6378173828125),
  vec4f(0.015981433913111687, 0.0035538729280233383, 0.0, 700.0),
);

fn _vgsl_33cc580b__spectralSample(index: u32) -> vec4f {
  return _vgsl_33cc580b__SPECTRAL_LUT[min(index, 127u)];
}
`};var he={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/particle-light-downsample.wgsl
// Builds the low-frequency particle-light field directly from the HDR scene.
// An 8x8 area filter preserves thin rays when reducing straight to 1/16 while
// deliberately avoiding the visible bloom threshold.

struct _vgsl_7e163447__DownsampleParams {
  sourceTexelSize: vec2f,
  sourceToTargetScale: vec2f,
}

@group(0) @binding(0) var sourceTexture: texture_2d<f32>;
@group(0) @binding(1) var sourceSampler: sampler;
@group(0) @binding(2) var<uniform> params: _vgsl_7e163447__DownsampleParams;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  var color = vec3f(0.0);
  for (var y = 0u; y < 8u; y = y + 1u) {
    for (var x = 0u; x < 8u; x = x + 1u) {
      let grid = vec2f(f32(x), f32(y)) - vec2f(3.5);
      let offset = grid * 0.125
        * params.sourceToTargetScale * params.sourceTexelSize;
      color += textureSampleLevel(
        sourceTexture,
        sourceSampler,
        uv + offset,
        0.0,
      ).rgb;
    }
  }
  return vec4f(max(color / 64.0, vec3f(0.0)), 1.0);
}
`};var be={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/present.wgsl
// Final linear-HDR presentation. The bloom pyramid has already been combined
// into one energy-normalized half-resolution texture, so this pass adds it to
// the untouched HDR scene and performs the one ACES tone mapping plus sRGB
// conversion. Geometry was already resolved by the 4x MSAA scene targets.

      

@group(0) @binding(0) var sceneTexture: texture_2d<f32>;
@group(0) @binding(1) var bloomTexture: texture_2d<f32>;
@group(0) @binding(2) var bloomSampler: sampler;

struct _vgsl_60f9ce56__PresentParams {
  bloomStrength: f32,
}

@group(0) @binding(3) var<uniform> params: _vgsl_60f9ce56__PresentParams;

@fragment
fn fs_main(
  @location(0) uv: vec2f,
  @builtin(position) position: vec4f,
) -> @location(0) vec4f {
  let scene = textureLoad(sceneTexture, vec2i(position.xy), 0).rgb;
  let bloom = textureSampleLevel(bloomTexture, bloomSampler, uv, 0.0).rgb;
  let linear = max(scene + bloom * max(params.bloomStrength, 0.0), vec3f(0.0));
  return vec4f(_vgsl_b50c27e4__linearToSrgb3(_vgsl_b50c27e4__tonemapAces(linear)), 1.0);
}

// vgsl-module: /Users/sean/Documents/techtree-climb/techtree-ash/assets/node_modules/@vgpu/wgsl-std/src/color/index.wgsl










fn _vgsl_b50c27e4__linearToSrgb(value: f32) -> f32 {
  if (value <= 0.0031308) {
    return value * 12.92;
  }
  return 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

fn _vgsl_b50c27e4__linearToSrgb3(value: vec3f) -> vec3f {
  return vec3f(_vgsl_b50c27e4__linearToSrgb(value.r), _vgsl_b50c27e4__linearToSrgb(value.g), _vgsl_b50c27e4__linearToSrgb(value.b));
}



fn _vgsl_b50c27e4__tonemapAces(value: vec3f) -> vec3f {
  let a = 2.51;
  let b = 0.03;
  let c = 2.43;
  let d = 0.59;
  let e = 0.14;
  return clamp((value * (a * value + b)) / (value * (c * value + d) + e), vec3f(0.0), vec3f(1.0));
}




`};var xe={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/pipelines/dark/copy-presentation.wgsl
// Exact copy of the retained, display-encoded dark base. \`textureLoad\` keeps
// pixel centres and encoded values unchanged; dust is added after this draw.

@group(0) @binding(0) var sourceTexture: texture_2d<f32>;

struct _vgsl_616a70b9__PresentParams {
  backgroundColor: vec3f,
  revealProgress: f32,
}

@group(0) @binding(1) var<uniform> params: _vgsl_616a70b9__PresentParams;

@fragment
fn fs_main(@builtin(position) position: vec4f) -> @location(0) vec4f {
  let presented = textureLoad(sourceTexture, vec2i(position.xy), 0);
  let reveal = clamp(params.revealProgress, 0.0, 1.0);
  if (reveal >= 1.0) { return presented; }
  return vec4f(mix(params.backgroundColor, presented.rgb, reveal), 1.0);
}
`};var F=2200;function we(e){let{gpu:n,label:r}=e,o=_(n,{shader:_e,geometry:e.lightGeometry,blend:"additive",cull:"none",depth:!1,label:`${r}.light`}),t=u(n,ie,{label:`${r}.pass-b-copy-a`}),l=u(n,ue,{label:`${r}.bloom-extract`}),a=Array.from({length:4},(I,g)=>{let w=A[g];return{horizontal:u(n,w.horizontal==="bilinear-pairs"?C:G,{label:`${r}.bloom-${g}-horizontal`}),vertical:u(n,w.vertical==="bilinear-pairs"?C:G,{label:`${r}.bloom-${g}-vertical`})}}),i=u(n,de,{label:`${r}.bloom-composite`}),c=u(n,he,{label:`${r}.particle-light-downsample`}),s=u(n,be,{label:`${r}.present`}),p=u(n,xe,{label:`${r}.copy-presentation`}),f=_(n,{shader:le,geometry:e.prism,cull:"front",depth:!1,blend:"premultiplied",label:`${r}.glass-back`}),m=_(n,{shader:ce,geometry:e.prism,cull:"back",depth:!1,label:`${r}.glass-front`}),h=_(n,{shader:ge,vertices:6,instances:F,cull:"none",depth:!1,blend:"additive",label:`${r}.dust`});return{light:o,copyBackground:t,bloomExtract:l,bloomBlur:a,bloomComposite:i,particleLightDownsample:c,present:s,copyPresentation:p,glassBack:f,glassFront:m,dust:h}}function ye(e,n){let{gpu:r,label:o}=n;n.controls.wireframe&&!e.wireframe&&(e.wireframe=_(r,{shader:pe,geometry:te(n),cull:"none",depth:!1,blend:"premultiplied",label:`${o}.wireframe`})),n.controls.lightWireframe&&!e.lightWireframe&&(e.lightWireframe=_(r,{shader:fe,geometry:n.lightGeometry,cull:"none",depth:!1,blend:"premultiplied",label:`${o}.light-wireframe`}))}var Te=y.map(e=>Q(e)),Ae=Te.map((e,n)=>ve(e,y[n]));function M(e,n,r){let t={direction:n==="horizontal"?[1,0]:[0,1],texelSize:[1/r[0],1/r[1]]};if(A[e]?.[n]==="bilinear-pairs"){let a=Ae[e];return{...t,kernel:[a.centerWeight,a.pairCount,0,0],weights0:a.weights.slice(0,4),weights1:a.weights.slice(4,8),weights2:a.weights.slice(8,12),offsets0:a.offsets.slice(0,4),offsets1:a.offsets.slice(4,8),offsets2:a.offsets.slice(8,12)}}let l=Te[e];return{...t,tapCount:y[e],coefficients0:l.slice(0,4),coefficients1:l.slice(4,8),coefficients2:l.slice(8,12),coefficients3:l.slice(12,16),coefficients4:l.slice(16,20),coefficients5:l.slice(20,24)}}function V(e,n,r,o=!0,t=1,l=1,a=!0){let i=e.backgroundTarget,c=e.sceneTarget,s=e.bloomTargets,p=e.presentationTarget,f=n.studioEnvironment;if(!i||!c||!s||!p)throw new Error("prepare() must create dark pipeline targets before bind().");if(!f)throw new Error("prepare() must create prism environments before bind().");let m=n.debugEnvironment??f;ye(e,n);let h=me("dark",t);if(!o){a&&e.copyPresentation.set({params:h}),e.dust.set({params:a?{time:r,revealProgress:h.revealProgress}:{time:r}});return}let I=oe(n,l);e.light.set({scene:I}),e.lightWireframe?.set({scene:I}),e.copyBackground.set({sceneTexture:i}),e.glassBack.set({params:U(n,"dark"),studioEnvironment:f.texture,debugEnvironment:m.texture,environmentSampler:n.environmentSampler}),e.glassFront.set({params:U(n,"dark"),sceneTexture:i,sceneSampler:n.sceneSampler,studioEnvironment:f.texture,debugEnvironment:m.texture,environmentSampler:n.environmentSampler}),e.wireframe?.set({params:{viewProjection:n.view.viewProjection}}),e.bloomExtract.set({sourceTexture:c,sourceSampler:n.sceneSampler,params:{threshold:n.controls.postprocess.bloomThreshold}});let g=s[3];e.particleLightDownsample.set({sourceTexture:c,sourceSampler:n.sceneSampler,params:{sourceTexelSize:[1/c.size[0],1/c.size[1]],sourceToTargetScale:[c.size[0]/g.vertical.size[0],c.size[1]/g.vertical.size[1]]}}),e.bloomBlur.forEach((w,b)=>{let D=s[b],De=b===0||b===3?D.vertical:s[b-1].vertical;w.horizontal.set({sourceTexture:De,sourceSampler:n.sceneSampler,params:M(b,"horizontal",D.horizontal.size)}),w.vertical.set({sourceTexture:D.horizontal,sourceSampler:n.sceneSampler,params:M(b,"vertical",D.vertical.size)})}),e.bloomComposite.set({level0Texture:s[0].vertical,level1Texture:s[1].vertical,level2Texture:s[2].vertical,levelSampler:n.sceneSampler,params:{radius:X(n.controls.postprocess.bloomRadius,z.bloomRadius.min,z.bloomRadius.max),factors:[...j,0]}}),e.present.set({sceneTexture:c,bloomTexture:s[0].horizontal,bloomSampler:n.sceneSampler,params:{bloomStrength:n.controls.view==="glass"?n.controls.postprocess.bloomStrength:0}}),e.copyPresentation.set({sourceTexture:p,params:h}),e.dust.set({params:Ie(n,r,h.revealProgress),colorTexture:s[1].vertical,lightTexture:g.vertical,lightSampler:n.sceneSampler})}function Ie(e,n,r){return{viewProjection:e.view.viewProjection,fieldHalfExtent:se(e),outputSize:e.outputSize,time:n,cameraDistance:e.cameraDistance,lightPlaneZ:J,prismA:B.a,prismB:B.b,prismC:B.c,prismFrontZ:Y,revealProgress:r}}function Se(e,n){e.backdropBundle||!e.backgroundTarget||(e.backdropBundle=$(n.gpu,{target:e.backgroundTarget,label:`${n.label}.dark-backdrop`},r=>{r.draw(e.light,{firstVertex:0,vertices:T}),r.draw(e.light,{firstVertex:k,vertices:E}),r.draw(e.glassBack),r.draw(e.light,{firstVertex:P,vertices:S})}))}var Pe=[0,0,0,1],Oe=/^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i;function ke(e,n){if(n==="caustic")return Pe;let r=e.match(Oe);return r?[N(Number.parseInt(r[1],16)/255),N(Number.parseInt(r[2],16)/255),N(Number.parseInt(r[3],16)/255),1]:Pe}function N(e){return e<=.04045?e/12.92:((e+.055)/1.055)**2.4}function Ee(e,n,r,o,t={}){let l=n.backgroundTarget,a=n.sceneTarget,i=n.bloomTargets,c=n.presentationTarget;if(!l||!a||!i||!c)throw new Error("prepare() must run before rendering the dark pipeline.");(t.updateScene??!0)&&(ze(e,n,r,t.profile),e.pass(d({target:a,clear:[0,0,0,1]},t.profile,"dark.scene"),s=>{s.draw(n.copyBackground),r.controls.view==="glass"&&(s.draw(n.glassFront),r.controls.wireframe&&n.wireframe&&s.draw(n.wireframe))}),e.pass(d({target:i[0].vertical,clear:[0,0,0,1]},t.profile,"dark.bloom.extract"),s=>s.draw(n.bloomExtract)),i.slice(0,3).forEach((s,p)=>{e.pass(d({target:s.horizontal,clear:[0,0,0,1]},t.profile,`dark.bloom.${p}.horizontal`),f=>{f.draw(n.bloomBlur[p].horizontal)}),e.pass(d({target:s.vertical,clear:[0,0,0,1]},t.profile,`dark.bloom.${p}.vertical`),f=>f.draw(n.bloomBlur[p].vertical))}),e.pass(d({target:i[3].vertical,clear:[0,0,0,1]},t.profile,"dark.particle-light.downsample"),s=>s.draw(n.particleLightDownsample)),i.slice(3).forEach((s,p)=>{let f=3+p;e.pass(d({target:s.horizontal,clear:[0,0,0,1]},t.profile,`dark.particle-light.${f}.horizontal`),m=>{m.draw(n.bloomBlur[f].horizontal)}),e.pass(d({target:s.vertical,clear:[0,0,0,1]},t.profile,`dark.particle-light.${f}.vertical`),m=>m.draw(n.bloomBlur[f].vertical))}),e.pass(d({target:i[0].horizontal,clear:[0,0,0,1]},t.profile,"dark.bloom.composite"),s=>{s.draw(n.bloomComposite)}),e.pass(d({target:c,clear:[0,0,0,1]},t.profile,"dark.present-cache"),s=>s.draw(n.present))),e.pass(d({target:o},t.profile,"dark.output"),s=>{s.draw(n.copyPresentation),r.controls.view==="glass"&&s.draw(n.dust,{instances:F})})}function ze(e,n,r,o){let t=n.backgroundTarget,l=r.controls.view==="glass"||r.controls.view==="back",a=r.controls.view!=="wall";e.pass(d({target:t,clear:ke(r.controls.wallColor,r.controls.view)},o,"dark.backdrop"),i=>{if(r.controls.view==="glass"&&!r.controls.lightWireframe&&n.backdropBundle){i.bundles(n.backdropBundle);return}a&&(i.draw(n.light,{firstVertex:0,vertices:T}),i.draw(n.light,{firstVertex:k,vertices:E}),r.controls.lightWireframe&&n.lightWireframe&&(i.draw(n.lightWireframe,{firstVertex:0,vertices:T}),i.draw(n.lightWireframe,{firstVertex:k,vertices:E}))),l&&i.draw(n.glassBack),a&&(i.draw(n.light,{firstVertex:P,vertices:S}),r.controls.lightWireframe&&n.lightWireframe&&i.draw(n.lightWireframe,{firstVertex:P,vertices:S}))})}function d(e,n,r){let o=n?.pass(r);return o?{...e,timer:o}:e}function Le(e,n,r,o){let t=n.gpu.device.isCompatibilityMode?void 0:!0;e.backgroundTarget??=x(n.gpu,{size:r,format:"rgba16float",msaa:t,label:`${n.label}.pass-a-back-and-light`}),e.sceneTarget??=x(n.gpu,{size:r,format:"rgba16float",msaa:t,label:`${n.label}.pass-b-front-glass`}),e.bloomTargets??=Array.from({length:4},(l,a)=>Ue(n,r,a)),e.presentationTarget??=x(n.gpu,{size:r,format:o,label:`${n.label}.retained-dark-presentation`}),K(e,r)}function Ue(e,n,r){let o=Z(e.gpu.device.features,r);return Object.freeze({horizontal:x(e.gpu,{size:q(n,r),format:o,label:`${e.label}.bloom-${r}-horizontal`}),vertical:x(e.gpu,{size:q(n,r),format:o,label:`${e.label}.bloom-${r}-vertical`})})}function K(e,n){L(e.backgroundTarget,n),L(e.sceneTarget,n),L(e.presentationTarget,n),e.bloomTargets?.forEach((r,o)=>{let t=q(n,o);L(r.horizontal,t),L(r.vertical,t)})}function Re(e){R(e.backgroundTarget),e.backgroundTarget=void 0,R(e.sceneTarget),e.sceneTarget=void 0,e.bloomTargets?.forEach(n=>{R(n.horizontal),R(n.vertical)}),e.bloomTargets=void 0,R(e.presentationTarget),e.presentationTarget=void 0}function q(e,n){let r=O[n]??O.at(-1);return[Math.max(1,Math.ceil(e[0]/r)),Math.max(1,Math.ceil(e[1]/r))]}function L(e,n){!e||e.size[0]===n[0]&&e.size[1]===n[1]||e.resize(n)}function R(e){e?.destroy?.()}function Qn(e){let n=we(e),r=!1,o=1;return{mode:"dark",get targets(){return{backdropHDR:n.backgroundTarget,sceneHDR:n.sceneTarget,presentationLDR:n.presentationTarget}},async prepare(t){ee(e,t.size),Le(n,e,t.size,t.format),r=!1;let l=ae(e);V(n,e,0,!0),await re([l,...Ge(n,t)]),Se(n,e)},resize(t){K(n,t),r=!1},bind(t,l){let a=l?.revealProgress??1,i=a!==o;V(n,e,t,(l?.updateScene??!0)||!r,a,l?.beamWidthReveal??1,i),o=a},render(t,l,a){let i=(a?.updateScene??!0)||!r;Ee(t,n,e,l,{...a,updateScene:i}),r=!0},debugSources:()=>ne,debugTarget(t){return Ce(n,t)},destroy(){r=!1,Re(n)}}}function Ce(e,n){let r=e.backgroundTarget,o=e.sceneTarget,t=e.bloomTargets;if(n==="dark-backdrop-hdr"&&r)return{primary:r};if(n==="dark-scene-hdr"&&o)return{primary:o};if(n==="dark-front-glass"&&o&&r)return{primary:o,secondary:r,mode:"difference",differenceGain:5};if(n==="dark-bloom-composite"&&t)return{primary:t[0].horizontal};if(n==="dark-particle-light"&&t)return{primary:t[3].vertical};let l=/^dark-bloom-(\d+)$/.exec(n)?.[1],a=l===void 0?-1:Number.parseInt(l,10);if(t&&a>=0&&a<3)return{primary:t[a].vertical}}function Ge(e,n){let r=e.backgroundTarget,o=e.sceneTarget,t=e.bloomTargets,l=e.presentationTarget,a={colors:[n.format]};return[e.light.compile(r),e.glassBack.compile(r),...e.lightWireframe?[e.lightWireframe.compile(r)]:[],e.copyBackground.compile(o),e.glassFront.compile(o),...e.wireframe?[e.wireframe.compile(o)]:[],e.dust.compile(a),e.bloomExtract.compile(t[0].vertical),...e.bloomBlur.flatMap((i,c)=>[i.horizontal.compile(t[c].horizontal),i.vertical.compile(t[c].vertical)]),e.bloomComposite.compile(t[0].horizontal),e.particleLightDownsample.compile(t[3].vertical),e.present.compile(l),e.copyPresentation.compile(a)]}export{Qn as a};

