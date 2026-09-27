declare module "phoenix_html"

declare module "phoenix" {
  export const Socket: unknown
}

declare module "phoenix_live_view" {
  // The exact surface this application uses from phoenix_live_view 1.2.
  export class LiveSocket {
    constructor(path: string, socket: unknown, options: Record<string, unknown>)
    connect(): void
  }
}

// The renderer the homepage crown's own bundle registers on window, and the
// shape of what it draws with. See optics/crown/index.ts.
type OpticsRenderer = import("./optics/crown/index").PrismRenderer

type OpticsRendererFactory = (
  canvas: HTMLCanvasElement,
  size: readonly [number, number],
  onDeviceLost: () => void,
) => Promise<OpticsRenderer>

// The WebMCP draft's document.modelContext. Browsers without it have no such
// property; public_tools.ts checks `"modelContext" in document` before use.
type ModelContextTool = {
  name: string
  title: string
  description: string
  inputSchema: object
  annotations: object
  execute(input: unknown, client: {signal?: AbortSignal}): Promise<unknown>
}

interface ModelContext {
  registerTool(tool: ModelContextTool, options: {signal: AbortSignal}): Promise<void>
  getTools(): Promise<Array<{name: string}>>
}

interface Document {
  readonly modelContext: ModelContext
}

interface DocumentEventMap {
  "techtree:themechange": CustomEvent<{theme: string; crownVariant: string}>
}

interface Window {
  liveSocket: import("phoenix_live_view").LiveSocket
  TechtreeOptics?: Record<string, OpticsRendererFactory>
}
