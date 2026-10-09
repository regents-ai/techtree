# Techtree commands

Every `regents techtree` command, written before it is built. A command that is not
described here does not exist yet. Techtree's commands are native code in regents-cli: they
run a local engine, check signed proofs and write files, which a plain request description
cannot say. `commands.json` describes the signed HTTP account and pairing subset; it complements the
native commands. The regents-cli chief builds each native command from its section here.

This file starts with the two commands added for reruns (decision 67 c) and public Skills
(decision 68 a), then the ChatGPT plan sign-in (decision 59 a) beside the own-Prime-key route
(decision 105 b). Each existing command gets its section here when it next changes.

Every command also takes `--json` (print the answer as JSON) and `--base-url URL` (the site's
address; also `TECHTREE_BASE_URL`). A refusal prints the site's `code`, `message` and `hint`
and exits non-zero.

## regents techtree skill fetch \<root_digest\>

- **What it does:** downloads a published Skill by its fingerprint, checks every file against
  that fingerprint, and writes the files to a folder. It never runs anything in the Skill.
- **Who may run it:** anyone (public).
- **What it changes:** nothing on the site. It writes files on this machine.
- **Route:** `GET /api/v1/skills/{root_digest}` → `getSkill`
- **Inputs:**
  - `<root_digest>`: the Skill's fingerprint, `sha256:` and 64 lowercase hex characters, as a
    Result page or `GET /api/v1/publications/{bundle_digest}` shows it (`skill_digest`).
  - `--to DIR`: where to write the files. Left out: `./<skill name>-<first 12 hex>`. The
    command refuses a folder that exists and is not empty.
- **Answer:**
  `{"skill": <SkillArtifact>, "files": [{"path", "content_base64"}, …], "results": [<bundle digest>, …]}`.
  - `skill` is the `skill.json` the Result's proof carried (`techtree.skill.v1alpha1`).
  - `files` holds one entry for each file `skill.files` lists, in the same order.
  - `results` lists the published Results that carried this Skill and are not withdrawn,
    newest first.
- **Refusals:**
  - 400 `invalid_skill_digest`: the fingerprint is not in that form.
  - 404 `skill_not_found`: no published Result that is not withdrawn carried this Skill.
  - On this machine, before writing anything: `skill_fingerprint_mismatch` when a file's
    bytes or the file list do not give the fingerprint asked for, and `skill_path_invalid`
    when a path would land outside `DIR`.

Server:

```text
root_digest must be "sha256:" + 64 lowercase hex      else 400 invalid_skill_digest
entries = published Results whose skill_digest == root_digest, not withdrawn, newest first
no entries                                           -> 404 skill_not_found
bundle  = the newest entry's stored bundle bytes, read as submitted
skill   = bundle member "skill.json"
files   = bundle member "skill/<path>" for each path in skill.files
answer 200 {"skill", "files", "results": entries' bundle digests}
  Content-Type: application/json; X-Content-Type-Options: nosniff; Cache-Control: public, max-age=300
```

This machine:

```text
answer = GET /api/v1/skills/<root_digest>
for each file: sha256(bytes) == listed digest, size == listed size, path is POSIX relative
  with no "..", no leading "/", no backslash, and a listed suffix (.md .txt .json .yaml .yml)
root_digest recomputed from skill.files (RFC 8785 canonical JSON of the sorted list) == asked
any check fails  -> refuse, write nothing
otherwise        -> write each file under DIR and print the folder and the Results it came from
```

- **Server needs:** the Skill inside each published proof (68 a, below), and the
  `skill_digest` the site already keeps on every published Result. The answer is data: the
  site serves the files as base64 inside JSON and never runs, renders or imports them.
- **History:** 2026-10-05 added.

## regents techtree climb prepare --rerun-of \<bundle_digest\>

- **What it does:** makes a local draft that reruns a published Result. The draft uses the
  same Campaign and the same Skill, with a new pair of runs (without and with the Skill) on
  this machine, signed with this machine's publisher key. `climb start`, `climb run` and
  `climb publish` then work on it as on any draft.
- **Who may run it:** anyone set up for Climbs. The runs use this person's own model access,
  as every Climb does.
- **What it changes:** nothing on the site. It writes a draft on this machine.
- **Route:** `GET /api/v1/publications/{bundle_digest}/bundle` → `getPublicationBundle`
  (existing).
- **Inputs:** `<bundle_digest>`: the published Result's bundle digest, as its page and
  `GET /api/v1/publications/{bundle_digest}` show it. There is no Climb argument: the
  Result names its Campaign.
- **Answer:** the draft's folder, the Climb and Campaign it reruns, and the Skill's
  fingerprint.
