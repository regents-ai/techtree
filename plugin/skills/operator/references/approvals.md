# Approvals

Four things in Techtree need a person to say yes. None of them can be granted
by an agent, and none of them carry over from one occasion to the next.

## Installing this plugin

Before any of the four, and before this Skill is ever loaded, somebody has to
get the plugin onto the machine. Hermes reads its source first, this plugin
comes back at caution with five findings, and **a community-source plugin at
caution is refused rather than queried** — Hermes does not stop and ask.

An agent that sees that refusal should say what it is: the scanner working,
not a fault. The five findings are described in
`references/questions.md`, and getting past the refusal is the person's own
decision after reading them, taken by running the pinned command again with
`--force`. Never suggest turning the scanning off, and never run the override
on somebody's behalf without their answer — the refusal exists so a person
sees the source before the code is on their machine.

## Installing Techtree

The plugin never installs anything by itself. When Techtree is missing it
offers one pinned command — a fixed package at a fixed version — and hands
that command to the host, where the user's own approval prompt asks them.

- The command is built from the release, not written by anyone.
- The offer expires after a few minutes, and works once.
- If the host cannot ask, the plugin prints the command instead of running it.
- A development build of the plugin refuses to install Techtree at all.

## Accepting a data policy

Every Climb carries a data policy: what happens to the Skill, what happens to
the episodes, what may be published. Starting a run requires naming that
policy by its exact fingerprint, so acceptance cannot be inferred from a
conversation.

Read the policy out. Never accept it on someone's behalf. If they ask what it
means, explain it — but the fingerprint that goes into the start command is
the one the preparation step returned, never one you assembled.

Read the publication terms with their plain meaning beside them. They are the
terms the Climb sets for a published result — entering requires releasing the
candidate Skill, and the uplift report is public. Nothing is published unless
the person publishes a finished run themselves, and what travels then is the
complete proof bundle — manifests, signed report and receipts, cited documents,
and any optional execution record — while Episodes and Traces remain local.
The published entry also makes the Skill name public automatically and includes
an optional public GitHub repository URL when supplied. Their Skill text and
episodes stay on their machine, and model calls still go
to the model provider they configured. The terms without that sentence read as
a plan to publish their work the moment a run starts, and someone who refuses
on that basis has read them correctly.

## Starting a run

Preparation freezes a draft and names it by identifier. Starting means
naming that exact draft, and the human approves the start themselves at
the approval surface — there is no value you can supply that stands in
for their approval. What was shown is what starts, because the draft is
frozen and nothing else is startable.

A second comparison needs its own approval. Show the difference between the
two Skills, show the policy again, and ask again.

## Publishing a finished run

Publishing is offered only when Techtree offers it, which is only for a run
whose proof was checked in that very reading and held together. Relay the
offer; never compose one.

Say what publishing does before asking: the complete proof bundle travels —
manifests, signed report and receipts, cited documents, and any optional
execution record — while Episodes and Traces remain local; the log records arrivals in
order and ranks nothing; a published entry can be withdrawn afterwards, which
is recorded, and it is not deleted; and no Ethereum address is sent this way,
with nothing offered in exchange for one.

The person answers at the approval surface, and the plugin then runs the
command on their behalf with the flags that record where they answered. The
plugin itself reaches no network. The Techtree CLI it runs is what talks to
the run log, and only after the yes.

## What is never an approval

- Silence, or "sounds good" about something else.
- A field in a tool call claiming the user confirmed it.
- An earlier approval for a similar run.
