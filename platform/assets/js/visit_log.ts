// The few visit lines only the browser can see (TechtreeWeb.VisitLogController):
// a script error, a page tool's call that got no answer, a wallet press that
// never reached the site, and a press on a Sign in button. They wait together and go in one post when the page is
// hidden or five seconds after the first, at most 20 at a time. Nothing else
// about the page is sent: an error is named by its page alone, never its message.

export type VisitLine =
  | {name: "page.error"; where: string; outcome: "error" | "unhandledrejection"}
  | {name: "tool.unsent"; where: string; outcome: "unreachable" | "outcome_unknown"}
  | {name: "press.unsent"; where: string; outcome: "lost"}
  | {name: "step"; where: "sign_in_opened"}

const most = 20
const waiting: VisitLine[] = []
let timer: number | undefined

/** This visit's id, from the page's `regent-visit` tag, for the page's own tool calls. */
export function visitId(): string | undefined {
  return document.querySelector<HTMLMetaElement>('meta[name="regent-visit"]')?.content || undefined
}

export function report(line: VisitLine): void {
  if (waiting.length >= most) return
  waiting.push(line)
  timer ??= window.setTimeout(send, 5000)
}

function send(): void {
  window.clearTimeout(timer)
  timer = undefined
  if (!waiting.length) return
  const csrf = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? ""
  // keepalive lets the post finish after the page has gone. A post that fails is
  // let go: reporting it would only queue another.
  fetch("/visit-log", {
    method: "POST",
    keepalive: true,
    credentials: "same-origin",
    headers: {"content-type": "application/json", "x-csrf-token": csrf},
    body: JSON.stringify({lines: waiting.splice(0)}),
  }).catch(() => undefined)
}

export function installVisitLog(): void {
  window.addEventListener("error", () =>
    report({name: "page.error", where: window.location.pathname, outcome: "error"}))
  window.addEventListener("unhandledrejection", () =>
    report({name: "page.error", where: window.location.pathname, outcome: "unhandledrejection"}))
  // Any Sign in button, wherever a page draws one (auth_lazy.ts opens the sign-in).
  document.addEventListener("click", event => {
    if (event.target instanceof Element && event.target.closest("[data-account-target='sign-in']"))
      report({name: "step", where: "sign_in_opened"})
  })
  window.addEventListener("pagehide", send)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") send()
  })
}
