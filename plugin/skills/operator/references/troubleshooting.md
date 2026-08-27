# When something is blocked

Every tool that refuses gives a reason and, where one exists, a repair. Relay
both. Do not work around a refusal.

## Techtree is not installed

Run the readiness check. It offers a pinned install command that needs the
user's approval. If `uv` is missing, install that first — the plugin will show
the documentation link and the usual options, and will not install it for you.

## This plugin build is a development build

Its release coordinates have not been chosen yet, so it will not install
Techtree and cannot prepare the guided introduction. Say that plainly; there
is nothing to fix locally, and a published build is the answer.

## Doctor reports a blocking failure

Something the run needs is not ready — Docker not running, the evaluation
engine not installed or unverified, evaluation credentials missing. The check
names it. Preparing a comparison is refused until it is resolved, which is
correct: a run started into a broken host wastes model tokens and produces
nothing.

## The installed Techtree belongs to a different release

The plugin and the CLI must be from the same release, or a comparison could
run against a different engine or catalogue than the one this build describes.
The readiness check names each coordinate that differs.

## A run failed or was cancelled

Ask for its status; Techtree reports the phase and, when it failed, its own
error. A failed run has no result and no proof — do not describe a partial run
as a result.

## A result looks wrong

Verify the proof. If the proof verifies and the number is still surprising,
the number is what happened; report it. If the proof does not verify, say so
loudly and do not present the numbers as evidence of anything.

## The tool answer was truncated

Long answers are cut, and say when they were. Nothing is lost: the same
information is available from the Techtree command the message names, run in a
terminal.