- **Refusals:**
  - 404 `publication_missing`: no Result is published under that digest.
  - 410 `publication_withdrawn`: its publisher withdrew it.
  - On this machine: the bundle's offline check fails, or
    `rerun_campaign_not_in_release` when its Campaign is not one in this release. Results
    made under `techtree.campaign.v3` cannot be rerun.

This machine:

```text
bundle   = GET /api/v1/publications/<bundle_digest>/bundle; check it offline in full
campaign = the bundle's Campaign digest; must be a Campaign in this release
           else refuse rerun_campaign_not_in_release
skill    = the bundle's skill.json and skill/ files (68 a); root_digest must equal the
           candidate experiment's Skill digest
draft    = ordinary draft: that Campaign, that Skill, a new baseline and candidate run
report   = when published, the uplift report carries "rerun_of": <bundle_digest>
```

Server, when a report with `rerun_of` is published (`POST /api/v1/publications`):

```text
rerun_of is null                         -> as today
original = the published Result with bundle_digest == rerun_of (withdrawn or not)
           none                          -> 422 rerun_original_unknown
original.campaign_spec_digest == this report's campaign_spec_digest
                                         else 422 rerun_campaign_mismatch
original.skill_digest == this proof's skill root_digest
                                         else 422 rerun_skill_mismatch
store rerun_of in the Result's assessment; nothing else changes
```

- **Pages:** a rerun's page names the Result it reruns and says whether it was signed by the
  same publisher key or another one. The original's page lists its reruns and counts them as
  Results, never as people: "2 reruns", not "2 people". A rerun from another key is still a
  report from someone's own machine, not independent reproduction, and one person can hold
  many keys.
- **Server needs:** `rerun_of` in `techtree.uplift-report.v3`, signed with the rest of the
  report. The relation is stored in the Result's existing assessment, with no new table.
- **History:** 2026-10-05 added.

## What a published proof carries for its Skill (68 a)

From `techtree.campaign.v4` on, a proof bundle (`techtree.local-proof-bundle.v1alpha2`) carries
its candidate Skill: `skill.json` (the existing SkillArtifact, as canonical JSON) and
`skill/<path>` holding each listed file's raw bytes, all listed in the bundle manifest. Those
`skill/` files are the only bundle members that are not JSON documents. Publishing a Result makes
its Skill public. Each Climb's data policy already says so
(`candidate_skill.public_release: required_for_climb`, the Skill owned by its participant), and
`climb publish` says it in plain words before anything is sent.

The site accepts a proof only when its Skill holds all of these. `climb publish` checks the
same list before anything leaves the machine:

```text
skill.json root_digest == the candidate experiment's Skill digest        skill_fingerprint_mismatch
every file's bytes give its listed digest and size                       skill_fingerprint_mismatch
paths: POSIX relative, unique, sorted, no "..", no leading "/", no "\",
       suffix .md .txt .json .yaml or .yml, SKILL.md present             skill_path_invalid
at most 32 files, each at most 128 KiB, 256 KiB in all                   skill_too_large
no file contains a private key or an API key:
  "-----BEGIN … PRIVATE KEY-----", sk-…, sk-ant-…, ghp_…, github_pat_…,
  AKIA + 16, xox[abprs]-…, "0x" + 64 hex standing alone                  skill_contains_secret
```

A refused proof is not published, and the answer names the file and the check it failed.

## regents techtree model login | status | logout

- **What it does:** signs this machine in to the person's ChatGPT plan with OpenAI's Sign in
  with ChatGPT, so Climbs can run on that plan (decision 59 a) as well as on the person's own
  Prime key. Techtree sells no model calls and charges nothing; plan runs use the person's own
  plan allowance.
- **Who may run it:** anyone with ChatGPT Plus or Pro.
- **What it changes:** nothing on the site. It writes `<techtree home>/chatgpt.json` (by default
  `~/.regents/techtree/chatgpt.json`) on this machine (`login`) or removes it (`logout`).
- **Route:** none on the Techtree site. Every call goes to OpenAI.
- **Inputs:** none.
- **Answer:**
  - `login`: opens the browser at OpenAI's sign-in address and listens on 127.0.0.1 for the
    answer. If no browser opens, it prints the address for the person to open on this machine;
    the address holds only the state and the PKCE challenge, never a token. Signing in from a
    remote shell is not covered in this version. Then it answers with the signed-in email, the line "Using your ChatGPT plan", and the link
    https://chatgpt.com/settings/usage, where the person sets how much of their plan Regents may
    use and can disconnect it.
  - `status`: signed in or not, the email, and the models the plan offers (the ones listed
    with visibility `list`).
  - `logout`: revokes the sign-in at OpenAI, then deletes the file. When OpenAI does not confirm
    the revocation, it still deletes the file and says the sign-in was removed here but not
    confirmed revoked at OpenAI; disconnecting Regents at https://chatgpt.com/settings/usage
    finishes it.
