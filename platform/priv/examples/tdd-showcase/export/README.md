# Collection forgecol_ffa133338756407eba327098051f996c, version 1

This folder is a private copy of one accepted collection of tasks, made by Techtree on 2026-09-27 at 06:53 UTC. Nothing in it has been published.

The collection's fingerprint is `sha256:5ce52d4aa2b5ba23ffdc5e7982a508b7ad9bc938f7f46a1b06feb324a7bab808`. This is the same collection only if this fingerprint matches the one the sender gave you. Checking this folder shows only that it agrees with its own records, not where it came from.

The tasks were written from the Skill tdd, whose fingerprint is `sha256:7dc0ee968fc1f3717b653a11b172f4c89b080edb0d4290d61b21135ffad14099`.

## What it holds

- `tasks/task_reroute-public-seam_1c0dc930/`: the task reroute-public-seam (held out) (corrected by a person), a positive case for claim C1, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_shipping-oracle_1c0dc930/`: the task shipping-oracle (held out) (corrected by a person), a positive case for claim C2, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_exchange-rate-boundary_1c0dc930/`: the task exchange-rate-boundary (corrected by a person), a positive case for claim C3, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_deactivate-account-interface_1c0dc930/`: the task deactivate-account-interface, a boundary case for claim C1, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_theater-cents-adr_1c0dc930/`: the task theater-cents-adr (corrected by a person), a positive case for claim C4, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_retry-backoff-boundary_1c0dc930/`: the task retry-backoff-boundary (held out) (corrected by a person), a positive case for claim C3, with its instruction, the files it starts from, its tests and its reference solutions.
- `export.json`: the collection's records and its acceptance, dated 2026-09-27 at 01:17 UTC, each task's qualification record, and where each task came from.

The tasks marked held out are kept from any agent that improves a Skill on this collection, and a revised Skill's verdict is worked out on them alone. Which tasks are held out follows from a fixed rule; nobody chose it. A task keeps its part in every collection accepted after this one in the same Techtree home, whichever Skill it is for, even when it is built again or appears under another name with the same files; one that was ever studied is never held out. Tasks whose files differ only slightly are not recognised as the same task.

A task marked corrected by a person was edited by hand after it was written and checked again the same way before it was accepted; `export.json` records when, and which files changed.

## What the tasks test

- C1: Tests target public behavioral seams rather than private methods, internal collaborators, or side channels, so they remain valid across behavior-preserving refactors.
  - What shows it: The submitted tests exercise and observe the feature only through exported interfaces and still pass when the implementation is replaced by an equivalent version with different private structure and storage.
- C2: Tests use an independent source of truth for expected results instead of recomputing expectations with the production algorithm.
  - What shows it: The submitted tests pass against the correct implementation and fail against plausible algorithm mutants, including mutants that would also affect expectations obtained by calling production code twice.
- C3: Tests substitute dependencies at system boundaries such as time or external services while using real internal collaborators.
  - What shows it: The tests control the external boundary deterministically, contain no doubles for project-owned collaborators, and continue to pass after those collaborators are reorganized without changing public behavior.
- C4: Code and tests follow the repository's established domain vocabulary and applicable architectural decisions.
  - What shows it: The resulting public API, test descriptions, values, and persisted representations use the terms and constraints defined by the repository guidance rather than generic alternatives.

A positive case is one where following the Skill should give the right result; a boundary case sits at the edge of where the claim applies; a counterexample checks that the Skill is not overused where it would give a wrong result or should change nothing.

## What it leaves out

- The Skill the tasks were written from, tdd. Its name and fingerprint are recorded; its text is not included.
- The conversations and logs from writing the tasks and from checking them.
- Everything else on the computer it came from, such as settings, sign-ins and past runs.

## Before you share it

Each task's tests and reference solutions are included, so anyone who has this folder can read the answers. Give it only to people who check or run the tasks, never to an agent being tested on them.

## Checking it

`techtree forge verify-export` works out again, from the files here:

- every file of every task, against the fingerprints the collection records
- each task's qualification record, against the collection
- the Skill each task was written from, by name and fingerprint, against the collection's
- the collection's members and fingerprint, against its acceptance
- which tasks are held out, against the rule that picks them from the tasks and the parts earlier versions gave them
- the README, against the fingerprint export.json records for it

It can only report what is recorded about:

- the Skill the tasks were written from: its name and fingerprint are recorded, its text is not included
- the proposal and the building of the tasks
- a person's corrections of tasks: when each was made and which files it changed are recorded, the tasks before them are not included
- the qualification runs: their results are recorded, not run again
- the images the tasks were built and checked with
- the acceptance itself: when it was given and how it was answered
- the parts earlier versions of the collection gave their tasks

## Running the tasks yourself

With this folder and the Skill the tasks were written from, you can check the folder, run the tasks on your own computer without the Skill and with it, and compare the two. You need:

- Docker, running linux/arm64 containers, the platform these tasks were built for; they are imported only on a computer whose Docker runs that platform. `techtree forge import` pulls the tasks' base images from the network; after that every task is built and run in a container on your computer with the network off.
- Techtree, installed the way https://techtree.sh/start says. It is installed with uv, which also installs the Python it runs on, Python 3.12 or 3.13.
- Hermes Agent, as `hermes` on your PATH, with a profile named techtree signed in to the provider you will use.
- The Skill the tasks were written from, tdd, in a folder of its own. `techtree forge inspect-skill` prints its full fingerprint on its Fingerprint line: compare it with the Skill's fingerprint at the top of this README. A different fingerprint is a different Skill.

Make the Hermes profile once:

```
hermes profile create techtree --no-alias
hermes -p techtree auth add PROVIDER
```

### What the model calls can cost

Only time limits them. Each try gives the agent its task's own time limit, below, and Techtree stops it 2 minutes after that if it has not stopped. Nothing limits its turns or its tokens, so what a try costs depends on the model and the provider you choose. Running every task once is 6 tries without the Skill and 6 with it; `--repetitions N` on `techtree forge run` runs each task N times.

- reroute-public-seam: 30 minutes
- shipping-oracle: 30 minutes
- exchange-rate-boundary: 30 minutes
- deactivate-account-interface: 30 minutes
- theater-cents-adr: 30 minutes
- retry-backoff-boundary: 30 minutes

### The commands, in order

```
techtree forge verify-export EXPORT_FOLDER
techtree forge import EXPORT_FOLDER
techtree forge inspect-skill SKILL_FOLDER
techtree forge run --arm baseline --collection forgecol_ffa133338756407eba327098051f996c --provider PROVIDER --model MODEL
techtree forge run --arm candidate --collection forgecol_ffa133338756407eba327098051f996c --provider PROVIDER --model MODEL --skill SKILL_FOLDER
techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID
```

EXPORT_FOLDER is this folder; SKILL_FOLDER is the folder holding the Skill and its SKILL.md; PROVIDER is the provider Hermes will be asked for, by the name Hermes uses; MODEL is the model Hermes will be asked for; BASELINE_RUN_ID is the id the run without the Skill prints; CANDIDATE_RUN_ID is the id the run with the Skill prints.

`techtree forge import` checks this folder as `verify-export` does, pulls the tasks' base images from the network, then admits each task again and checks it on your computer the way it was checked when it was built: its image is built with the network off, a run that does nothing must fail its tests, and its solutions must pass or fail them as they should. It calls no model. The collection keeps its id, its parts and its fingerprint, so when the fingerprint matches the sender's, the comparison names the same collection and the same tasks as one made where it was accepted. Each run shows what it will do and asks before it starts.

`techtree forge import` refuses a Techtree home that already holds a collection of this Skill. To give it a Techtree home of its own, add --home FOLDER, naming a new folder, to techtree forge import and to every command after it.

Running every task, the held-out ones too, is right for checking a result: they are kept from an agent that improves the Skill, not from you.
