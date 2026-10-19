// Builds the static mockup pages into site/ from src/layout.html and src/pages/*.html.
// Each page starts with one comment holding its settings as JSON.
import {readFileSync, readdirSync, writeFileSync, mkdirSync} from "node:fs"
import {dirname, join} from "node:path"

const root = dirname(new URL(import.meta.url).pathname)
const layout = readFileSync(join(root, "src/layout.html"), "utf8")

const escape = text => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")

const copyButton = (target, variant) => `<button type="button" class="rg-button rg-button--${variant} rg-copy command__copy" data-copy-target="${target}">
        <span class="rg-button__label">
          <span class="rg-copy__words">
            <span class="rg-copy__idle">Copy</span>
            <span class="rg-copy__copied">Copied</span>
            <span class="rg-copy__selected">Selected</span>
            <span class="rg-copy__failed">Couldn't copy</span>
          </span>
        </span>
      </button>`

function commands(body, page) {
  let count = 0
  return body.replace(/<mk-command label="([^"]+)">\n([\s\S]*?)\n\s*<\/mk-command>/g, (_all, label, text) => {
    const id = `${page}-command-${++count}`
    const lines = text.split("\n").map(line => line.trim()).filter(Boolean).join("\n")
    return `<div class="rg-panel rg-panel--surface command rg-support-panel">
      <div class="command__head">
        <p class="command__label">${label}</p>
        ${copyButton(id, "secondary")}
      </div>
      <pre id="${id}" class="command__block" tabindex="0" role="region" aria-label="Command"><code>${escape(lines)}</code></pre>
    </div>`
  })
}

for (const file of readdirSync(join(root, "src/pages"))) {
  const source = readFileSync(join(root, "src/pages", file), "utf8")
  const [, json, rest] = source.match(/^<!-- (\{.*\}) -->\n([\s\S]*)$/)
  const page = JSON.parse(json)
  const values = {
    title: page.title,
    description: page.description,
    main_class: page.main_class,
    docs_current: page.docs ? ' aria-current="page"' : "",
    body: commands(rest, file.replace(/\.html$/, "")),
  }
  const html = layout.replace(/\{\{(\w+)\}\}/g, (_all, key) => values[key])
  const out = join(root, "site", page.out)
  mkdirSync(dirname(out), {recursive: true})
  writeFileSync(out, html)
  console.log(`built ${page.out}`)
}