- **Refusals:**
  - `plan_not_eligible`: OpenAI answered `subscription_sharing_user_not_eligible` (the plan is
    not Plus or Pro), `chatpass_v2_scope_not_authorized`, or a 403 for its policy or the
    person's region.
  - `model_sign_in_required`: `status` or a Climb found no sign-in, the sign-in can no longer
    be refreshed (`invalid_grant`, `refresh_token_reused`), or OpenAI answered 401
    `subscription_sharing_invalid_user`. The answer says to run `regents techtree model login`.
- **doctor:** its "Evaluation model credential" check becomes two lines, "Own Prime key" and
  "ChatGPT sign-in", each set up or not; a Climb needs only the route it runs on. Signed in
  means the file exists, the refresh token is within its 30 days, and the granted scopes include
  `chatgpt.tokens.use.direct`. doctor makes no network call, so it never refreshes.

This machine:

```text
registration  self-serve: open-source local apps need no OpenAI approval
first login   GET https://auth.openai.com/api/accounts/authorize
                client_id=dynamic_agent_client, agent_name_hint=Regents,
                ext_agent_host_id=<this machine's saved urn:uuid>,
                redirect_uri=http://127.0.0.1:<port>/callback (loopback only),
                scope="openid profile email offline_access resource.invoke
                       chatgpt.tokens.use.direct", resource=https://api.openai.com/v1,
                PKCE S256, state, nonce
              the callback returns the code and this person's issued client_id (kept)
later logins  the same, with the kept client_id
token         POST https://auth.openai.com/api/accounts/oauth/token (public client, no secret)
              check the ID token: JWKS signature, iss, aud == issued client_id, exp, nonce
              granted scopes must include chatgpt.tokens.use.direct
storage       <techtree home>/chatgpt.json (by default ~/.regents/techtree/chatgpt.json),
              written atomically, mode 0600
refresh       access token lasts 1 hour; refresh token 30 days and rotates on every use
              refresh under a file lock so two processes never reuse one refresh token
logout        revoke at the endpoint OpenAI's OpenID configuration names, then delete the file
              (deleted even when the revocation is not confirmed, and the answer says so)
never         the token in a URL, a log, a container, a --json answer or anything sent to Techtree
```

- **History:** 2026-10-05 added.

## How a Climb runs: own Prime key or ChatGPT plan (59 a, 105 b)

A Climb runs on one of two routes, and the person picks one for each run: their own Prime key,
as today, or their ChatGPT plan (decision 59 a). Both stay (decision 105 b). Credits bought
through Stripe's LLM billing come later as a third route. On either route the person pays their
own provider and Techtree charges nothing. Hello World, Frontier-CS, Tasksmith and the au-bas
Climb all move in climb-v0.7.0. `techtree.campaign.v4` and `techtree.experiment.v4` are not
released yet, so this changes them in place:

```text
ModelSpec       {model_id, access}                       provider, revision and credential_env go
model_id        OpenAI's own name for one model held fixed for every Climb: "gpt-6-luna"
access          the routes this Campaign offers: a non-empty, sorted set with no repeats,
                drawn from "chatgpt_plan" and "prime_key" ("stripe_credits" joins later)
                prime_key asks Prime for "openai/<model_id>" and reads the key the way Prime
                does (PRIME_API_KEY, else `prime login`)
SamplingSpec    {reasoning_effort}                       temperature and max_tokens go on both
                                                         routes: the plan refuses them, and a
                                                         reply cap on one route only would make
                                                         the two routes' tries differ
Budgets         maximum_input_tokens, maximum_output_tokens, maximum_model_calls, timeout_seconds
                on both routes
                maximum_usd: present exactly when access holds prime_key, and used only there
```

One run is one route. A run's baseline and candidate always use the same route, so the uplift a
Result claims is measured within one route. The route is recorded and signed:

```text
experiment manifest v4   access: "prime_key" | "chatgpt_plan"   (in the bundle, checked offline)
uplift report            access, and cost provenance provider_reported (prime_key) or
                         plan_included (chatgpt_plan)
```

Choosing the route:

