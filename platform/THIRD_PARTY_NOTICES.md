# Third-party notices

## VGPU prism and crown renderers

The 13-cube crown under `assets/js/optics/crown/` is adapted from the public
VGPU homepage prism and from the Regents crown adaptation of that renderer.

- Project: `vercel-labs/vgpu`
- Source: https://github.com/vercel-labs/vgpu
- Commit: `bd3b05101fdd1193a1593558d3c52a0b2b18f31d`
- Source directory: `apps/docs/app/[lang]/(home)/components/prism-background`
- License: MIT

The `/prism` renderer is a source-built copy of the current public dark homepage
pipeline from the same project:

- Commit: `ef2418bc13269cc4b3198ecfebf34a26f6a1073e`
- Source directory: `apps/docs/app/[lang]/(home)/components/prism-background`
- Package: `vgpu@0.3.1`

Only the production dark pipeline and its required chunks are vendored. The
React control panel, debug renderer, performance sampler, and light-mode
pipeline are not included. Phoenix renders the page copy, while the local
WebGPU canvas loads only on `/prism` and pauses when it is offscreen or hidden.
The inline VGPU wordmark outlines come from the same current repository.

### MIT License

Copyright (c) 2025 Vercel, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
