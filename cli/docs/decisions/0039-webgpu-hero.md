# 0039 — The hero techtree renders in WebGPU (vgpu), overriding 0030's ban

Date: 2026-08-27. Founder ruling.

## Ruling

The homepage hero gains a techtree visual in the style of the founder's
reference image: a branching lattice of 3D cubes — the voxel mark
extruded — lit by a point light that follows the reader's cursor.
It is rendered with vgpu (vgpu.sh), a WebGPU library, explicitly
overriding decision 0030's "CSS or lightweight SVG only, no WebGL"
rule for this one surface. The founder chose WebGPU over the
dependency-free CSS-3D alternative after both were costed.

## What the override does NOT change

- **The real-data rule stands.** Labeled nodes, statuses and counts
  still come only from served artifacts: the evidence graph remains
  the DOM data layer. The WebGPU lattice is label-free ambience —
  cubes and connectors carrying no text, no status, no numbers —
  plus lit cube bodies for the real nodes.
- **Self-contained serving stands.** The library is vendored and
  bundled through the site's own pipeline; the strict CSP
  (script-src 'self') is not loosened; nothing loads from a CDN.
- **Graceful honesty stands.** Browsers without WebGPU, readers with
  prefers-reduced-motion, and touch devices get the existing 2D
  evidence graph exactly as it is today; the feature detects and
  degrades, never breaks. Rendering pauses when the hero is
  off-screen.

## Sequencing

This is site presentation: it moves no release coordinate and no
scientific digest, and classifies as site-only under the 0022
discipline. It must keep the full ash gate green and may not touch
frozen paths.
