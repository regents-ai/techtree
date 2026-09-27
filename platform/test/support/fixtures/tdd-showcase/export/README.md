# Collection forgecol_ed65fc14bb8949678812c1eab5fe3a56, version 1

This folder is a private copy of one accepted collection of tasks, made by Techtree on 2026-09-27 at 07:00 UTC. Nothing in it has been published.

The collection's fingerprint is `sha256:d5c38ea0f542023f0dd24c8f19d62806b162cf951e4a14e725c61b6722a4045c`. This is the same collection only if this fingerprint matches the one the sender gave you. Checking this folder shows only that it agrees with its own records, not where it came from.

The tasks were written from the Skill tdd, whose fingerprint is `sha256:7dc0ee968fc1f3717b653a11b172f4c89b080edb0d4290d61b21135ffad14099`.

## What it holds

- `tasks/task_tdd-cart-total_f844b506/`: the task tdd-cart-total, a positive case for claim C1, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-date-ranges_f844b506/`: the task tdd-date-ranges (held out), a boundary case for claim C1, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-cache-rewrite_f844b506/`: the task tdd-cache-rewrite (held out), a counterexample for claim C1, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-slugify_f844b506/`: the task tdd-slugify (held out), a positive case for claim C2, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-roman-numerals_f844b506/`: the task tdd-roman-numerals, a boundary case for claim C2, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-parser-kept_f844b506/`: the task tdd-parser-kept (held out), a counterexample for claim C2, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-rate-limiter_f844b506/`: the task tdd-rate-limiter, a positive case for claim C3, with its instruction, the files it starts from, its tests and its reference solutions.
- `tasks/task_tdd-csv-report_f844b506/`: the task tdd-csv-report, a counterexample for claim C3, with its instruction, the files it starts from, its tests and its reference solutions.
- `export.json`: the collection's records and its acceptance, dated 2026-09-27 at 07:00 UTC, each task's qualification record, and where each task came from.

The tasks marked held out are kept from any agent that improves a Skill on this collection, and a revised Skill's verdict is worked out on them alone. Which tasks are held out follows from a fixed rule; nobody chose it. A task keeps its part in every collection accepted after this one in the same Techtree home, whichever Skill it is for, even when it is built again or appears under another name with the same files; one that was ever studied is never held out. Tasks whose files differ only slightly are not recognised as the same task.

## What the tasks test

- C1: Tests written test-first check behaviour through the public interface, so they still pass when a correct implementation is written another way.
  - What shows it: The agent's tests pass against a second correct implementation of the same module that shares none of the first one's internal names.
- C2: Tests written with the red-green loop catch wrong behaviour instead of restating the code.
  - What shows it: The agent's tests fail against each deliberately wrong implementation the checker keeps back.
- C3: The loop leaves one test for each behaviour asked for, without mocking the module's own parts.
  - What shows it: Removing any one asked-for behaviour from a correct implementation makes at least one of the agent's tests fail, and no test replaces a function of the module under test.

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

Only time limits them. Each try gives the agent its task's own time limit, below, and Techtree stops it 2 minutes after that if it has not stopped. Nothing limits its turns or its tokens, so what a try costs depends on the model and the provider you choose. Running every task once is 8 tries without the Skill and 8 with it; `--repetitions N` on `techtree forge run` runs each task N times.

- tdd-cart-total: 30 minutes
- tdd-date-ranges: 30 minutes
- tdd-cache-rewrite: 30 minutes
- tdd-slugify: 30 minutes
- tdd-roman-numerals: 30 minutes
- tdd-parser-kept: 30 minutes
- tdd-rate-limiter: 30 minutes
- tdd-csv-report: 30 minutes

### The commands, in order

```
techtree forge verify-export EXPORT_FOLDER
techtree forge import EXPORT_FOLDER
techtree forge inspect-skill SKILL_FOLDER
techtree forge run --arm baseline --collection forgecol_ed65fc14bb8949678812c1eab5fe3a56 --provider PROVIDER --model MODEL
techtree forge run --arm candidate --collection forgecol_ed65fc14bb8949678812c1eab5fe3a56 --provider PROVIDER --model MODEL --skill SKILL_FOLDER
techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID
```

EXPORT_FOLDER is this folder; SKILL_FOLDER is the folder holding the Skill and its SKILL.md; PROVIDER is the provider Hermes will be asked for, by the name Hermes uses; MODEL is the model Hermes will be asked for; BASELINE_RUN_ID is the id the run without the Skill prints; CANDIDATE_RUN_ID is the id the run with the Skill prints.

`techtree forge import` checks this folder as `verify-export` does, pulls the tasks' base images from the network, then admits each task again and checks it on your computer the way it was checked when it was built: its image is built with the network off, a run that does nothing must fail its tests, and its solutions must pass or fail them as they should. It calls no model. The collection keeps its id, its parts and its fingerprint, so when the fingerprint matches the sender's, the comparison names the same collection and the same tasks as one made where it was accepted. Each run shows what it will do and asks before it starts.

`techtree forge import` refuses a Techtree home that already holds a collection of this Skill. To give it a Techtree home of its own, add --home FOLDER, naming a new folder, to techtree forge import and to every command after it.

Running every task, the held-out ones too, is right for checking a result: they are kept from an agent that improves the Skill, not from you.
