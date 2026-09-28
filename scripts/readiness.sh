#!/usr/bin/env bash
# Checks what the "is-agentic" agent-readiness scorer looks for, against this
# checkout's own server on localhost, so every site is measured the same way.
#
#   scripts/readiness.sh
#
# Starts the development server on a free port with the error debugger off, so
# errors answer as they do in a release, runs the checks, then stops the server.
# The first run compiles the dependencies into _build/readiness, which takes a
# few minutes; later runs reuse it.
# Needs the local development database (see platform/README.md) for /healthz.
# The rate-limit check runs last: it spends the client's whole budget.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root/platform"

port="$(node -e 'const s = require("net").createServer().listen(0, "127.0.0.1", () => { console.log(s.address().port); s.close() })')"
base="http://127.0.0.1:$port"
log="_build/readiness-server.log"
mkdir -p _build

# The debugger switch is read when the endpoint compiles, so the readiness server
# builds into its own folder and leaves the everyday development build as it is.
PORT="$port" TECHTREE_DEBUG_ERRORS=off MIX_BUILD_PATH=_build/readiness mix phx.server >"$log" 2>&1 &
server=$!

stop_server() {
  kill "$server" 2>/dev/null || true
  wait "$server" 2>/dev/null || true
}
trap stop_server EXIT

echo "==> Starting the server on $base"
for _ in $(seq 600); do
  if curl --silent --output /dev/null "$base/robots.txt"; then break; fi
  if ! kill -0 "$server" 2>/dev/null; then
    echo "The server stopped before answering; its log:" >&2
    tail -n 40 "$log" >&2
    exit 1
  fi
  sleep 1
done

node --input-type=module - "$base" <<'CHECKS'
const base = process.argv[2];
const pages = ["/", "/docs", "/about", "/contact", "/privacy", "/terms"];
let failed = 0;

