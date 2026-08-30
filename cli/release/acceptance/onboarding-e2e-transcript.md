# WP11f — the agent-first onboarding journey, as a conversation

Ticket `techtree-python-ndq.3.6`. Contract `docs/release/contracts/wp11f.md`.
Performed 2026-08-27 by an acceptance worker acting as the operator, on the
founder's Mac, into a throwaway Hermes home.

**About credentials in this transcript.** Decision 0036 removed every
secret-shaped-string filter from this project, deliberately. Nothing here was
filtered afterwards. The rule this journey worked to is the other one: a
credential never entered the record in the first place. The Prime CLI
configuration was copied into the journey home with a plain `cp` and its
contents were never opened by the worker; the one host-model call read the key
inside its own process and put it straight into a request header. No credential
value appears in this file, in any artifact this ticket produced, or in any
tool argument.

---

## 0. What stood in for what

The founder's own Hermes was not touched and not restarted. Everything below
ran against a throwaway `HERMES_HOME` under a scratchpad. That home has no
model and no provider configured, so **no live Hermes agent conversation was
possible**, and none was held. What follows is the journey driven through the
installed plugin's own tools and the installed CLI, with a minimal host facade
standing in for Hermes' `PluginContext` — the same substitution WP11e made for
the guided revision, and disclosed for the same reason.

That means: the plugin-install and enable legs establish that the pinned commit
installs, is pinned, and loads its tools. They establish **nothing about the
founder's own working Hermes**. The real-Hermes path was walked by the founder
himself on 2026-08-27 on a prior build of the same lineage, producing
`run_b3e25a431d3b43128deb31e99a0b6c68`; that is the record for the leg this
journey does not cover.

---

## 1. The one instruction

The pinned guide at `https://techtree.sh/start` publishes this, verbatim, as
the thing a person pastes into their existing Hermes:

> Read the pinned Techtree installation guide at https://techtree.sh/start.
> Review the exact GitHub plugin release and installation commands with me. Ask
> for my approval before installing software or spending model credits. Install
> and enable the Techtree Hermes plugin, tell me when Hermes must be restarted,
> then use the plugin to install and verify the Techtree CLI and run the Hello
> World Climb. Do not upload my local evaluation artifacts.

The plugin's own README at the pinned commit publishes a second, differently
worded prompt for the same purpose.

## 2. What the agent would read

`https://techtree.sh/start` answered 200 and was read
(sha256 `b648afd8dbaa73d76072064e787e1d21827323509501a50805da711ec853d099`).
`https://github.com/regents-ai/techtree-hermes` answered **404**: the repository
the guide names does not exist yet. So the "pinned GitHub release instructions"
were read where they actually live before Gate 2 — the local candidate at
commit `df5ead2b38316a8def7837ae0bedfe8c1d5c64a4`, whose README is
`b697a5560746aa880221ae55d681a11d80a722d8` in git and
sha256 `a243e96f…` on disk. Nothing here should be read as covering the public
path; that is WP11-postpublish.

The live guide declares itself a placeholder — "This is not a real release yet.
The versions and revisions below are stand-ins, published so the path can be
read before it is real. They install nothing." — and the three commands it
publishes are:

    hermes plugins install regents-ai/techtree-hermes --ref 0000000000000000000000000000000000000000 --enable
    hermes plugins doctor techtree --ci
    uv tool install techtree==0.0.0-placeholder

## 3. Installing the plugin — the first approval

Run without a terminal anyone could answer at, the install **refused**:

    Decision: BLOCKED — Blocked (community source + caution verdict, 6 findings).
    Blocked: Security scan blocked plugin install: Requires confirmation
    exit 1

Re-run on a real terminal, Hermes asked twice and the operator answered twice:

    Install anyway? Only continue if you trust the source. [y/N]: y
    ...
    Enable 'techtree' now? [y/N]: y
    ✓ Plugin techtree enabled.
    Restart the gateway for the plugin to take effect:
      hermes gateway restart