```text
climb prepare <climb> --access prime-key|chatgpt-plan
  required whenever the Climb offers more than one route; no default, never guessed from what is
  set up on this machine
  missing           model_access_required: lists the routes the Climb offers and which are set
                    up here ("ChatGPT plan: signed in as you@... / own Prime key: not set up")
  not offered       model_access_not_offered
  not set up        model_sign_in_required (plan) or prime_key_missing (Prime)
  the draft records the route; climb start uses it, and its first line names it
climb prepare --rerun-of <bundle_digest> --access ...
  any route the Climb offers; the rerun records its own route, and its page shows the
  original's beside it
```

Both routes stop the same way:

```text
per try         stop starting calls once a token limit is crossed or K calls are reached; the
                call that crosses still finishes, so a try can go past its token limits by one
                full reply; the try is graded as it stands
receipt         EpisodeReceiptV3 gains ending: completed | token_limit | call_limit | timeout
                the report counts tries by ending
prime_key also  the run-wide dollar stop at maximum_usd; run_spend_unreported when Prime
                reports no cost
```

On the plan, regents-cli runs a forwarder on this machine's loopback address. The model calls
from inside the container reach it, and it sends each one to
`POST https://api.openai.com/v1/responses` with a fresh access token, `store: false` and
`stream: true`. A call counts only on a `response.completed` event. The forwarder drops every
field the plan refuses (`max_output_tokens`, `temperature`, `top_p`, `truncation`,
`previous_response_id` and the rest of OpenAI's list), sends the full history each time, and
keeps `reasoning`.

```text
cost            provenance plan_included: tokens used, no dollar figure
plan used up    the run ends with plan_limit_reached and no Result; the message reads
                "Your ChatGPT plan's limit for Regents is used up. Manage usage:
                 https://chatgpt.com/settings/usage" (no reset time is guessed)
plan refused    400 subscription_sharing_unsupported_capability: the run ends with
                plan_request_refused. The forwarder sent something the plan does not take, a
                fault on our side; the request is never retried and OpenAI's request id is kept
                in the details
plan busy       503 subscription_sharing_usage_unavailable or subscription_sharing_user_unavailable:
                a bounded retry inside the forwarder, then the run ends with plan_unavailable
not eligible    plan_not_eligible
no sign-in      model_sign_in_required
```

- **Before a run starts:** `climb prepare` and `climb start` name the route.
  - Plan: "Using your ChatGPT plan", the settings link, and "Runs on your ChatGPT plan. Each try
    stops starting model calls once it passes its token limit or reaches K calls, so the run uses
    about N tokens of your plan's limits; a try's last reply can go over. Techtree charges
    nothing."
  - Own Prime key: "Runs on your own Prime key. Stops at $X, or sooner when each try passes its
    token limit or reaches K calls. Techtree charges nothing."
  - K is `maximum_model_calls`; N is (`maximum_input_tokens` + `maximum_output_tokens`) × tries;
    $X is `maximum_usd`. The call and dollar limits are exact; the token limits are not.
- **Site needs:** the importer reads `ModelSpec.access` and the Budgets (`maximum_usd` only when
  the Climb offers the Prime key). A Climb page shows the routes it offers, the token and call
  limits, and the dollar limit when the Prime key is offered. A Result page says "Ran on: own
  Prime key" or "Ran on: ChatGPT plan", read from the signed manifest and report. A Climb's
  board lists every Result together (same model, sampling and limits) with the route on each
  row and a filter by route; it is not split.
- **Still to prove:**
  - The two routes give the model the same input. The Prime key goes through Verifiers' client
    to Prime; the plan goes through the forwarder to OpenAI, which moves system text into
    `instructions` and wraps tools in a namespace. regents-cli records both routes' outgoing
    requests for the same try on the free stand-in and compares them field by field. If they
    cannot be made equal, a Climb's board splits Results by route.
  - Many parallel tries on one plan (OpenAI's docs name no concurrency limit).
  - Whether the plan serves gpt-6-luna, known once Sean signs in. If not, Sean chooses between
    moving every Climb to one model both routes serve, or listing only the Prime key on those
    Climbs.
- **History:** 2026-10-05 added (plan only). 2026-10-06: both routes (105 b).

## Hosted publication access (API v4)

`publish`, `climb publish` and `withdraw` retain their local participant proof and exact
JSON bytes. Hosted requests require fresh SIWA proof for audience `techtree` and current
owner-approved pairing. The CLI prepares and signs POST `/api/v1/publications` over the
original body, never a re-encoded copy. A retry keeps the same document and signs a fresh
request. Only `https://techtree.sh` may receive production proof; arbitrary base URLs
remain available for public reads and offline work. Frozen prior releases remain intact.

The signed HTTP subset adds `agents whoami`, `agents pair`, `account balances`,
`account credits-history` and `account points`. It does not replace the native engine,
manage grants, activate Points, or move funds. Pairing codes go on stdin.
