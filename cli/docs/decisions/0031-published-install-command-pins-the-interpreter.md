# 0031 — The published install command pins the interpreter

Status: binding (founder decision, 2026-08-26). Amends decision 0011
item 2, which fixed the install coordinate as the bare
`uv tool install techtree==0.1.0`.

## What was observed

WP11e's clean-machine journey, and then the WP11b journey before it,
found the same thing. The wheel's own metadata is correct — it declares
Python 3.12 or 3.13 and nothing else. But `uv`, left to choose on a Mac
whose Homebrew Python is 3.14, installs onto 3.14 anyway. The install
reports success. The program runs. And then `techtree doctor` reports
`python_version fail — Python 3.14.7 is outside the supported range`.

A first-time participant's very first Techtree output is a failed health
check, on a machine that did nothing wrong, after running the exact
command this project published.

The certified journey did not hit this because it installed with an
explicit `--python 3.12`, and that difference from the published
coordinate is recorded in `release/acceptance/terminal-e2e.json`. The
certified path and the published path were not the same command.

## Ruling

The published install command pins the interpreter.

The pinned value is **read from the bootstrap document's own
requirements block**, which already declares the Python this release
supports. It is not a second copy of that number written by hand.
Two hand-written copies of one fact is precisely how a document ends up
telling someone to install on an interpreter it also calls unsupported.

`tools/verify_release_core.py` enforces it: the check that the published
command pins the distribution and version now also requires it to pin
the interpreter the same document declares. A release whose install
command and stated requirements disagree does not verify.

## What this does not change

ReleaseCore carries no install command, so its digest is unaffected and
the four byte-identical copies stay byte-identical. Nothing scientific
moves: no Campaign, engine, catalog, Skill or DataPolicy digest changes,
and the certified comparison is untouched. This is the install
coordinate only.

## The related tooling rule

Decision 0011's coordinate is what a participant runs, once, for a
version that exists exactly once. Release engineering and acceptance are
different: they rebuild the same version number repeatedly. Ticket
techtree-python-kml recorded that `uv tool install --force` can serve a
stale cached wheel of the same version — it exits zero, prints
"Installed 1 package", and leaves the previous build in place. Every
runbook and acceptance step that installs a locally built wheel uses
`--reinstall`, never `--force`, and checks the build provenance the
program reports against the wheel it meant to install before any paid
step. That is not a Techtree defect and it is not the published
coordinate; it is a hazard of rebuilding one version, and it can put the
wrong bytes under a paid certification.