Installed at `df5ead2b38316a8def7837ae0bedfe8c1d5c64a4`, detached HEAD, clean
worktree, `plugins.enabled: [techtree]` in the throwaway home's config.

The command differed from the published one in one respect: a `file://` URL
pointed at the local candidate repository instead of `regents-ai/techtree-hermes`,
because that repository does not exist. Hermes warned "Using insecure/local URL
scheme". `--ref` and the 40-character commit are exactly the published shape.
`--enable` was **not** passed, so the enable question was asked rather than
pre-answered; the published command passes it and skips that one prompt.

## 4. The restart question, asked of the software rather than the documents

`hermes plugins doctor techtree --ci` in a brand-new process, with nothing
restarted: **OK — 16 tools, 2 hooks registered.** `hermes tools list` in another
brand-new process: `✓ enabled techtree`.

Reading Hermes' own loader settles why. `model_tools.py` runs plugin discovery
at import, and its comment says each entry point "runs discovery explicitly at
its own startup"; `_ensure_plugins_discovered` memoises per process. So:

- a **new** `hermes` process sees a newly enabled plugin immediately — no
  restart of anything is required;
- a process that was **already running** when the plugin was enabled never sees
  it. That includes the launchd-supervised gateway, and it includes the very
  chat session the user pasted the prompt into.

The agent-first path is therefore the case where a restart genuinely is
required, which is what the guide says. Hermes' own post-enable line names only
the gateway, which is narrower than the situation the guide describes.

## 5. Installing the CLI — the second approval

The plugin was asked what this host has. It offered exactly one plan:

    uv tool install --python 3.12 techtree==0.1.0
    requires_confirmation: true
    "Techtree is not installed. This command changes software on this machine,
     so the user has to approve it."

The operator approved that exact command, and the plugin dispatched it to the
host terminal — the plugin never runs an installer itself. The coordinate was
resolved from the candidate `dist/` directory through `UV_FIND_LINKS`, with the
cache disabled outright, because nothing is published to an index; the argv
itself was the plugin's, unedited.

Result: `installed: true`, `approval: host_terminal`, Techtree 0.1.0 on
CPython 3.12.13, and the plugin's own post-install check agreed the CLI belongs
to its release. 161 wheel members compared, 160 byte-identical; the only
difference is `dist-info/RECORD`, which the installer writes.

## 6. Verification and health

    techtree release verify --expected sha256:bef3b9d4…
    ok — 12 checks, 9 passed, 3 skipped

    techtree doctor --climb hello-world-climb@1
    ok — 14 checks, 14 passed
    execution_model_credential: "the active Prime CLI configuration holds a key
                                 the pinned evaluation client can use."
    hermes_plugin: "The Techtree plugin is installed and switched on for this Hermes"

## 7. The review a person answers before any money moves

Rendered by the CLI, on a real terminal, and declined on purpose:

    This runs 72 episodes: the same tasks once for each side of the comparison.
    This run spends model tokens on inference. Before anything starts, Techtree
    checks that this Campaign's enforced per-episode limits cannot add up past
    the $2.50 maximum it declares, and refuses to run it if they could. …
    Nothing keeps a running total while the run is under way …
    The Skill is the only scientific change.
    Model calls go to prime, under that provider's policies.
    Techtree does not upload your episodes, traces, receipts, proof bundles, or
    Skill proposals.
    …
    Start this run? [y/N]: n

    Error: the run was not approved, so nothing was started
    Code: policy_acceptance_required

Nothing started. No claim of a development fake executor appeared anywhere on
this surface, and the run the operator did approve recorded
`fake_executor: false`. The WP11e P0 (`techtree-python-ce9`) is gone.

## 8. The approval, and the first run

Approved through the plugin's own start tool. Recorded as
`approved_by: human_via_hermes`, `policy_acknowledgement_method:
host_agent_confirmation`, `fake_executor: false`. Run
`run_618a27f7fde4465ebe02a6bf33b71f7c`, worker pid 98642.