const check = (name, ok, detail = "") => {
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${name}${ok || !detail ? "" : `  (${detail})`}`);
  if (!ok) failed += 1;
};

const get = async (path, accept) => {
  const response = await fetch(base + path, {
    headers: accept ? { accept } : {},
    redirect: "manual",
  });
  return { status: response.status, headers: response.headers, body: await response.text() };
};

const type = (answer) => (answer.headers.get("content-type") || "").split(";")[0].trim();
const varyAccept = (answer) =>
  (answer.headers.get("vary") || "").toLowerCase().split(",").map((v) => v.trim()).includes("accept");
const parses = (text) => {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};
const limited = (answer) =>
  /^"[^"]+";q=\d+;w=\d+/.test(answer.headers.get("ratelimit-policy") || "") &&
  /^"[^"]+";r=\d+;t=\d+/.test(answer.headers.get("ratelimit") || "");
const cached = (answer) =>
  /^"[0-9a-f]{64}"$/.test(answer.headers.get("etag") || "") &&
  (answer.headers.get("cache-control") || "").includes("public");

console.log("Public pages: HTML and Markdown at one address, with Vary: Accept");
for (const path of pages) {
  const html = await get(path, "text/html");
  const md = await get(path, "text/markdown");
  check(`${path} as HTML`, html.status === 200 && type(html) === "text/html" && varyAccept(html),
    `${html.status} ${type(html)} vary=${html.headers.get("vary")}`);
  check(`${path} as Markdown`, md.status === 200 && type(md) === "text/markdown" && varyAccept(md) && md.body.startsWith("# "),
    `${md.status} ${type(md)} vary=${md.headers.get("vary")}`);
}

console.log("Head metadata on the home page");
const home = await get("/", "text/html");
const ld = [...home.body.matchAll(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map((m) => parses(m[1]));
check("JSON-LD parses", ld.length > 0 && ld.every(Boolean), `${ld.length} blocks`);
const graph = ld.flatMap((doc) => (doc && doc["@graph"]) || (doc ? [doc] : []));
check("JSON-LD names an Organization and a WebSite",
  ["Organization", "WebSite"].every((kind) => graph.some((node) => node["@type"] === kind)));
check("JSON-LD carries no postal address", !JSON.stringify(ld).includes('"address"'));
const siteType = home.body.match(/<meta[^>]*name="is-agentic-site-type"[^>]*content="([^"]+)"/);
check("site type is declared", Boolean(siteType), "no is-agentic-site-type meta");
if (siteType) console.log(`        site type: ${siteType[1]}`);

console.log("Errors: HTML, Markdown and JSON 404s");
const missing = "/readiness-no-such-page";
const e404 = [
  [missing, "text/html", "text/html"],
  [missing, "text/markdown", "text/markdown"],
  [missing, "application/json", "application/json"],
  ["/api/readiness-no-such-route", "text/html", "application/json"],
];
for (const [path, accept, expected] of e404) {
  const answer = await get(path, accept);
  const body = expected === "application/json" ? parses(answer.body) : null;
  const shaped = expected !== "application/json" ||
    (body && body.error && ["code", "message", "hint"].every((key) => typeof body.error[key] === "string"));
  check(`${path} asked as ${accept} answers 404 ${expected}`,
    answer.status === 404 && type(answer) === expected && shaped, `${answer.status} ${type(answer)}`);
}

console.log("OpenAPI description");
const openapiAnswer = await get("/openapi.json");
const openapi = parses(openapiAnswer.body);
check("/openapi.json parses as OpenAPI 3", Boolean(openapi && /^3\./.test(openapi.openapi)));
check("/openapi.json is cached with an ETag", cached(openapiAnswer));
const operations = Object.entries((openapi && openapi.paths) || {}).flatMap(([path, item]) =>
  Object.entries(item)
    .filter(([method]) => ["get", "put", "post", "patch", "delete"].includes(method))
    .map(([method, operation]) => ({ path, method, operation })));
const ids = operations.map(({ operation }) => operation.operationId);
check("every operation has a unique operationId", ids.every(Boolean) && new Set(ids).size === ids.length);
check("externalDocs points at the developer documentation", Boolean(openapi && openapi.externalDocs && openapi.externalDocs.url));
const resolve = (object) => {
  let node = object;
  while (node && node.$ref) node = node.$ref.slice(2).split("/").reduce((at, key) => at && at[key], openapi);
  return node;
};
for (const { path, method, operation } of operations) {
  const responses = operation.responses || {};
  const errors = Object.entries(responses).filter(([status]) => /^[45]/.test(status) || status === "default");
  const untyped = errors.filter(([, response]) => {
    const content = (resolve(response) || {}).content || {};
    return !Object.values(content).some((media) => media.schema);
  }).map(([status]) => status);
  check(`${method.toUpperCase()} ${path}: every error response has a schema`, untyped.length === 0, `untyped: ${untyped.join(", ")}`);
  check(`${method.toUpperCase()} ${path}: declares a default response`, Boolean(responses.default));
  const tooMany = resolve(responses["429"]);
  check(`${method.toUpperCase()} ${path}: declares 429 with Retry-After and RateLimit headers`,
    Boolean(tooMany && tooMany.headers && ["Retry-After", "RateLimit", "RateLimit-Policy"].every((h) => tooMany.headers[h])));
  const success = Object.entries(responses).find(([status]) => /^2/.test(status));
  check(`${method.toUpperCase()} ${path}: declares RateLimit headers on success`,
    Boolean(success && (resolve(success[1]).headers || {})["RateLimit"]));
  if (method === "get") {
    const answer = await get(path, "application/json");
    const served = path === "/healthz" ? answer.status === 200 : answer.status !== 404 && answer.status < 500;
    check(`GET ${path} is served`, served, `${answer.status}`);
  }
}

console.log("Rate-limit headers");
for (const path of ["/healthz", "/api/v1/profile", "/api/readiness-no-such-route"]) {
  const answer = await get(path, "application/json");
  check(`${path} answers with RateLimit-Policy and RateLimit`, limited(answer),
    `${answer.headers.get("ratelimit-policy")} / ${answer.headers.get("ratelimit")}`);
}

console.log("Discovery files");
const sitemap = await get("/sitemap.xml");
const urls = [...sitemap.body.matchAll(/<url>([\s\S]*?)<\/url>/g)].map((m) => m[1]);
check("/sitemap.xml lists the public pages", sitemap.status === 200 && urls.length >= pages.length, `${urls.length} entries`);
check("every sitemap entry has an ISO 8601 lastmod",
  urls.length > 0 && urls.every((entry) => /<lastmod>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})<\/lastmod>/.test(entry)));
const robots = await get("/robots.txt");
check("/robots.txt names the sitemap", robots.status === 200 && /^Sitemap: https?:\/\/\S+\/sitemap\.xml$/m.test(robots.body));
check("/robots.txt is cached with an ETag", cached(robots));
const llms = await get("/llms.txt");
check("/llms.txt is a Markdown guide with a title", llms.status === 200 && type(llms) === "text/plain" && llms.body.startsWith("# "));
check("/llms.txt links the docs and the OpenAPI description", llms.body.includes("/docs") && llms.body.includes("/openapi.json"));
check("/llms.txt is cached with an ETag", cached(llms));
const docs = await get("/docs", "text/markdown");
for (const heading of ["Errors", "Rate limits", "Versioning and deprecation"]) {
  check(`/docs has a "${heading}" section`, new RegExp(`^## ${heading}$`, "m").test(docs.body));
}
const security = await get("/.well-known/security.txt");
const expires = security.body.match(/^Expires: (.+)$/m);
const expiresAt = expires ? Date.parse(expires[1]) : NaN;
check("/.well-known/security.txt has Contact and a future Expires",
  security.status === 200 && type(security) === "text/plain" && /^Contact: \S+$/m.test(security.body) &&
  expiresAt > Date.now() && expiresAt < Date.now() + 367 * 24 * 3600 * 1000);
