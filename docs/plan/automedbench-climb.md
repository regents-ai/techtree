# AutoMedBench Climb (from VERA)

Sean, 2026-10-07: "Make a plan to integrate this code https://github.com/AutoMedBench/VERA as a run that someone
can do."

## What VERA is

VERA (github.com/AutoMedBench/VERA, Apache-2.0, arXiv 2610.05923, two commits, 6 Oct 2026) is a training system,
not a benchmark. It builds rubric-scored sandboxes from earlier agent runs, then improves an open Qwen3.5 model and its
agent's Skills in alternating rounds, keeping a change only when scores rise. The released code has no sandboxes,
data, model weights, Docker image or rubric source ("opening soon"), needs several GPUs for training, and cost about
$240k as research. Nobody can run VERA itself from this release.

What VERA measures itself on can be run: **AutoMedBench-Lite v0.1** (huggingface.co/datasets/MitakaKuma/
AutoMedBench-Lite-release, MIT code, 11.6 GB, not gated, last changed 24 Sep 2026). Seven medical-imaging tasks, one
per track, each run as a five-stage research workflow (S1–S5) in a sandbox:

| Track | Task | Data terms |
| --- | --- | --- |
| Classification | skin lesions (HAM10000 / ISIC) | CC BY-NC 4.0, non-commercial |
| Synthesis | pancreas CT super-resolution (MSD) | CC BY-SA 4.0 |
| Detection | paediatric wrist X-ray (GRAZPEDWRI-DX) | CC BY 4.0; no re-identification attempts |
| Segmentation | multi-organ CT (TotalSegmentator CT-Lite) | CC BY 4.0 |
| Question answering | MedXpertQA-MM, 2,005 cases | MIT |
| Report writing | chest X-ray reports (CheXpert Plus mirror) | not declared; Stanford's terms apply |
| Enhancement | low-dose CT denoising (SimNICT) | CC BY-ND 4.0 |

Score: Overall = half Agentic (S1–S5; S1–S3 graded by a judge model pinned to Claude Opus 5, S4–S5 by code) + half
Task (Dice, SSIM, accuracy, mAP). It ships its own runner (`automedbench harbor`, "Mini-Harbor"); its Docker path runs
on CPU and hides GPUs. The upstream Harbor backend is switched off until seven adapters pass parity; Harbor has no
AutoMedBench adapter yet.

## The run

**An AutoMedBench-Lite Climb**, run by a person on their own machine through regents-cli like the Tasksmith Climb:
the tasks run without and with the person's Skill, and the uplift is published to techtree.sh as an ordinary signed
Result. VERA's own idea, improving a Skill against these tasks, arrives later through the SkillOpt template
([skillopt-climb-template.md](skillopt-climb-template.md)), which already ends in an ordinary Climb Result.

Not chosen: running it on the server on Fly Sprites like the wallet bench (Regents Labs pays every model and judge
call, and the result is not the person's); waiting for VERA's data (no date).

Done means: a person with Docker and their own model key runs `regents techtree climb prepare` / `climb start` on the
AutoMedBench-Lite Climb, it finishes on CPU, `publish` sends the Result, and techtree.sh shows the score per track
with the Skill's uplift.

## Things to settle first

1. **Data terms.** Techtree never re-hosts the data; the person's machine downloads it from Hugging Face. Report writing
   (terms undeclared) and skin lesions (non-commercial) are left out of the first Climb unless Sean says otherwise.
2. **Public answers.** The Lite release ships its answer files next to the inputs, so a Result cannot prove the agent
   never saw them. The Climb page says so, and the Result records a hash of every answer file it was scored against.
   A held-out set needs AutoMedBench's own unpublished split; ask the authors later.
3. **Judge cost and route.** S1–S3 need a judge model call per stage. The person pays it through their own key (the
   Prime route, as in SkillOpt). Cost per run is unknown until a measured pilot.
4. **HQ 122 c** (no Climb features or spend) is lifted for this Climb (Sean "2 a", 7 October 2026): the probe, then a
   pilot capped at $10 with every model call announced before it is made.
5. **CPU time.** Segmentation (TotalSegmentator) and 2,005 question-answering cases may be too slow on a laptop. The
   probe measures each track; slow tracks use a fixed sample of cases, recorded in the Climb.

## Decisions

- 7 October 2026, Sean "1 a": the run is this AutoMedBench-Lite Climb, run by a person through regents-cli.
- 7 October 2026, Sean "2 a": HQ 122 c lifted for it; probe, then a pilot capped at $10, each call announced.
- Open: which tracks go in (the five with clear terms, or all seven), and whether VERA's method goes first onto
  Techtree's existing non-medical Climbs (see below).

## VERA outside medicine

VERA's method is not medical. The paper runs the same loop on a second domain, software and computer work
("CoWork", sandboxes built from Terminal-Bench, SWE-Bench and MLE-Bench), where the co-evolved 9B agent also improves
SWE-Bench Verified (44.0 to 54.2). This release ships only the medical half: its rubric tables, sandboxes, research
tools and Skills are medical, and the CoWork environments and AutoCoWorkBench are not released.

What carries to any domain: the loop (score each stage, decide whether the model or the Skills caused a weakness,
change one, keep it only if the score rises), the rubric shape (five to ten weighted yes/no checks per stage, each
checkable from evidence, an executable check overriding the judge) and the judge that inspects the workspace.

For Techtree, the Skill half is the SkillOpt template, and it needs no medical data: it can run on any existing Climb
(Tasksmith, Frontier-CS, Hub) today. The model half needs GPUs (about 100 GPU-hours for a 9B model per domain) and
stays out of scope. On AutoMedBench the Skill half alone reached 56.1 against 69.1 for both halves, so Skills give most
but not all of VERA's gain.

## Phases

| Phase | Owner | Work | Spend |
| --- | --- | --- | --- |
| P0 probe | Techtree chief | Read `automedbench_release/` in full; list each track's image, CPU time and judge calls; check whether its runner fits a Climb engine as is (wrap `automedbench harbor` and normalise its report, as `normalize_eval_output.py` does) or needs Harbor-format tasks under Verifiers' `HarborTaskset` like `hf-tasksmith-v1`. | none |
| P1 pilot | Techtree chief | One track (enhancement, the CPU one), one repeat, on a local machine; record wall time, tokens and dollars per stage. | capped, approved per call |
| P2 regents-cli | regents-cli chief | Climb definition `automedbench-lite-climb@1` in `build_fixture_catalog.py`, engine and taskset package, data download with checksums, scoring to Techtree's uplift report, release core; regents-cli 1.8.0. | none |
| P3 Techtree | Techtree chief | Starter Skill, Climb page and home list copy (`climb_copy.ex`, `starter_skill.ex`, `home_live.ex`), data-terms and public-answers notes on the page, release record `climb-v0.8.0`, plugin pin. | none |
| P4 walk | Sean | Run it end to end on his machine and publish; check the Result page on techtree.sh. | his key |
| P5 later | Techtree chief | VERA-style Skill improvement on this Climb through the SkillOpt template. | per SkillOpt's $25 limit |

## Open questions for the authors

- A held-out split for Lite, or permission to hold some cases back.
- Whether the Opus 5 judge pin may be any provider's Opus 5 (the person's Prime route) rather than Bedrock.
- The Docker image registry named `<registry>` in the AutoMedBench README.
