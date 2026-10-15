# Change-to-guidance checks

Use the rows that match the actual diff; inspect other relevant classes even if the
diff never touches prose. This is an impact guide, not a second operation registry.

| Changed behavior | Trace through |
|---|---|
| Endpoint, operation name, path or field | Router/controller/action → OpenAPI → manifest/capabilities → site `cli/commands.json` and `COMMANDS.md` → bundled CLI contracts → help/examples → public guides and copy buttons |
| Actor, pairing, membership, ownership or wallet rule | Policy/actor construction → shared refusal → UI disabled reason → start/pair handoff → tool authority and availability → CLI refusal/next step → Skills and recovery docs |
| Credits price, reservation, refund or budget | Accounting source → shared UI labels/help → tool effect/payment metadata → confirmation/purchase/refund explanations → CLI prompts/retry advice → accounting guide. Activation is a distinct decision. |
| Points rate, milestone, allowance or eligibility | Catalog/version and committed evidence producer → source adapter → account display → explanatory tooltips/guide/Skill → capability notes. Check account-wide attribution and original event/rule snapshots; do not activate earning. |
| Error, timeout, retry or idempotency | Status/code/payload → browser error UI → CLI error mapping/next_steps → manifest error schema → recovery docs. Repeating a payment is not a generic retry. |
| CLI option, argument, output or release | Parser/descriptor → generated help/completion → output/JSON contract → docs/examples → product handoff strings → installation pin/hash/source commit → bundled site descriptors |
| Dependency or shared component pin | Diff the pinned package → template integration → each relevant consumer → copied/generated assets → visible words/behavior → published client/service versions |
| Tool schema or registration | Manifest → runtime registration/page scope → input validation → descriptions/annotations → generated capability listing → OpenAPI/CLI mapping → native-host limitation wording |
| UI interaction, empty/loading state or navigation | LiveView/component/hook/Swift view → tooltip/ARIA text → docs screenshots or examples → copyable agent prompt → stale state/session behavior |
| Feature gate or launch state | Server gate → public discovery/index → each tool's availability → CLI doctor/refusal → public guide. Preparing or listing a request must not imply executing it is allowed. |
| Migration, data shape or configuration | Migration and minimum schema version → release order → startup/health messages → configuration example → operators' current runbook. Never rewrite old execution evidence as a new result. |
| Authentication/signing protocol | SIWA-owned specification/signer → server verifier → shared site adapter → CLI handshake/proof transport → browser preparation helper → recovery and install guides. Product docs link the maintained protocol source. |
| Product-use or developer Skill | Correct source Skill and references → public serving allowlist or installed alias → packaged plugin copy → actual commands/versions. Keep developer and customer instructions distinct. |

## Small representative evaluations

Use bounded cases to validate the checker itself, without exercising a live product:

- Change a required JSON field while leaving a CLI descriptor and copy-button example
  unchanged. A useful review finds both consumers, not only the OpenAPI edit.
- Change a server error from retryable to terminal after a charge. A useful review
  traces the CLI's recovery instructions and does not recommend another charge.
- Publish a new client while retaining a dated old acceptance transcript. A useful
  review updates current onboarding when necessary but preserves the transcript.
- Re-pin a shared component that changes a tooltip or budget interpretation. A useful
  review checks template and consumers even if no local Markdown changed.
- Remove signer support from a runtime. A useful review distinguishes native execution
  from tool listing and names the limitation without inventing a cookie fallback.