const catalogAnswer = await get("/.well-known/api-catalog");
const catalog = parses(catalogAnswer.body);
check("/.well-known/api-catalog is a linkset naming /openapi.json",
  catalogAnswer.status === 200 && type(catalogAnswer) === "application/linkset+json" &&
  Boolean(catalog && catalog.linkset && catalog.linkset.some((entry) =>
    (entry["service-desc"] || []).some((link) => link.href.endsWith("/openapi.json")))));

console.log("Browser tools (WebMCP)");
for (const path of pages) {
  const answer = await get(path, "text/html");
  const policy = (answer.headers.get("permissions-policy") || "").split(",").map((v) => v.trim());
  check(`${path} sends Permissions-Policy: tools=(self)`, policy.includes("tools=(self)"),
    `permissions-policy=${answer.headers.get("permissions-policy")}`);
}
const manifestAnswer = await get("/capabilities");
const manifest = parses(manifestAnswer.body);
const tools = (manifest && Array.isArray(manifest.tools)) ? manifest.tools : [];
check("/capabilities serves the tool manifest as JSON",
  manifestAnswer.status === 200 && type(manifestAnswer) === "application/json" && tools.length > 0,
  `${manifestAnswer.status} ${type(manifestAnswer)} ${tools.length} tools`);
check("/capabilities is cached with an ETag", cached(manifestAnswer));
const names = tools.map((tool) => tool.name);
const hints = ["readOnlyHint", "untrustedContentHint", "consequentialHint", "debugging"];
check("every tool name is unique and 1-128 of A-Z a-z 0-9 _ . -",
  names.every((name) => /^[A-Za-z0-9_.-]{1,128}$/.test(name)) && new Set(names).size === names.length,
  names.join(", "));
for (const tool of tools) {
  const schema = tool.input_schema || {};
  check(`tool ${tool.name}: title, description, a closed object schema and WebMCP annotations only`,
    Boolean(tool.title) && Boolean(tool.description) && schema.type === "object" &&
    schema.additionalProperties === false && Array.isArray(schema.required) &&
    Object.keys(tool.annotations || {}).every((hint) => hints.includes(hint)) &&
    ["requires", "route", "scope"].every((key) => typeof tool[key] === "string"));
}
// The page's script registers every manifest entry whose scope is "site", from
// the copy of the manifest bundled into it: that copy must name the same tools.
const siteNames = tools.filter((tool) => tool.scope === "site").map((tool) => tool.name);
const script = home.body.match(/<script[^>]*src="(\/assets\/js\/site[^"]*\.js)"/);
const bundle = script ? (await get(script[1])).body : "";
const bundledSite = (bundle.match(/scope:\s*"site"/g) || []).length;
check(`the page's script registers the manifest's site tools: ${siteNames.join(", ")}`,
  bundle.includes("registerTool") && bundledSite === siteNames.length &&
  siteNames.every((name) => bundle.includes(JSON.stringify(name))),
  script ? `${bundledSite} site tools bundled` : "no site.js script tag on /");
const tableNames = (text) => [...text.matchAll(/^\| `([^`]+)` \|/gm)].map((m) => m[1]);
const same = (listed) => listed.length === names.length && names.every((name) => listed.includes(name));
check("/docs lists exactly the manifest's tools", same(tableNames(docs.body)), tableNames(docs.body).join(", "));
const docsHtml = await get("/docs", "text/html");
check("/docs shows the tools as a table",
  names.every((name) => docsHtml.body.includes(`<td><code>${name}</code></td>`)));
check("/llms.txt lists exactly the manifest's tools", same(tableNames(llms.body)), tableNames(llms.body).join(", "));
check("/llms.txt links the tool manifest", llms.body.includes("/capabilities"));

console.log("Past the budget");
let last;
for (let i = 0; i < 1000; i += 1) {
  last = await get("/healthz");
  if (last.status === 429) break;
}
const refusal = parses(last.body);
check("a client past its budget gets 429 with Retry-After and a JSON error",
  last.status === 429 && /^\d+$/.test(last.headers.get("retry-after") || "") && limited(last) &&
  Boolean(refusal && refusal.error && refusal.error.code === "too_many_requests"),
  `${last.status} retry-after=${last.headers.get("retry-after")}`);

console.log(failed === 0 ? "\nReadiness: every check passed." : `\nReadiness: ${failed} check(s) failed.`);
process.exit(failed === 0 ? 0 : 1);
CHECKS
