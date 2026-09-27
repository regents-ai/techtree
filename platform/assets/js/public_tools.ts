// The read-only tools every page offers a browser's own agent (WebMCP draft,
// document.modelContext). priv/tool_manifest.json describes each tool once;
// this file only adds the public request behind it. Nothing here signs in,
// writes or spends: publishing stays with the CLI and its key.

import manifest from "../../priv/tool_manifest.json" with {type: "json"}

type Property =
  | {type: "integer"; minimum: number; maximum?: number; description: string}
  | {type: "string"; minLength?: number; maxLength?: number; pattern?: string; description: string}

type Schema = {
  type: "object"
  properties: Record<string, Property>
  required: string[]
  dependentRequired?: Record<string, string[]>
  additionalProperties: false
}

type Entry = {
  name: string
  title: string
  description: string
  input_schema: Schema
  annotations: {readOnlyHint: boolean; untrustedContentHint: boolean}
  scope: string
}

// Named fields that passed inputProblem against the tool's schema.
type Input = Record<string, string | number>

type Reply =
  | {ok: true; status: number; data: unknown; verdict?: unknown}
  | {ok: false; status: number; error: unknown}

type Request = (input: Input, signal: AbortSignal | undefined) => Promise<Reply>

const requests: Record<string, Request> = {
  async techtree_start(_input, signal) {
    const [bootstrap, guide] = await Promise.all([
      read("/api/v1/bootstrap", "json", signal),
      read("/skill.md", "text", signal),
    ])
    if (!bootstrap.ok) return bootstrap
    if (!guide.ok) return guide
    return {ok: true, status: 200, data: {bootstrap: bootstrap.data, installation_guide: guide.data}}
  },
  techtree_climbs: (_input, signal) => read("/api/v1/catalog", "json", signal),
  techtree_climb: (input, signal) =>
    read(`/api/v1/climbs/${encodeURIComponent(input.slug)}`, "json", signal),
  techtree_results: (input, signal) => {
    const query = Object.entries(input).map(([key, value]) => [key, String(value)])
    return read(`/api/v1/publications?${new URLSearchParams(query)}`, "json", signal)
  },
  async techtree_result(input, signal) {
    const response = await read(`/api/v1/publications/${input.bundle_digest}`, "json", signal)
    return response.ok
      ? {...response, verdict: (response.data as {decision: unknown}).decision}
      : response
  },
}

async function read(path: string, format: "json" | "text", signal: AbortSignal | undefined): Promise<Reply> {
  const response = await fetch(path, {
    headers: {Accept: format === "json" ? "application/json" : "text/markdown"},
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    signal,
  })
  const body: unknown = format === "json" ? await response.json() : await response.text()
  if (response.ok) return {ok: true, status: response.status, data: body}
  return {ok: false, status: response.status, error: (body as {error?: unknown}).error ?? {message: body}}
}

// The browser does not check input against the schema, so each call is
// checked here, and a refusal names the field and what it must be.
function inputProblem(input: unknown, schema: Schema) {
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    return "Send an object of named fields."
  }
  const unknown = Object.keys(input).find(key => !Object.hasOwn(schema.properties, key))
  if (unknown) {
    const fields = Object.keys(schema.properties)
    return fields.length
      ? `${unknown} is not a field of this tool; its fields are ${fields.join(", ")}.`
      : `${unknown} is not a field of this tool; it takes none.`
  }
  const missing = schema.required.find(key => !Object.hasOwn(input, key))
  if (missing) return `${missing} is required.`
  for (const [key, needed] of Object.entries(schema.dependentRequired ?? {})) {
    const absent = Object.hasOwn(input, key) && needed.find(other => !Object.hasOwn(input, other))
    if (absent) return `${key} is sent together with ${absent}.`
  }
  for (const [key, value] of Object.entries(input)) {
    const problem = valueProblem(key, value, schema.properties[key])
    if (problem) return problem
  }
  return null
}

function valueProblem(key: string, value: unknown, property: Property) {
  if (property.type === "integer") {
    const within = typeof value === "number" && Number.isSafeInteger(value) && value >= property.minimum &&
      (property.maximum === undefined || value <= property.maximum)
    if (within) return null
    return property.maximum === undefined
      ? `${key} must be a whole number of at least ${property.minimum}.`
      : `${key} must be a whole number from ${property.minimum} to ${property.maximum}.`
  }
  if (typeof value !== "string" || value.length < (property.minLength ?? 0) || value.length > (property.maxLength ?? Infinity)) {
    return `${key} must be text of ${property.minLength} to ${property.maxLength} characters.`
  }
  if (property.pattern && !new RegExp(property.pattern).test(value)) {
    return `${key} does not have the right form. ${property.description}`
  }
  return null
}

// JSON imports widen every literal, so the manifest is read as the shape it is written in.
const entries = manifest.tools as unknown as Entry[]

const tools: ModelContextTool[] = entries.filter(entry => entry.scope === "site").map(entry => ({
  name: entry.name,
  title: entry.title,
  description: entry.description,
  inputSchema: entry.input_schema,
  annotations: entry.annotations,
  async execute(input: unknown, {signal}: {signal?: AbortSignal}) {
    const problem = inputProblem(input, entry.input_schema)
    if (problem) return {ok: false, error: {code: "invalid_input", message: problem}}
    try {
      return await requests[entry.name](input as Input, signal)
    } catch (_error) {
      return signal?.aborted
        ? {ok: false, error: {code: "cancelled", message: "The read was cancelled; nothing changed."}}
        : {ok: false, error: {code: "unreachable", message: "Techtree's public API could not be read. Try again."}}
    }
  },
}))

// One registration per shown page: register on pageshow, remove on pagehide,
// so a page restored from the back/forward cache never holds two sets. The
// html element's data-webmcp-status says whether the browser holds them all;
// only the latest registration writes it.
export function installPublicTools(): void {
  const status = document.documentElement.dataset
  if (!("modelContext" in document)) {
    status.webmcpStatus = "unsupported"
    return
  }
  let registration: AbortController | undefined

  window.addEventListener("pageshow", () => {
    const current = new AbortController()
    registration = current
    const {signal} = current
    Promise.all(tools.map(tool => document.modelContext.registerTool(tool, {signal})))
      .then(() => document.modelContext.getTools())
      .then(held => {
        if (registration !== current) return
        const names = new Set(held.map(tool => tool.name))
        status.webmcpStatus = tools.every(tool => names.has(tool.name)) ? "connected" : "error"
      })
      .catch((error: unknown) => {
        current.abort()
        if (registration !== current) return
        status.webmcpStatus = "error"
        console.warn("Techtree's browser tools could not be offered.", error)
      })
  })
  window.addEventListener("pagehide", () => registration!.abort())
}
