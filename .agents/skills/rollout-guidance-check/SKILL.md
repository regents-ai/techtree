---
name: rollout-guidance-check
description: Check whether a Regent code change needs matching updates to human-facing copy, tooltips, product Skills, agent instructions, WebMCP descriptions, API contracts, CLI help or rollout guides. Use during implementation and release review; report source, packaged and deployed drift separately.
---

# Check guidance when code changes

Review the instructions a person or agent will actually encounter after this change.
Done means every affected surface is updated, explicitly unchanged for a stated reason,
or recorded as a release dependency. A passing search or generated file is not proof
that the advice works.

This is a developer skill. It does not belong in a product's agent-use Skill or grant
permission to execute the instructions being reviewed. Default to read-only review;
edit only when the user's task authorizes fixes. Do not activate earning or spending,
sign requests, publish, deploy, run migrations or contact third parties as a check.

## Establish the version and the change

1. Read the repository/workspace instructions and identify the exact base and target
   commits, working edits, affected packages and intended rollout stage. Preserve
   other agents' changes. A primary checkout may be older than the release branch.
2. Explain the observable behavior change: inputs, outputs, permissions, side effects,
   limits, money, timing, retries, errors, availability or installation. Include removed
   behavior. A dependency pin can change any of these without changing the host's code.
3. Keep four versions distinct: source under review, bundled client/contract, published
   client, and deployed service. Runtime support is a separate fact. Never mark a
   source-only fix live, or a listed WebMCP tool successfully executed.

Use [the surface map](references/surface-map.md) to locate the owners and generators.
Shared behavior lands in the library and ash-template first; products adopt the
template. Regents is one consumer, not the baseline.

## Find all affected surfaces

Refresh the file index when the repository layout or relevant files change:

```sh
uv run --no-project --no-config --no-env-file --offline python scripts/inventory.py --workspace /absolute/regent --output /absolute/review-output
```

For a specific checkout or a standalone reviewer environment:

```sh
uv run --no-project --no-config --no-env-file --offline python scripts/inventory.py --workspace /absolute/regent \
  --repo /absolute/checkout --ref COMMIT --no-working-overlay --output /absolute/review-output
```

Run from this skill's directory or use its script's absolute path. These commands use
an already installed Python through uv, without loading project configuration.
Where repository rules permit and uv is unavailable, the standard-library-only helper
can also run with Python 3.10 or newer directly. Default scans use
local `origin/main` snapshots (HEAD when absent) plus explicitly distinguished current
checkout differences, including committed changes and working edits. Explicit missing
revisions fail instead of substituting HEAD. For release review, pass the actual target
checkout/ref with `--no-working-overlay`; the default scan is
not a release inventory. Use a new or empty output directory outside scanned sources
for each run; previous reports are preserved rather than overwritten or mixed with a
new selection. Supply real directory paths, not symlinks. The script
never fetches, executes repository code or follows external symlink targets. It excludes
known private filenames (including `.env*` except `.env.example`), credential locations
and key extensions before reading content. Ordinary source configuration is eligible,
but filename rules can conservatively exclude policy/example files too; those recorded
boundaries remain manual-review work. Source/prose names containing words such as
“credentials” are not automatically secrets; inspect only suitable source roots.
The exact filename denylist is in `exclusion()`; this is not a secret scanner.
Filename exclusions cannot detect secrets stored under arbitrary names, so select only
source roots suitable for review. Git-ignored untracked paths are recorded as unreviewed
boundaries without reading them; excluded directory trees may have one boundary row.
Default repository discovery honors the workspace's Git ignores. An explicit `--repo`
selects that repository independently of parent-workspace ignores; its own overlay
still honors its Git ignores, while the requested commit is a separate source snapshot.
Current unverified boundaries remain in the overlay even when equality cannot be
checked; the overlay path count is not an exact changed-file count.
Staged differences from HEAD are separately listed as unreviewed `index_overlay`
boundaries; the separate index's content is not read. Eligible working files are
still read, including when their bytes also happen to be staged. Non-Git loose documentation and Skill roots
bypass text-search ignore files, so select only suitable source roots.
The expected-root list covers repository containers from the surface map, not every
module path inside a repository. Inspect affected source paths separately.
Inspect `coverage.json`: excluded,
oversized, binary, unknown text and unavailable repositories cannot silently become
“checked.” The full CSV/JSONL includes candidates and exclusions, not just regex hits.

