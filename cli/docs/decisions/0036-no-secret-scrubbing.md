# 0036 — Techtree does no secret scrubbing and no secret scanning

Status: binding (founder ruling, 2026-08-26).

## Ruling

Techtree ships no secret-shaped-string detection of any kind. Two mechanisms
are deleted outright, not disabled:

1. **The text scrubber** — the redaction of credential-shaped strings from
   error messages, the worker log, the run journal, engine-installer output,
   and the improvement context.
2. **The Skill scanner's secret patterns** — the rules that refuse a Skill for
   containing text that looks like a credential.

## The founder's reasoning

> "why are we concerning ourself with how another agent redacts things? or that
> a Skill file has secrets? maybe the skill file is about security and we have
> false positives. we are assuming too much and this is brittle."

Both mechanisms assume a secret can be recognised by its shape. It cannot, in
either direction. The Skill scanner's failure is the worse of the two and has
no escape hatch: a Skill *about* security — one documenting an authorization
header, or carrying an example key block — is refused outright, with no flag
anywhere in the code to overrule it. In a product whose premise is that people
bring their own Skills, blocking legitimate work on a regex is a worse failure
than the thing it prevents.

## The objection that was raised, and the answer

The chief raised one, and it is recorded because it was the stated condition
for changing this ruling. The scrubber was not only a display filter, as first
believed and reported. It also ran at write time on three paths, one of them
the run journal, which is append-only by this project's own rules. The
concrete case: engine installation runs a subprocess with the operator's own
environment, and a failing package manager quotes the operator's index
configuration back — a private index URL carries its password inline. Without
the scrubber that password is written permanently into a run's evidence.

The founder's answer, 2026-08-26: credentials are moving to agent
authentication rather than inline URL secrets, so the case the scrubber was
guarding stops applying.

The ruling stands on that basis. It is recorded here rather than inferred so
that if inline credentials ever return to a supported path, the reason this
was removed can be re-examined rather than rediscovered.

## What is NOT removed, and shares only a word

- **The environment allowlist** (`scrubbed_child_environment`,
  `scrubbed_worker_environment`). A fixed list of variable names a child may
  inherit — `PATH`, `HOME`, `TMPDIR`, `TECHTREE_LOG_LEVEL` — and nothing else
  gets through. It is not pattern matching, it is what stops the evaluation
  credential reaching a subprocess with no business holding it, and the
  founder's standing rules say it may never be weakened.
- **Control-character stripping.** Not secret detection: it stops borrowed
  output redrawing someone's terminal.
- **Refusals based on a Skill's shape** — size, file count, symlinks, non-text
  bytes. None of these guess at meaning.
- **Memory-address normalisation**, which happens to live in the same function.
  It exists so an error message does not vary between runs, and has nothing to
  do with secrets.

## Consequence to state plainly

An error message, a worker log line, or a run journal entry now carries
whatever the underlying tool printed, verbatim. If a tool prints a credential,
Techtree writes it down. That is the accepted trade: no guessing, in exchange
for no filtering.