The process that started it exited immediately. The run kept going, and every
later command reached it by run identifier from a completely new process. The
plugin's start tool was then called a second time with the same draft: it
returned the same run identifier and started nothing new — one run directory
exists. A replayed installation plan identifier was refused outright: "that
installation plan was not offered by this session."

## 9. The first result

    Baseline 0.000 → candidate 0.639, delta +0.639
    23 wins · 0 losses · 13 ties, 36 tasks
    decision accepted · proof grade P1 · verified offline

That is the certified stability pair reproduced exactly, from the shipped
artifacts, on a fresh home. The proof verified from the stored bytes with
nothing fetched: **339 checks, no failures**.

Cost: **USD 0.1168**, and the provenance matters — the provider reported none
(`cost_provenance: unavailable`), so this figure is derived by Techtree from
the run's own token counts at prices recorded 2026-08-20.

## 10. The one guided revision

The improvement context Techtree exported carried public prompts, pass/fail and
rewards, and `subject_reply: null` throughout — no hidden answers and no
subject replies, as the data boundary claims.

One host completion, on the frozen profile, through the plugin's own one-shot
wrapper: `z-ai/glm-5.2`, temperature 0, `max_completion_tokens` 32768, strict
`json_schema`, one request, no retry, no repair. Provider response id
`a319c0b7b9bceb36-SJC`, finish reason `stop`, 5,112 prompt / 7,921 completion
tokens, **provider-reported cost USD 0.0441**.

A usable proposal came back and neither guard rejected it. The model proposed
reducing each position-weighted product modulo 97 incrementally rather than
summing first — 14 lines added, 5 removed, 19 changed. Techtree scanned it,
prepared `draft_5602c1912a104539bad52e8719484665`, and stopped:

    "Nothing has run. Show the difference above, the data policy, and the
     declared maximum, and start only if the user agrees to this exact
     comparison."  requires_user_confirmation: true

The two WP11e guard defects (`techtree-python-5f6`, `techtree-python-0mx`) did
not fire on this attempt.

One thing about that answer is worth stating because it happened live: the
plugin defaults to the bounded, chat-shaped form of every answer unless the
caller names `channel: "terminal"`, and Hermes documents no field the plugin
can read. The proposal therefore came back without its request accounting, its
draft digest, or its provenance — the fields the record is made of. They are in
this journey's own host-call record instead.

## 11. The second approval, and the second run

Approved against the diff, the data policy digest, the 72-episode count and the
declared maximum. Run `run_4584be6d8e1248ce9495a51ce2059fee`,
`approved_by: human_via_hermes`. The approval event's `draft_digest` came back
`null`, on both runs — the one field that makes "a person approved this exact
draft" checkable by eye.

## 12. The second result

    Baseline (Skill v1) 0.639 → candidate (Skill v2) 0.667, delta +0.028
    1 win · 0 losses · 35 ties
    decision accepted · proof grade P1 · verified offline — 339 checks, no failures

The revision moved one task. That is what the product said, and it is what is
recorded here: no verdict was added to it. Worth noting for anyone reading a
single number — the same Skill scored 0.639 as the candidate of the first
comparison and 0.639 as the baseline of the second, which is the two runs
agreeing, and the +0.028 is one task out of thirty-six.

Cost: **USD 0.0580**, again derived by Techtree from token counts rather than
reported by the provider.

## 13. What was spent, in total

| leg | estimate | actual | where the actual came from | ceiling |
|---|---|---|---|---|
| first comparison | 0.2383 | 0.1168 | derived from the run's token counts | 0.30 ✓ |
| one guided-revision host completion | 0.1816 | 0.0441 | reported by the provider | 0.30 ✓ |
| second comparison | 0.1200 | 0.0580 | derived from the run's token counts | 0.30 ✓ |
| **total** | | **0.2189** | | authorised 1.50 |

One host call was refused by the provider's edge before it reached a model
(HTTP 403, Cloudflare 1010) because this journey's own facade used a bare
standard-library HTTP client. Nothing was generated and nothing was billed.
That was a defect in the harness, not in the product, and it was corrected by
using the client stack this release already pins. No paid outcome was retried.
