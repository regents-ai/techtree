# Docs

Install the released CLI, test a Skill against no Skill or its earlier version, verify a Result, and publish a Climb Result to the public Results log. Reading anything here needs no account.

## Install and check this machine

The [agent installation guide](/skill.md) names the exact release to install and every step after it. The [bootstrap contract](/api/v1/bootstrap) carries the same install command as exact arguments; use its released versions and arguments as they are. Then run `techtree doctor`: it checks what the machine needs and prints the next action, without calling a paid model.

## Test your Skill

Techtree makes practice tasks from what your Skill teaches, then your agent works them without the Skill and with it. Every step that sends anything to a model prints a review first and waits for your yes. Each command prints the next one.

```sh
techtree forge inspect-skill path/to/your-skill
techtree forge plan SOURCE_ID --provider PROVIDER --model MODEL
# Review, correct, build and accept, one printed step at a time.
techtree forge run --arm baseline --collection COLLECTION_ID --provider PROVIDER --model MODEL
techtree forge run --arm candidate --collection COLLECTION_ID --provider PROVIDER --model MODEL --skill path/to/your-skill
techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID
```

Both runs use the same provider and model. The comparison calls no model: it pairs every task across the two runs and says whether the Skill improved, regressed, was mixed or made no difference, overall and on the held-out tasks alone. To compare two versions of a Skill, give the baseline run the earlier version with `--skill path/to/earlier-skill`. The [tdd example](/examples/tdd) shows a finished comparison.

## Take a quick look with the Hello World Climb

The Hello World Climb is a small, fixed comparison that ships with the release, run with a starter Skill (`techtree skill starter`). `techtree climb prepare` prints the exact one-time start command and the most the run may spend before anything runs. Its toy tasks say nothing about your own Skill.

## Verify and publish a Result

`techtree proof verify path/to/result-bundle` reads a Result bundle, recomputes its checks and makes no model call. [Verify](/verify) says exactly what verification establishes.

Only Climb runs can be published today. `techtree publish RUN_ID` shows the publication terms and asks before it sends the Result bundle; the site answers with a signed receipt, and publishing the same bundle again changes nothing. `techtree withdraw BUNDLE_DIGEST` marks a published Result withdrawn and stops offering its bundle. Published Results are listed at [Results](/results).

## Read the public API

Reads need no account. The [OpenAPI description](/openapi.json) types every address, and the [API catalog](/.well-known/api-catalog) points to it and to this page.

- `GET /api/v1/bootstrap`: the installation contract for this release.
- `GET /api/v1/catalog`: the published Climbs.
- `GET /api/v1/climbs/{slug}`: one Climb.
- `GET /api/v1/objects/{digest}`: one published object, byte for byte.
- `GET /api/v1/publications`: published Results, newest first.
- `GET /api/v1/publications/{bundle_digest}`: one published Result, and `/bundle` for the exact bytes it was submitted as.
- `GET /api/v1/publication-keys/{key_id}`: the key this site signs receipts with.
- `POST /api/v1/publications`: publish or withdraw a Result. The CLI does this for you.
- `GET /healthz`: whether the site is serving a release.

The CLI's `--json` flag prints one machine-readable answer per command.

## Errors

Every JSON error is an `error` object with a stable `code`, a `message` and a `hint` that says what to do next:

```json
{"error": {"code": "publication_missing", "message": "no run is published under that fingerprint", "hint": "Use a fingerprint listed at https://techtree.sh/api/v1/publications."}}
```

Branch on the status and the `code`, never on the wording of `message`.

An unknown address under `/api` answers JSON 404 whatever the `Accept` header says. An unknown page answers 404 as HTML, as Markdown when you ask for `text/markdown`, or as JSON when you ask for `application/json`. The [OpenAPI description](/openapi.json) lists every status each address can return.

## Rate limits

Each client address has {{request_limit}} requests per {{request_window}} seconds, shared by `/healthz` and the API. Publishing or withdrawing a Result has a budget of its own, {{publication_limit}} per {{publication_window}} seconds, and does not count against the first. Pages are not counted. Every answer says where you stand:

```http
RateLimit-Policy: "default";q={{request_limit}};w={{request_window}}
RateLimit: "default";r={{request_remaining}};t=42
```

`q` is the number of requests allowed in a window of `w` seconds, `r` is how many remain and `t` is the number of seconds until the window resets. Answers to a publication name the `publication` budget instead. Past the limit the answer is `429` with a `Retry-After` header in seconds and the code `too_many_requests`, or `publication_rate_limited` for a publication; wait that long, then send the request again.

## Versioning and deprecation

- The API version is in the path (`/api/v1`) and in `info.version` of the [OpenAPI description](/openapi.json). Every document Techtree publishes also names its own format in `schema_version`. New addresses, response fields and optional inputs can appear at any time, so ignore fields you do not recognise.
- A breaking change, such as removing or renaming a field, address or error code, changing a type or making an input required, ships in place under the same path. It is listed below on the day it ships and `info.version` moves to a new major number. There is no notice period and no `Deprecation` or `Sunset` header, so check `info.version` before relying on a field.
- While a Result is published, its bundle is served as the exact bytes it was submitted as, in the format it was submitted in.

### Breaking changes

- Version 3: every error except a profile answer is `{"error": {"code", "message", "hint"}}`; `retryable` is gone.
- Version 2: an unknown address, a body that cannot be read and an unexpected failure answer `{"error": {"code", "message", "hint"}}`, with no `retryable`.

## Browser tools

Every page offers the agent built into a browser these tools through WebMCP (`document.modelContext`). Each only reads public information, needs no account and spends nothing; publishing a Result stays with the CLI and its key. The [tool manifest](/capabilities) describes them as JSON.

{{tools}}

## What leaves your machine

Local Runs, Episodes and Traces stay local. Model calls go to the provider you chose, or the one the Climb names. Techtree receives a Result bundle only when you publish it. No Techtree account or browser upload is required.

## More

- [Start](/start), [Results](/results), [Verify](/verify) and the [Changelog](/changelog).
- [Agent guide](/llms.txt) and [security.txt](/.well-known/security.txt), which says where to report a vulnerability.
- Source and issues: [github.com/regents-ai/techtree](https://github.com/regents-ai/techtree).
