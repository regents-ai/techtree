// Serves site/ at http://localhost:4015. A folder answers with its index.html.
import {createServer} from "node:http"
import {readFile, stat} from "node:fs/promises"
import {dirname, extname, join, normalize} from "node:path"

const site = join(dirname(new URL(import.meta.url).pathname), "site")
const port = Number(process.env.PORT || 4015)
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".woff2": "font/woff2",
}

createServer(async (request, response) => {
  const path = normalize(decodeURIComponent(new URL(request.url, "http://localhost").pathname))
  let file = join(site, path)
  if (!file.startsWith(site)) return response.writeHead(403).end()
  try {
    if ((await stat(file)).isDirectory()) {
      if (!path.endsWith("/")) return response.writeHead(301, {location: `${path}/`}).end()
      file = join(file, "index.html")
    }
    const body = await readFile(file)
    response.writeHead(200, {"content-type": types[extname(file)] || "application/octet-stream", "cache-control": "no-store"})
    response.end(body)
  } catch {
    response.writeHead(404, {"content-type": "text/plain"}).end("Not part of the mockup")
  }
}).listen(port, "127.0.0.1", () => console.log(`Mockups at http://localhost:${port}/`))
