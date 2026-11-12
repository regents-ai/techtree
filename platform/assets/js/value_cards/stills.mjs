// Draws every value card's still frame into priv/static/images/value-cards/:
// each panel at its still moment, as <name>.webp. The colours and shaders are
// the site's own, read from panel.ts and panels/ beside this file.
//
//   npm run stills:value-cards            (from platform/, after changing a panel)
//   npm run stills:value-cards -- level   (only the panels named)
//
// vgpu draws each frame on this machine's GPU; a headless browser only packs
// the pixels as WebP. Needs Node 22.18 or newer, which reads the .ts files as they are.
import {mkdirSync, readdirSync, writeFileSync} from "node:fs"
import {createRequire} from "node:module"
import {basename, dirname, join} from "node:path"
import {fileURLToPath} from "node:url"
import {prepareShader} from "@vgpu/wgsl/prepare"
import {effect, frame, init, target} from "vgpu/node"
import {shaderFor, uniforms} from "./panel.ts"

const {chromium} = createRequire(import.meta.url)("playwright")
const here = dirname(fileURLToPath(import.meta.url))
const out = join(here, "../../../priv/static/images/value-cards")
// Wide enough to stay sharp on a dense screen at the sizes a card takes.
const SIZE = 600
const only = process.argv.slice(2)

const names = readdirSync(join(here, "panels"))
  .filter(file => file.endsWith(".ts"))
  .map(file => basename(file, ".ts"))
  .filter(name => only.length === 0 || only.includes(name))

mkdirSync(out, {recursive: true})
const gpu = await init()
const browser = await chromium.launch()
const page = await browser.newPage()

for (const name of names) {
  const panel = (await import(join(here, "panels", `${name}.ts`)))[name]
  const still = target(gpu, {size: [SIZE, SIZE], format: "rgba8unorm"})
  const shader = effect(gpu, prepareShader(shaderFor(panel), `value_card_${name}.wgsl`), {
    set: uniforms(panel, SIZE, SIZE, panel.stillAt),
  })
  frame(gpu, current => current.pass(still, shader))
  const read = await still.color.read({mipLevel: 0, region: "all"})
  const pixels = read
  const webp = await page.evaluate(
    async ([base64, size]) => {
      const bytes = Uint8ClampedArray.from(atob(base64), character => character.charCodeAt(0))
      const canvas = new OffscreenCanvas(size, size)
      canvas.getContext("2d").putImageData(new ImageData(bytes, size, size), 0, 0)
      const packed = new Uint8Array(await (await canvas.convertToBlob({type: "image/webp", quality: 0.78})).arrayBuffer())
      return btoa(Array.from(packed, byte => String.fromCharCode(byte)).join(""))
    },
    [Buffer.from(pixels.buffer, pixels.byteOffset, SIZE * SIZE * 4).toString("base64"), SIZE],
  )
  writeFileSync(join(out, `${name}.webp`), Buffer.from(webp, "base64"))
  console.log(`${name}.webp`)
}

await browser.close()
gpu.dispose()