Use `git diff --name-status BASE HEAD`, changed identifiers and old/new words to search
the index and source with `rg`. Follow callers, shared pins, route renderers, generators,
copy buttons and packaged consumers. Then apply [the impact checklist](references/impact-checklist.md).
Semantic changes often have no matching old string: inspect the owning UI and tool
descriptions even if text search finds nothing.

Cover these classes, recording a reason when unaffected:

- Public guides, docs, About/help pages, legal/price/limit copy and discovery indexes.
- Visible UI text, tooltips, labels, placeholders, disabled reasons, empty/loading/error
  states, accessibility labels, dialogs, notices and emails.
- Human-to-agent handoffs, pairing/start instructions, copyable commands and prompts.
- Product-use Skills and their references, examples and assets; separately, developer
  Skills, AGENTS/CLAUDE instructions and generated dependency usage rules.
- WebMCP names/descriptions/schemas/annotations, page-specific tool registration,
  hosted MCP tools, plugin descriptions and capability/availability declarations.
- CLI command descriptions, `--help`, arguments, defaults, examples, install/version
  pins, shell completions, doctor checks, refusals and `next_steps`.
- OpenAPI/JSON schemas, operation IDs, response/error contracts and bundled copies.
- SDK/package docs, module docs/docstrings/NatSpec, examples and configuration examples.
- Release instructions, migrations/prerequisites, supported-host limitations and
  versioned acceptance records. Historical records retain their dated truth.
- Generated/static outputs and vendored first-party assets, including their source
  generator, build command and client packaging step.
- Runtime-authored content: identify its rendering and data owner; do not dump private
  database content. Record any published material that cannot be inspected here.

## Decide and verify

For each affected surface, trace **implementation → authored description → generator/
package → public route or command → consumer**. Read the relevant source; pattern hits
alone are insufficient. Record its owner, path/line, expected behavior and disposition:
`update required`, `already consistent`, `generated refresh required`, `pending release`,
`historical—retain`, or `blocked` with the precise missing evidence.

Check promises about authority, pairing, wallet identity, spending, refunds, Points,
idempotency, retries, rate limits and gates particularly closely. A harmless read must
not be described as a mutation; a tool that spends or publishes must not claim to be
read-only. A browser tool must not silently borrow a person's session as agent authority.
Do not infer activation from deployed code or “available” from a manifest entry.

Validate commands against the actual published/bundled client and target service contract.
Check stdin/file forms, required fields, quoting, defaults and expected errors. Never
validate by pasting a secret/code into a command or performing a consequential action.
Inspect existing contract/generation checks before running them; use bounded non-mutating
checks. If meaningful execution requires sign-in or a payment, record the unverified
step and the authority needed, rather than claiming it passed.

Generated output is corrected at its source, then regenerated through the existing tool.
Do not create another manifest, repair generated copies by hand, or globally replace
version numbers in historical evidence. One CLI version update must also reconcile its
source revision, artifact hash and command availability wherever those are published.

For a source review, a pending release is an explicit dependency, not automatically a
code defect. For a post-release check, inspect the actual public route/installed command
and report stale behavior as deployed drift. Note when only source was available.

## Review result

Lead with concrete findings, each with a file/line, the user/agent action that goes wrong,
evidence, and the smallest correction. Separate wrong instructions, missing rollout work,
and unverified behavior. Do not request cosmetic rewrites or label unchanged historical
records broken merely because they mention an old release.

Include a compact coverage table: surface, owner/source, disposition and verification.
List exact reviewed revisions, unavailable surfaces, generated outputs to refresh, client
release dependencies and post-deployment checks. An empty finding list is not blanket
clearance: say what was actually covered and what was not.

For hosted OpenAI code review, read [the integration notes](references/openai-review.md).
Use the repository's packaged Skill and immutable PR diff; do not assume the review
environment has Sean's workspace, sibling repositories or live access. Report missing
evidence explicitly. Repository instructions do not enable automatic review by themselves.
