// Generated file. Do not edit.
//
// Source: vercel-labs/vgpu @ bd3b05101fdd1193a1593558d3c52a0b2b18f31d
// Entry:  apps/docs/app/[lang]/(home)/components/prism-background/copy-linear.wgsl
// Modules resolved into this shader:
//   apps/docs/app/[lang]/(home)/components/prism-background/copy-linear.wgsl  sha256:efe393a9a45832a9acd7b87c2d8428cd440bf394ce1321c7aaa2f7efd4c856a2
// Method: @vgpu/wgsl 0.3.1 resolveShader(), with the same identifier-preserving
//   options the upstream bundler loader is configured with, then module paths rewritten
//   to the stable identities above. Resolution happens here, once, not in the browser.
export default {version: 1, wgsl: "// vgsl-module: apps/docs/app/[lang]/(home)/components/prism-background/copy-linear.wgsl\n// Raw ping-pong copy. The scene stays in linear HDR until the final surface pass.\n\n@group(0) @binding(0) var sceneTexture: texture_2d<f32>;\n\n@fragment\nfn fs_main(@builtin(position) position: vec4f) -> @location(0) vec4f {\n  return textureLoad(sceneTexture, vec2i(position.xy), 0);\n}\n"} as const
