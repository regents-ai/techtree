// Manifest-listed public reads and signed requests. A signed tool takes only its input;
// the agent's browser host signs the exact request (window.regentsSign), so no key,
// signature or receipt passes through the page.

import manifest from "../../priv/tool_manifest.json" with {type: "json"}
import {Refused, signedTools, type SignedOperation} from "../vendor/regent_agent_access/signed_tools"
import {report, visitId} from "./visit_log"

function signedTransport() { return signedTools({
  origin: window.location.origin,
  trustedOrigins: [document.querySelector<HTMLMetaElement>('meta[name="agent-request-origin"]')?.content ?? ""],
  audience: manifest.audience,
  proofHeaders: manifest.proof_headers,
  requestHeaders: client,
  // Only the signed tools are operations.
  operations: manifest.tools.filter(entry => entry.authentication === "siwa_per_request") as unknown as SignedOperation[],
}) }


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
  authentication: string
}

// Named fields that passed inputProblem against the tool's schema.
type Input = Record<string, string | number>

type Reply =
  | {ok: true; status: number; data: unknown; verdict?: unknown}
  | {ok: false; status: number; error: unknown}

type Format = "json" | "text" | "exact"

// Each tool reads through its own reader, which names the tool and this visit.
type Request = (input: Input, read: (path: string, format: Format) => Promise<Reply>) => Promise<Reply>

const requests: Record<string, Request> = {
  async techtree_start(_input, read) {
    const [bootstrap, guide] = await Promise.all([
      read("/api/v1/bootstrap", "json"),
      read("/agents.md", "text"),
    ])
    if (!bootstrap.ok) return bootstrap
    if (!guide.ok) return guide
    return {ok: true, status: 200, data: {bootstrap: bootstrap.data, installation_guide: guide.data}}
  },
  techtree_climbs: (_input, read) => read("/api/v1/catalog", "json"),
  techtree_climb: (input, read) => read(`/api/v1/climbs/${encodeURIComponent(input.slug)}`, "json"),
  techtree_results: (input, read) => {
    const query = Object.entries(input).map(([key, value]) => [key, String(value)])
    return read(`/api/v1/publications?${new URLSearchParams(query)}`, "json")
  },
  async techtree_result(input, read) {
    const response = await read(`/api/v1/publications/${input.bundle_digest}`, "json")
    return response.ok
      ? {...response, verdict: (response.data as {decision: unknown}).decision}
      : response
  },
  results_bundle: (input, read) =>
    read(`/api/v1/publications/${encodeURIComponent(input.bundle_digest)}/bundle`, "exact"),
  skills_show: (input, read) => read(`/api/v1/skills/${encodeURIComponent(input.root_digest)}`, "json"),
  wallet_bench_list: (_input, read) => read("/wallet-bench.json", "json"),
  wallet_bench_show: (input, read) => read(`/wallet-bench/${encodeURIComponent(input.id)}/results.json`, "json"),
}

// Every call names its tool and this visit, so the site's log can put the call
// beside the rest of the visit (TechtreeWeb.VisitLog). Neither is a credential.
function client(tool: string): Record<string, string> {
  const visit = visitId()
  return {"x-regent-client": `webmcp/${tool}`, ...(visit && {"x-regent-visit": visit})}
}

// "json" answers the parsed JSON, "text" a Markdown document, and "exact" a JSON
// answer's own bytes as text, unparsed, so a signed bundle keeps every byte.
async function read(tool: string, path: string, format: Format, signal: AbortSignal | undefined): Promise<Reply> {
  const response = await fetch(path, {
    headers: {Accept: format === "text" ? "text/markdown" : "application/json", ...client(tool)},
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    signal,
  })
  if (response.ok) {
    const data: unknown = format === "json" ? await response.json() : await response.text()
    return {ok: true, status: response.status, data}
  }
  const body: unknown = format === "text" ? await response.text() : await response.json()
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
    if (entry.authentication === "siwa_per_request") {
      try {
        const response = await signedTransport().execute(entry.name, input as Record<string, unknown>, signal)
        const data = await response.json()
        return response.ok ? {ok: true, status: response.status, data} : {ok: false, status: response.status, error: data.error}
      } catch (error) {
        // No agent signer, a signer that failed or said no, or a call cancelled while
        // it signed: nothing was sent, and the refusal has the words for the agent.
        if (error instanceof Refused) return {ok: false, error: error.refusal}
        return {ok: false, error: {code: "signed_request_failed", message: String(error),
          hint: "Check the input against this tool's schema, then call the tool again. Browser cookies grant no agent authority."}}
      }
    }
    const problem = inputProblem(input, entry.input_schema)
    if (problem) return {ok: false, error: {code: "invalid_input", message: problem}}
    try {
      return await requests[entry.name](input as Input, (path, format) => read(entry.name, path, format, signal))
    } catch (_error) {
      if (signal?.aborted) return {ok: false, error: {code: "cancelled", message: "The read was cancelled; nothing changed."}}
      // The site never heard it, so the page reports it.
      report({name: "tool.unsent", where: entry.name, outcome: "unreachable"})
      return {ok: false, error: {code: "unreachable", message: "Techtree's public API could not be read. Try again."}}
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
  window.addEventListener("pagehide", () => registration?.abort())
}
