# Local Repo2RLEnv lane: design

Historical status: design, 2026-09-11. Implements the founder decisions recorded in
`repo2rlenv-v02x.md` ("Founder decisions, 2026-09-11"). It binds the first
executable slice of the lane; it does not authorize publication, package
release, deployment, or platform-funded inference.

## Current status and supersession, 2026-09-17

The [current founder release assignment](repo2rlenv-v02x.md#founder-release-assignment-2026-09-17)
supersedes conflicting proposals below. `forge build/status` is implemented and
offline-reviewed; real Docker qualification and fresh-worker reproduction remain
open. `forge run` is implemented (2026-09-19; the run specification, gate and
run storage are described under "Forge run" in `cli/docs/product-architecture.md`);
`forge compare` and its report remain unimplemented design.
No model quality, subscription compatibility or positive uplift is established.

The local-agent contract is not complete. Prefer a demonstrated Verifiers
grading handoff; direct Harbor-compatible grading of agent attempts requires
explicit founder approval and accurate labels. Hermes-owned authentication and
explicit Skill preload are endorsed but unqualified. Baseline and candidate must
have isolated homes and recorded initial state; the memory/Skills seed policy
remains unanswered. Do not treat the older direct-grading or shared-memory prose
as a decision. Model-free build qualification is separate from agent grading.

The current assignment grants scoped package/site release authority after
review and verification, not paid execution without an account/scope/cap or
private-data disclosure. Docker recovery remains coordinated with the founder.

## What the lane does

This is the target workflow, not a claim that the runner already exists.

A person points Techtree at a repository on their own machine. Techtree turns
that repository's history into Harbor tasks with Repo2RLEnv, builds the task
images locally, proves each task is a real test (the reference fix scores, the
untouched base does not), and then runs the person's own Hermes against those
tasks twice: as configured today, and with a candidate Skill added. The
difference is private local evidence about whether the Skill helps that agent on
that codebase. The same evidence feeds the existing `uplift` loop so the Skill
can be revised and measured again.

Forge artifacts remain local unless separately approved for disclosure. The
intended subject is the person's own Hermes, calling its configured provider;
inference still sends task context to that provider under its policies. Local
artifacts do not mean network-free execution. Techtree never copies a credential.

## Upstream facts the design rests on

Checked on 2026-09-11 against the installed packages and sources. Each one
shaped a decision below.

**Repo2RLEnv 0.8.8.**

- `commit_runtime` walks a local clone's `git log`, splits each commit into a
  source patch and a test patch, and validates the pair in a Docker sandbox by
  running the test commands before and after the source patch. It needs a
  bootstrap image with the repository baked in at `/workspace` and a list of
  test commands. Its emitted `environment/Dockerfile` is `FROM <bootstrap tag>`
  plus a reset to the task's base commit and a history scrub, so it builds
  locally without a registry.
- The `user_dockerfile` bootstrap path builds a Dockerfile with a fresh clone as
  the build context and skips the LLM loop, but records **no test commands**.
  Without test commands validation reports nothing, and every candidate is
  rejected as `no_fail_to_pass`. The LLM bootstrap discovers test commands but
  needs an LLM behind litellm.
- `CommitRuntimePipeline(input, options, bootstrap=BootstrapResult(...))` accepts
  a bootstrap result directly. That is how Techtree supplies the image tag and
  the test commands together.
- `pr_diff` needs pull requests from a forge; it refuses a local path. The spike
  proved its task builder works on local commits when driven through its
  Python API, but its Dockerfile clones from `github.com/local/<name>`, which
  does not exist. `pr_diff` on a local repository therefore needs a
  Techtree-owned Dockerfile and is deferred to a later slice.
- Tasks are graded by `tests/test.sh` inside the task container. `commit_runtime`
  ships `tests/verifier.py`, `tests/f2p.json`, `tests/p2p.json`; the script
  resets the test files to the base commit, applies the test patch, runs the
  test commands, and writes `/logs/verifier/reward.txt` (reward equals the
  fail-to-pass rate times the pass-to-pass rate) plus `reward-details.json`.
  The verifier material is only mounted at grading time.
- Generation is model free when the person supplies a Dockerfile and test
  commands. No LLM is called anywhere in that path.

**Verifiers 0.3.1.**

- The Docker runtime never pulls and never bind-mounts; it runs a local image
  tag as is. It refuses Dockerfile-only Harbor tasks; a task must name an image.
- Every harness that drives an agent installs that agent inside the container.
  There is no path that drives an agent already installed on the host.
- Model calls must flow through the interception endpoint to appear in the
  trace, and the endpoint forwards to one OpenAI-compatible upstream. A harness
  that makes zero calls through it still scores.

**Hermes 0.21.1 (the person's install).**

- `hermes -z "<prompt>" --in <dir> --usage-file <path> -s <skill>` runs one
  turn non-interactively and writes a JSON usage report, exit code 0/1/2.
- `terminal.backend: docker` routes every terminal, file and code-execution
  tool call through `docker exec` into a container Hermes starts from
  `terminal.docker_image`, with `docker_volumes` bind mounts,
  `docker_network: false` for an air-gapped sandbox, `container_persistent:
  false` for one container per session, and CPU, memory and PID limits.
- `HERMES_HOME` selects the home directory. A home that is not the default
  root reads OAuth logins (ChatGPT/Codex, Anthropic, xAI) from the root
  `~/.hermes/auth.json`; Hermes documents that these logins are shared across
  profiles, not copied. Static API keys live in a profile's `.env`.
- Skills load from `$HERMES_HOME/skills` and `skills.external_dirs` in
  `config.yaml`. There is no environment-variable override for either, nor for
  the terminal backend settings; `config.yaml` is the only way to set them.
- The subscription proxy (`hermes proxy start`) exposes the Nous Portal and xAI
  subscriptions as an OpenAI-compatible endpoint. It has no adapter for the
  ChatGPT subscription.

**Docker observation, 2026-09-17.** A read-only daemon probe timed out after
eight seconds; no restart was attempted. Offline status inspection works without
Docker or `uv`. Generation and real qualification still need a responding daemon;
neither injected command diagnostics nor package installation establish that.

## Decisions

**Historical design proposals, 2026-09-11.** Items 1 and 2 below are superseded
where they preselect direct agent grading or initial state by the
[September 17 status](#current-status-and-supersession-2026-09-17). Their original
wording is retained as history, not executable runner authority.

1. **Techtree runs the subject loop itself; Verifiers is not on this path.**
   The founder requires the person's own host Hermes calling the person's own
   ChatGPT subscription. Verifiers can neither drive a host agent nor forward to
   a ChatGPT subscription, so its interception contract cannot hold. Techtree
   therefore performs what Verifiers' `HarborTask` performs, in the same order
   and with the same reward file precedence: prepare the workspace, let the
   agent act, stage `tests/` into a fresh container from the task image, run
   `bash /tests/test.sh`, read `/logs/verifier/reward.json` then `reward.txt`.
   The pinned v0.1 Verifiers path is untouched. This departs from the "Verifiers
   owns evaluation" sentence in `repo2rlenv-v02x.md` and is listed under
   "Decisions needed" below.
2. **The subject runs on the host with a Docker sandbox for its tools.** Techtree
   runs the person's `hermes` binary with a throwaway `HERMES_HOME` whose
   `config.yaml` is written by Techtree: the person's model and provider,
   `terminal.backend: docker` pointed at the task image, the task workspace
   bind-mounted at `/workspace`, network off, resource limits, and
   `skills.external_dirs` naming the candidate Skill directory for the treated
   arm only. Techtree copies no `.env` and no `auth.json`; the OAuth login is
   read by Hermes from its root store. Static-key providers are out of scope
   until the founder says otherwise.
3. **Techtree supplies the bootstrap; Repo2RLEnv supplies the tasks.** The person
   gives a Dockerfile (or accepts a Techtree default for a `uv` Python project)
   and one or more test commands. Techtree clones the repository into a build
   context, builds the bootstrap image, and hands Repo2RLEnv a
   `BootstrapResult` carrying the tag and the test commands. Repo2RLEnv does the
   mining, validation, and emission.
4. **`commit_runtime` first, `pr_diff` second.** `pr_diff` on a local repository
   needs a Techtree-owned Dockerfile, so it follows once `commit_runtime` is
   qualified.
5. **Repo2RLEnv is installed as a managed bundle**, the way the evaluation engine
   is: a pinned `pyproject.toml` and `uv.lock` under `resources/forge/`,
   synced with `uv sync --frozen` into the Techtree home. The ordinary package
   still depends on none of it.
6. **The CLI namespace is `forge`**, one of the six reserved namespaces. It is
   registered by this lane and removed from the reserved list.
7. **Evidence is private and says so.** A `forge` Result records the subject as
   `mutable_local` with the Hermes version, profile name, model, provider and
   the digest of the config Techtree wrote. It is never a pinned subject
   instance, never signed as a public proof, and never accepted by `publish`.

## Surfaces

Only `build` and `status` are registered. `run` and `compare` below are proposed.

```
techtree forge build   --repo PATH [--dockerfile PATH] --test-cmd CMD [--test-cmd CMD]
                       [--limit N] [--language python|node|go|rust|java|c_cpp]
techtree forge status  BUILD_ID|RUN_ID
techtree forge run     --arm baseline|candidate --build BUILD_ID --provider NAME
                       --model ID [--tasks ID,...] [--skill PATH] [--reasoning R]
                       [--repetitions N] [--yes]
techtree forge compare RUN_ID RUN_ID                      (unimplemented)
```

`forge build` produces a build directory, qualifies every emitted task, and
prints the qualification receipt. `forge run` runs one arm over the qualified
tasks with the person's own Hermes and writes a Result. `forge compare` reads
two Results over the same build and prints the per-task and aggregate
difference. `uplift context` learns to read a `forge` comparison in slice 3.

Implemented commands follow the existing envelope machinery: `--json`, warnings,
blockers, next actions. Build and status make no model calls. The proposed
`forge run` would call models through the person's Hermes after authorization.

## Storage

Under the Techtree home:

```
forge/
  env/                          managed Repo2RLEnv project (uv sync --frozen),
                                installed.json records the shipped files' digest
  builds/<build_id>/
    build.json                  ForgeBuildRecord: inputs, digests, image ids
    progress.json               last observed phase, partial evidence, failure
    Dockerfile                  the Dockerfile the bootstrap image was built from
    checkout/<slug>/            git clone of the repository's committed history
    tasks/<task_id>/            the Harbor task package as Repo2RLEnv wrote it
    qualification.json          ForgeQualification: per-task checks and verdicts
    qualification/<task_id>/    image build log, control/ and reference/ output
    log/                        bootstrap build log, driver request and log
  runs/<run_id>/                 proposed only; not implemented
    run.json                    ForgeRun: build id, arm, subject description
    tasks/<task_name>/
      workspace/                the bind-mounted working tree after the agent
      hermes-home/config.yaml   the config Techtree wrote (no secrets)
      usage.json                Hermes usage report
      agent.log                 Hermes stdout and stderr
      verifier/                 reward.txt, reward-details.json, test output
      patch.diff                git diff of the workspace against the base
    result.json                 ForgeResult: per-task rewards and metadata
```

## `forge build` in detail

1. Validate inputs, then create durable progress before daemon/environment
   preparation. A missing Docker executable leaves a failed receipt and build ID;
   offline `status` can inspect it. Input rejection before build admission need
   not create a build. Missing `uv` is rejected at CLI service construction.
2. Clone the repository with `git clone --no-hardlinks <repo> <context>` so the
   build context is a clean checkout with full history and no working-tree
   noise. Record the HEAD commit.
3. Retain the Dockerfile beside the build and use it with the cloned checkout
   as Docker's build context, recording the resulting immutable image ID.
   The default Dockerfile, used when none is given, is a `python:3.12-slim`
   image that installs `git` and `uv`, copies the checkout to `/workspace`,
   and runs `uv sync --frozen` there. The platform is the host's, not
   Repo2RLEnv's `linux/amd64` default, so Apple silicon does not emulate.
4. Run the bundled driver script inside the managed venv. It builds a
   `BootstrapResult` from the tag, language and test commands, constructs
   `CommitRuntimePipeline` with `synthesize_with_llm=false` and the requested
   limit, calls `run(out_dir)`, and prints one JSON line with the emitted task
   names and the skip-reason counts. Validation stays on: it runs the tests in
   a sandbox from the bootstrap image and is what makes the fail-to-pass list
   real. No LLM is configured and none is called.
   The validation container is started by the driver on Techtree's terms, not
   Repo2RLEnv's: from the bootstrap image's content id with pulling refused,
   under a name Techtree chose, with no network and the same memory and CPU
   bounds as qualification. Every runtime container the forge starts, for
   validation or for qualification, is offline and bounded; image builds are
   not, since they install the toolchain. The pipeline removes the container
   when it finishes; on failure, timeout or Ctrl-C, Techtree attempts bounded
   removal by name. Timeout/failure diagnostics record the outcome; Ctrl-C
   currently attaches it as an exception note, not in the durable cancelled
   receipt. A removal request is not proof that an unavailable daemon cleaned up.
   Real cancellation/cleanup acceptance remains open.
5. For every emitted task, build the task image from its
   `environment/Dockerfile` as `techtree-forge/<slug>/<task>:<hash>`.
6. Qualify every task, model free, with the checks the plan requires:
   - **clean build and reset**: the task image builds; a container from it has
     `/workspace` at the base commit with a clean tree;
   - **intended failure of the unrepaired control**: run `tests/test.sh` on the
     untouched workspace; reward must be `0.0` and the fail-to-pass tests must
     be reported failing;
   - **successful reference repair**: apply `solution/patch.diff`, run
     `tests/test.sh`; reward must be `1.0`;
   - **recognized test collection**: the task names at least one fail-to-pass
     test, and the control run's verifier output counts exactly that many
     fail-to-pass tests, all failing;
   - **protected verifier material**: `/tests`, `/solution` and `/logs` are
     absent from the task image; grading mounts `tests/` and `solution/`
     read-only, and the test patch is applied only by the verifier; the only
     host path the tests can write is the run's `verifier/` directory, whose
     reward files are read as small regular files (a symlink or a directory
     there is no verdict), and the container transcript is kept beside it,
     out of their reach;
   - **bounded resources**: the verifier ran under the task's
     `[verifier].timeout_sec` and the container limits Techtree set;
   - **preserved rejection reasons**: Repo2RLEnv's skip counts and each task's
     `validation_status` are recorded verbatim.
   A task that fails any check is kept with its verdict and must be excluded
   from the future `forge run` admission path.
7. Commit complete task contents and ordered membership before qualification;
   verify content before and after grading. Store `build.json` after generation
   and content commitment, `qualification.json` after all-task grading, and
   progress/partial records at phase and task boundaries. Absent rewards are not
   zero; generation, qualification and usable-task facts are separate. Zero
   usable tasks is a typed build refusal with retained evidence. See the
   [implemented commitment/status contract](../../cli/docs/product-architecture.md).

Fresh-worker reproduction remains an acceptance gate: use a genuinely fresh
worker or clean environment and compare pinned source, task content, membership
and verdict evidence without relying on hidden local state. Repeating the build
on the same warm machine alone does not establish independent reproduction.

## `forge run` in detail

**Historical sketch, superseded 2026-09-19 by the implementation** described
under "Forge run" in `cli/docs/product-architecture.md`. Where they differ the
implementation controls: the arm is declared as a run specification before
anything runs; the throwaway home is a profile under the person's Hermes root,
so sign-ins are borrowed and nothing is copied; no model block is copied from
any profile — provider and model are named on the command line and recorded;
every attempt starts from a fresh state with memory off; and the run keeps a
`run.json` of per-attempt outcomes rather than a `result.json`.

For each qualified task, in sequence:

1. Create the workspace on the host by `docker create` from the task image and
   `docker cp <container>:/workspace <workspace>`, then remove the container.
   The workspace is at the base commit with the scrubbed history.
2. Write the throwaway Hermes home: `config.yaml` with the person's
   `model` block copied from their active profile's config (model, provider,
   reasoning settings only), `terminal` set to the Docker sandbox, `skills`
   set to the candidate Skill directory in the treated arm, approvals off,
   title generation off. Nothing else from the profile is copied.
3. Run `hermes -z "<instruction.md>" --in <workspace> --usage-file <usage.json>`
   with `HERMES_HOME` pointing at the throwaway home, stdout and stderr
   captured, under the task's `[agent].timeout_sec` enforced by Techtree. The
   Skill is preloaded with `-s <name>` in the treated arm so the comparison
   measures the Skill as delivered, not whether the agent chose to open it.
4. Diff the workspace against the base commit and save the patch.
5. Grade: run a fresh container from the task image with the workspace mounted
   at `/workspace`, the task's `tests/` mounted read-only at `/tests`, and a
   host directory at `/logs/verifier`; execute `bash /tests/test.sh` under the
   verifier timeout; read the reward with Verifiers' precedence.
6. Record the task outcome: reward, reward details, usage report, exit code,
   wall time, whether the timeout fired, and the config digest.

The run's `result.json` names the subject honestly: Hermes version from
`hermes --version`, the profile whose model block was copied, model, provider,
the config digest, and `subject_kind: mutable_local`.

## What the comparison is and is not

**Superseded historical description, 2026-09-17:** the following paragraph
assumed inherited and shared state that has not been approved. Retained as
history; do not use it as a current product claim.

Both arms are the person's own agent as it is today, with its own memory, its
own installed Skills and its own model. Only the candidate Skill differs. The
comparison therefore answers "does this Skill help this agent, here, now", not
"does this Skill help Hermes". The Result says so. Known confounds recorded on
every Result: the agent's persistent memory is shared across arms and tasks,
and any Skill already installed under the same name shadows the candidate.
Slice 3 may add a memory-off switch if the founder wants a cleaner arm.

**Current requirement:** use isolated homes with matching declared initial
state, changing only the candidate Skill. Record memory settings/content digest,
visible Skills, configuration, tools, model/provider and runtime. The seed policy
remains open. Refuse candidate shadowing and answer leakage; check task-content,
ordered-membership, runtime and grading compatibility before comparison. Preserve
task/infrastructure failure, timeout, cancellation and missing evidence as
distinct outcomes. Do not call repeated revision on the same tasks held-out uplift.

The sandbox has no network. The agent cannot fetch the fix. The host Hermes
process still has its web tools; slice 2 restricts the toolset to terminal,
file, code execution and skills, which is the set the sandbox routes.

## Decisions needed from the founder

**Historical questions below are superseded by the September 17 direction.**
Authentication ownership and explicit preload are endorsed, but need real
acceptance. Demonstrating the preferred Verifiers handoff remains engineering
work; approval is required before direct grading instead. The seed policy and
account/scope/cap for real attempts remain unanswered. Original questions follow
for provenance, not as repeated permission requests.

1. Confirm decision 1 above: Techtree grades `forge` runs itself with the same
   procedure as Verifiers' Harbor task, and Verifiers is not on the local
   subject path. The alternative keeps Verifiers as the grader by syncing the
   agent's workspace into a Verifiers container after the agent finishes,
   which costs two containers per task and gains a Verifiers episode file
   whose trace holds no model calls.
2. Confirm that the throwaway Hermes home reading the root OAuth store counts
   as "the user's local connection" under decision 7. Techtree copies no
   credential; Hermes reads its own store. Providers configured with static
   keys in a profile `.env` are not supported by this lane.
3. Confirm the Skill delivery in the treated arm: preloaded with `-s` (measures
   the Skill's content) rather than merely installed (measures whether the
   agent chooses to use it). Both can be recorded later as separate arms.

## Slices and acceptance

**Slice 1, `forge build`.** Implemented 2026-09-11 in `cli/src/techtree/forge/`
(models, process boundary, Docker wrapper, managed bundle, generation,
qualification, service), the shipped project under
`cli/src/techtree/resources/forge/` (pinned `repo2rlenv==0.8.8`, the driver,
the default Dockerfile), the commands `forge build` and `forge status`, and
the contract documents. No tests were written for the forge (founder
decision, 2026-09-15); verification is a real build against a working daemon.
`forge` is no longer a reserved namespace. Task ids follow Repo2RLEnv's
`local__<slug>-<sha12>` convention; images are `techtree-forge/<slug>:<sha12>-<build12>`
for the bootstrap and `techtree-forge/<slug>/<task_id>:<build12>` per task.

Acceptance still open: select an authorized repository with suitable repair
history and a root-level uv-managed Python project, or a specifically reviewed
custom Dockerfile. The Techtree monorepo root does not fit the default recipe.
On a working daemon, demonstrate an intended unrepaired failure and successful
reference repair, retained rejection/partial evidence, bounded cleanup and a
fresh-worker reproduction. No selected repository or successful outcome is
invented here; until that execution occurs, the lane is code, not qualification.

**Slice 2, `forge run`.** Workspace materialization, throwaway Hermes home,
supervised `hermes -z`, grading container, Result. Acceptance: one arm over the
qualified tasks completes with rewards recorded and the Result names the
subject as mutable and local. Runs cost the person's own subscription usage;
the first real run is announced before it starts.

**Slice 3, `forge compare` and the loop.** Comparison output, `uplift context`
reading a `forge` comparison, memory-off switch if wanted, `pr_diff` recipe with
a Techtree-owned Dockerfile.

Not in any slice here: publication, Prime Agent, Codex, Fabric, Relay, hosted
execution, payments.
