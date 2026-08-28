import{f as g,h as f,k as s,m as l}from"./prism-current-chunk-SQQEIMQF.js";var h={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-bake.wgsl
// Bakes either authored analytic environment into the same equirectangular HDR
// texture layout used by the environment-map and transmission examples.

     
     
     

struct _vgsl_6993c98a__BakeParams {
  debug: f32,
}

@group(0) @binding(0) var<uniform> params: _vgsl_6993c98a__BakeParams;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let direction = _vgsl_757932e2__direction_from_equirect(uv);
  if (params.debug > 0.5) {
    return vec4f(_vgsl_2ca0ad87__sampleDebugEnvironment(direction), 1.0);
  }
  return vec4f(_vgsl_51c980fd__sampleStudioEnvironment(direction), 1.0);
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-debug-map.wgsl
// Directional environment used to audit reflection and refraction paths.
//
// The six dominant-axis faces deliberately have unrelated colors, matching the
// topology of a cubemap without requiring a texture. Three great-circle ribbons
// cross those face boundaries. Their colors come only from the global direction,
// so the center of every ribbon is continuous even where the face color changes.

const _vgsl_2ca0ad87__DEBUG_POSITIVE_X = vec3f(1.0, 0.16, 0.11);
const _vgsl_2ca0ad87__DEBUG_NEGATIVE_X = vec3f(0.05, 0.92, 0.92);
const _vgsl_2ca0ad87__DEBUG_POSITIVE_Y = vec3f(0.18, 1.0, 0.26);
const _vgsl_2ca0ad87__DEBUG_NEGATIVE_Y = vec3f(1.0, 0.12, 0.72);
const _vgsl_2ca0ad87__DEBUG_POSITIVE_Z = vec3f(0.14, 0.32, 1.0);
const _vgsl_2ca0ad87__DEBUG_NEGATIVE_Z = vec3f(1.0, 0.72, 0.06);

struct _vgsl_2ca0ad87__DebugFace {
  color: vec3f,
  /** WebGPU cubemap face coordinates: (0, 0) is the authored top-left. */
  uv: vec2f,
}

fn _vgsl_2ca0ad87__debugFace(direction: vec3f) -> _vgsl_2ca0ad87__DebugFace {
  let absolute = abs(direction);
  if (absolute.x >= absolute.y && absolute.x >= absolute.z) {
    let positive = direction.x >= 0.0;
    let facePosition = select(
      vec2f(direction.z, -direction.y),
      vec2f(-direction.z, -direction.y),
      positive,
    );
    return _vgsl_2ca0ad87__DebugFace(
      select(_vgsl_2ca0ad87__DEBUG_NEGATIVE_X, _vgsl_2ca0ad87__DEBUG_POSITIVE_X, positive),
      facePosition / absolute.x * 0.5 + 0.5,
    );
  }
  if (absolute.y >= absolute.z) {
    let positive = direction.y >= 0.0;
    let facePosition = select(
      vec2f(direction.x, -direction.z),
      vec2f(direction.x, direction.z),
      positive,
    );
    return _vgsl_2ca0ad87__DebugFace(
      select(_vgsl_2ca0ad87__DEBUG_NEGATIVE_Y, _vgsl_2ca0ad87__DEBUG_POSITIVE_Y, positive),
      facePosition / absolute.y * 0.5 + 0.5,
    );
  }
  let positive = direction.z >= 0.0;
  let facePosition = select(
    vec2f(-direction.x, -direction.y),
    vec2f(direction.x, -direction.y),
    positive,
  );
  return _vgsl_2ca0ad87__DebugFace(
    select(_vgsl_2ca0ad87__DEBUG_NEGATIVE_Z, _vgsl_2ca0ad87__DEBUG_POSITIVE_Z, positive),
    facePosition / absolute.z * 0.5 + 0.5,
  );
}

fn _vgsl_2ca0ad87__debugRibbonMask(distanceFromPlane: f32) -> f32 {
  return 1.0 - smoothstep(0.018, 0.035, abs(distanceFromPlane));
}

fn _vgsl_2ca0ad87__debugArrowMask(uv: vec2f) -> f32 {
  let point = vec2f(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0);
  let shaft = (1.0 - smoothstep(0.05, 0.075, abs(point.x)))
    * smoothstep(-0.62, -0.54, point.y)
    * (1.0 - smoothstep(0.18, 0.25, point.y));
  let headWidth = max(0.0, (0.68 - point.y) * 0.72);
  let head = (1.0 - smoothstep(headWidth, headWidth + 0.025, abs(point.x)))
    * smoothstep(0.12, 0.18, point.y)
    * (1.0 - smoothstep(0.62, 0.68, point.y));
  return max(shaft, head);
}

/** Diagnostic radiance arriving from \`direction\`, in linear RGB. */
fn _vgsl_2ca0ad87__sampleDebugEnvironment(directionInput: vec3f) -> vec3f {
  let direction = normalize(directionInput);
  let face = _vgsl_2ca0ad87__debugFace(direction);

  // This world-space ramp is independent of face-local UV. Negating direction.y
  // therefore reverses the lighting of all four side faces at once.
  let worldHeight = direction.y * 0.5 + 0.5;
  var color = face.color * (0.42 + worldHeight * 0.44) + vec3f(0.025);

  // Dark seams make the analytically selected cubemap face unambiguous.
  let edgeDistance = min(
    min(face.uv.x, 1.0 - face.uv.x),
    min(face.uv.y, 1.0 - face.uv.y),
  );
  let faceEdge = 1.0 - smoothstep(0.012, 0.026, edgeDistance);
  color = mix(color, vec3f(0.012), faceEdge * 0.78);

  // Each ribbon follows a great circle through both ends of its named axis.
  // Its gradient is derived from that world-space coordinate, not face-local UV,
  // which makes it a continuous reference across every cubemap seam it crosses.
  let xRibbon = _vgsl_2ca0ad87__debugRibbonMask(direction.y);
  let yRibbon = _vgsl_2ca0ad87__debugRibbonMask(direction.z);
  let zRibbon = _vgsl_2ca0ad87__debugRibbonMask(direction.x);
  let xGradient = mix(_vgsl_2ca0ad87__DEBUG_NEGATIVE_X, _vgsl_2ca0ad87__DEBUG_POSITIVE_X, direction.x * 0.5 + 0.5);
  let yGradient = mix(_vgsl_2ca0ad87__DEBUG_NEGATIVE_Y, _vgsl_2ca0ad87__DEBUG_POSITIVE_Y, direction.y * 0.5 + 0.5);
  let zGradient = mix(_vgsl_2ca0ad87__DEBUG_NEGATIVE_Z, _vgsl_2ca0ad87__DEBUG_POSITIVE_Z, direction.z * 0.5 + 0.5);

  color = mix(color, xGradient * 1.35 + vec3f(0.08), xRibbon * 0.92);
  color = mix(color, yGradient * 1.35 + vec3f(0.08), yRibbon * 0.92);
  color = mix(color, zGradient * 1.35 + vec3f(0.08), zRibbon * 0.92);

  // Face-local orientation legend. It is intentionally not symmetric under
  // either U or V inversion:
  //   top = white, bottom = black, left = cyan, right = orange.
  let top = 1.0 - smoothstep(0.035, 0.06, face.uv.y);
  let bottom = smoothstep(0.94, 0.965, face.uv.y);
  let left = 1.0 - smoothstep(0.035, 0.06, face.uv.x);
  let right = smoothstep(0.94, 0.965, face.uv.x);
  color = mix(color, vec3f(1.8), top * 0.96);
  color = mix(color, vec3f(0.004), bottom * 0.98);
  color = mix(color, vec3f(0.0, 1.4, 1.7), left * 0.94);
  color = mix(color, vec3f(1.8, 0.42, 0.02), right * 0.94);

  // A white upward arrow remains readable away from the face boundaries and
  // makes a vertical flip obvious even in a small internal reflection.
  color = mix(color, vec3f(1.8), _vgsl_2ca0ad87__debugArrowMask(face.uv) * 0.94);
  return color;
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-map-common.wgsl
const _vgsl_757932e2__PI: f32 = 3.141592653589793;

// Copied from the environment-map and transmission examples. Texture v=0 is
// the zenith and v=1 the nadir, so the direction-to-texture Y convention stays
// explicit and shared by every reflection/refraction path.


fn _vgsl_757932e2__direction_from_equirect(uv: vec2f) -> vec3f {
  let phi = (uv.x - 0.5) * 2.0 * _vgsl_757932e2__PI;
  let theta = uv.y * _vgsl_757932e2__PI;
  return vec3f(
    sin(theta) * cos(phi),
    cos(theta),
    sin(theta) * sin(phi),
  );
}

/** Selects the prefiltered level matching the direction's angular footprint. */


/**
 * One texture fetch with the examples' smooth reconstruction. \`size\` is level
 * zero's extent and \`lod\` may be fractional for trilinear mip blending.
 */


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

     

struct _vgsl_51c980fd__StudioPanel {
  direction: vec3f,
  /** Half-extents of the panel in tangent space, as a fraction of its distance. */
  size: vec2f,
  feather: f32,
  color: vec3f,
  intensity: f32,
}

/** A back-left wall, soft center fill and dominant right key. */
fn _vgsl_51c980fd__studioPanels() -> array<_vgsl_51c980fd__StudioPanel, 3> {
  return array<_vgsl_51c980fd__StudioPanel, 3>(
    // A broad back-left wall, only a touch brighter than the dark floor.
    _vgsl_51c980fd__StudioPanel(
      vec3f(-0.82, 0.08, 0.57), // direction
      vec2f(1.35, 1.1), // size
      0.22, // feather
      vec3f(0.82, 0.84, 0.88), // color
      0.011 // intensity
    ),
    // A broad, heavily feathered center fill that barely lifts the bottom edge.
    _vgsl_51c980fd__StudioPanel(
      vec3f(0.0, -0.707, 0.707), // direction
      vec2f(0.38, 0.62), // size
      0.18, // feather
      vec3f(1.0, 0.97, 0.91), // color
      0.22 // intensity
    ),
    // The cool right panel is the dominant key and keeps a more defined edge.
    _vgsl_51c980fd__StudioPanel(
      vec3f(0.612, 0.354, 0.707), // direction
      vec2f(0.5, 0.16), // size
      0.035, // feather
      vec3f(0.76, 0.88, 1.0), // color
      20.0 // intensity
    ),
  );
}

/**
 * How much of \`panel\` a ray heading in \`direction\` sees: a rectangle projected
 * onto the sphere, feathered at its border so its edge does not alias in a
 * mirror-smooth reflection.
 */
fn _vgsl_51c980fd__studioPanelMask(direction: vec3f, panel: _vgsl_51c980fd__StudioPanel) -> f32 {
  let forward = normalize(panel.direction);
  // Any helper axis works as long as it is not parallel to the panel's own; the
  // overhead panels are the ones that need the fallback.
  let helper = select(vec3f(0.0, 1.0, 0.0), vec3f(0.0, 0.0, 1.0), abs(forward.y) > 0.92);
  let right = normalize(cross(helper, forward));
  let up = cross(forward, right);
  let facing = dot(direction, forward);
  if (facing <= 0.01) {
    return 0.0;
  }
  let localX = abs(dot(direction, right) / facing);
  let localY = abs(dot(direction, up) / facing);
  let edgeX = 1.0 - smoothstep(panel.size.x, panel.size.x + panel.feather, localX);
  let edgeY = 1.0 - smoothstep(panel.size.y, panel.size.y + panel.feather, localY);
  return edgeX * edgeY;
}

/** Rotates a reflection into the studio's frame. Copied from \`glass-fractal\`. */


/** Radiance arriving from \`direction\`, in linear RGB. */
fn _vgsl_51c980fd__sampleStudioEnvironment(directionInput: vec3f) -> vec3f {
  let direction = normalize(directionInput);
  let floorBlend = 1.0 - smoothstep(-0.22, -0.02, direction.y);
  var room = mix(
    vec3f(0.00025, 0.0003, 0.0004),
    vec3f(0.006, 0.007, 0.009),
    floorBlend,
  );

  // The projection wall occupies the upper part of the -Z hemisphere. Keep the
  // floor below it, but drive the wall itself essentially to black so the prism
  // reflects the same dark surface it physically stands in front of.
  let negativeZ = 1.0 - smoothstep(-0.08, 0.08, direction.z);
  let aboveFloor = smoothstep(-0.28, -0.08, direction.y);
  let backWall = negativeZ * aboveFloor;
  room = mix(room, vec3f(0.00002), backWall);

  // A restrained seam is just bright enough to preserve the floor/wall read.
  let horizon = exp(-abs(direction.y + 0.1) * 22.0) * 0.0012;
  var color = room + vec3f(horizon, horizon * 0.96, horizon * 0.9);
  let panels = _vgsl_51c980fd__studioPanels();
  for (var index = 0u; index < 3u; index = index + 1u) {
    let panel = panels[index];
    color = color + panel.color * (_vgsl_51c980fd__studioPanelMask(direction, panel) * panel.intensity);
  }
  // Filmic compression, then the asset's gamma-2.2 encode and the sRGB decode a
  // sample of it performs.
  let mapped = color / (vec3f(1.0) + color);
  return _vgsl_b50c27e4__srgbToLinear3(pow(max(mapped, vec3f(0.0)), vec3f(1.0 / 2.2)));
}

// vgsl-module: /Users/sean/Documents/techtree-climb/techtree-ash/assets/node_modules/@vgpu/wgsl-std/src/color/index.wgsl




fn _vgsl_b50c27e4__srgbToLinear(value: f32) -> f32 {
  if (value <= 0.04045) {
    return value / 12.92;
  }
  return pow((value + 0.055) / 1.055, 2.4);
}

fn _vgsl_b50c27e4__srgbToLinear3(value: vec3f) -> vec3f {
  return vec3f(_vgsl_b50c27e4__srgbToLinear(value.r), _vgsl_b50c27e4__srgbToLinear(value.g), _vgsl_b50c27e4__srgbToLinear(value.b));
}














`};var b={version:1,wgsl:`// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-blur.wgsl
// Copied from the environment-map/transmission environment pyramid. This runs
// only while baking; runtime glass shading still performs one environment fetch.

     

struct _vgsl_b2d17eda__Blur {
  texel: vec2f,
  direction: vec2f,
  radius: f32,
  equirect_compensation: f32,
}

@group(0) @binding(0) var<uniform> blur: _vgsl_b2d17eda__Blur;
@group(0) @binding(1) var src: texture_2d<f32>;
@group(0) @binding(2) var src_samp: sampler;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let sin_theta = max(sin(uv.y * _vgsl_757932e2__PI), 0.15);
  let scale = mix(1.0, 1.0 / sin_theta, blur.equirect_compensation);
  let step = blur.direction * blur.texel * blur.radius * scale;

  var offsets = array<f32, 3>(0.0, 1.3846153846, 3.2307692308);
  var weights = array<f32, 3>(0.2270270270, 0.3162162162, 0.0702702703);
  var sum = textureSampleLevel(src, src_samp, uv, 0.0) * weights[0];
  for (var index = 1; index < 3; index = index + 1) {
    sum += textureSampleLevel(
      src,
      src_samp,
      uv + step * offsets[index],
      0.0,
    ) * weights[index];
    sum += textureSampleLevel(
      src,
      src_samp,
      uv - step * offsets[index],
      0.0,
    ) * weights[index];
  }
  return sum;
}

// vgsl-module: /private/tmp/vgpu-current.DKqEud/apps/docs/app/[lang]/(home)/components/prism-background/environment-map-common.wgsl
const _vgsl_757932e2__PI: f32 = 3.141592653589793;

// Copied from the environment-map and transmission examples. Texture v=0 is
// the zenith and v=1 the nadir, so the direction-to-texture Y convention stays
// explicit and shared by every reflection/refraction path.




/** Selects the prefiltered level matching the direction's angular footprint. */


/**
 * One texture fetch with the examples' smooth reconstruction. \`size\` is level
 * zero's extent and \`lod\` may be fractional for trilinear mip blending.
 */

`};var i=[1024,512],E=8,A=2*Math.PI/i[0],x=1.15;function U(e){return g(e,{minFilter:"linear",magFilter:"linear",mipmapFilter:"linear",addressModeU:"repeat",addressModeV:"clamp-to-edge"})}function V(e,n,o){let t=e.device.createTexture({size:[...i],format:"rgba16float",mipLevelCount:E,usage:["texture_binding","copy_dst"],label:`${n}.texture`}),r=f(e,h,{label:`${n}.bake`}),a=f(e,b,{label:`${n}.blur`});return r.set({params:{debug:o?1:0}}),{texture:t,bake:r,blur:a,prepared:!1}}async function N(e,n,o){if(n.prepared)return;let t=l(e,{size:i,format:"rgba16float",label:`${n.texture.label}.level0`});await Promise.all([n.bake.compile(t),n.blur.compile(t)]),s(e,r=>{r.pass({target:t,clear:[0,0,0,1]},a=>a.draw(n.bake))}),y(e,t,n.texture,0);for(let r=1;r<E;r++){let a=[Math.max(1,i[0]>>r),Math.max(1,i[1]>>r)],c=l(e,{size:a,format:"rgba16float",label:`${n.texture.label}.blur-h${r}`}),d=l(e,{size:a,format:"rgba16float",label:`${n.texture.label}.level${r}`}),v=[1/a[0],1/a[1]];n.blur.set({src:t,src_samp:o,blur:{texel:v,direction:[1,0],radius:x,equirect_compensation:1}}),s(e,_=>{_.pass({target:c},u=>u.draw(n.blur))}),n.blur.set({src:c,src_samp:o,blur:{texel:v,direction:[0,1],radius:x,equirect_compensation:0}}),s(e,_=>{_.pass({target:d},u=>u.draw(n.blur))}),y(e,d,n.texture,r),m(c),m(t),t=d}m(t),n.prepared=!0}function y(e,n,o,t){let r=e.gpu.createCommandEncoder({label:`${o.label}.copy-level${t}`});r.copyTextureToTexture({texture:n.color.gpu},{texture:o.gpu,mipLevel:t},[n.size[0],n.size[1],1]),e.gpu.queue.submit([r.finish()])}function m(e){e.destroy?.()}function M(e){e?.texture.destroy()}var p=.9803921568627451,P=1,G=2.5,k=.25,T=P*(1-Math.cbrt(1-k)),I={dark:[0,0,0],light:[p,p,p]};function O(e,n=1){return{backgroundColor:I[e],revealProgress:Math.min(1,Math.max(0,n))}}function F(e){let o=1-(1-w(e/P))**3,t=w((e-T)/(G-T));return{opacity:o,beamWidth:1-(1-t)**3}}function w(e){return Math.min(1,Math.max(0,e))}export{i as a,A as b,U as c,V as d,N as e,M as f,O as g,F as h};

