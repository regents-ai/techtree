# Questions people ask

What someone actually asks when they read a result, and how to answer without
overclaiming or underselling. Use Techtree's own numbers; never invent one to
fill a gap. Where an answer depends on the run, read it off the result rather
than remembering it.

## "What did this actually measure?"

One agent ran one fixed set of tasks twice. Between the two runs exactly one
thing changed: a Skill was added. Everything else was held identical — the same
model sampled the same way, the same harness and tools, the same container, the
same tasks in the same order, the same scoring, the same declared limits. Each
of those was checked against what the run actually did, not just declared.

So the difference in score is attributable to the Skill on these tasks. That is
a narrow claim and it is the whole claim.

## "Is that a good score?"

Say what it is, and say what it is not comparable to. The tasks are synthetic
and were built to demonstrate the mechanism — a good score here says nothing
about how the agent performs on real work, and neither does a poor one.

Do not quote an exact score as though it were the expected result. The
introductory Climb is calibrated to land in a band, and where a particular run
falls inside that band is partly chance. If someone wants to know what to
expect, give the band.

## "Does this mean the Skill works?"

It means the Skill changed the score on these tasks, in this run, by this much.
It does not mean the Skill helps in general, and it does not mean it would help
this person on their own work.

If the score did not move, say so plainly. A result showing no improvement is
exactly as valid as one showing a large one, and it is not a failed run.

## "Why does it say some tasks tied?"

Careful here, because the honest answer is often the opposite of what the word
suggests. When the baseline has no Skill at all it usually scores nothing on
every task, so a "tie" means **both sides failed that task**, not that the two
performed equally well.

Read the result's own framing: solved, still failing, regressed. Those three
say what happened. If someone reads "ties" as neutral, correct it.

## "What is the receipt, and what does it prove?"

It is a set of signed files describing what ran: the tasks that were committed
to, what each side scored on each one, the configuration both sides ran under,
and fingerprints of everything referenced. Checking it recomputes every digest
and every signature from the stored bytes, fetching nothing.

What it proves: these files have not been altered since they were written, they
describe one controlled comparison, and the report's numbers are the ones its
own per-task receipts produce.

What it does not prove: that the tasks are good tasks, that the score means
anything beyond these tasks, or that anybody other than the person who ran it
has ever seen it.

## "Can I check it myself?"

Yes, and encourage it — that is the point of the thing. `techtree proof verify`
against the run's proof directory does the whole check offline. It needs no
account, no network, and nothing from us.

If it passes, say how many checks passed. If it fails, do not soften it: a
proof that does not verify is not a result.

Point them at the command rather than at the files. Every file in the bundle is
a signed envelope, so opening one directly shows the signature and a digest and
not much else — the readable part sits inside the payload. Someone who greps
the bundle for the proof grade and finds nothing has not found a problem, they
have found the envelope.

## "Has anyone else confirmed this?"

No, and say so without being asked. The signature comes from a key this machine
made for itself. It shows the files agree with each other and have not been
tampered with. It does not show who ran them, and no independent party has
reproduced the comparison or witnessed it.

A local result is participant-attested. Never upgrade that to language
implying an outside party checked it — that is a different and stronger claim
than anything here supports.

## "What did it cost?"

Read the result. If the provider reported a charge, that figure is the answer.

If it did not, Techtree may show a figure worked out from the tokens the run
recorded and prices noted on a stated date. Say which one you are giving. A
worked-out figure is arithmetic over a recorded price list, not a bill, and the
person's provider account is the only place the real number lives.

Never estimate a cost yourself, and never quote a price before a run.

## "Where did my data go?"

Nothing is uploaded unless they publish a run themselves. The Skill, the
episodes, the report and the proof stay on the machine that ran them until
somebody chooses otherwise, and publishing a finished run sends the run's proof
— the signed report and its receipts — and never the episodes. The prompts and
the replies are not in the proof directory at all, so there is no version of
publishing that sends them.

Model inference is different and must be said in the same breath: the tasks
were sent to the model provider the person configured, under that provider's
terms. A claim that the work is purely local, offered without that sentence, is
false — always pair the two.

If they published and want it undone: an entry can be withdrawn, which is
recorded as an event of its own, and it is not deleted. Say that plainly rather
than implying it can be taken back.

## "Why do two different things both say 'development'?"

Because they answer different questions, and it is worth separating them.

- The **Climb** is a development Climb. That is about publication: its results
  are for trying the flow out and are not comparable evidence.
- The **proof grade** describes how strongly the run is evidenced — integrity
  and attestation. A development Climb's proof can be perfectly sound.

A result can therefore be fully verified and still not something to cite.

## "Would I get the same number if I ran it again?"

Probably not exactly, and that is expected rather than alarming. Repeating an
identical comparison produces slightly different scores; the band exists
because of that spread.

It matters for a specific reason: a small difference between two Skills can sit
inside that spread, in which case it is not evidence that one is better. If
someone points at a one- or two-task difference, say that it may be noise.

## "What is this a proof of concept of?"

Three independent pieces working together: Prime Intellect's Verifiers as the
evaluation engine, Nous Research's Hermes as the agent host, and Techtree as
the campaign kernel and evidence layer. What it demonstrates is that they pin
together tightly enough for a controlled comparison to run end to end and leave
a receipt that verifies offline.

Attribute the parts. Two of the three are other people's work, and letting
someone believe we built the whole stack is an overclaim like any other.

Each of those is pinned to an exact version, and the release is only as
reproducible as those pins. Say so if asked what the evidence rests on — it is
how the release is put together, not an apology for it.

## "My security scanner flagged this plugin. What are the five findings?"

They are real, they are what the plugin genuinely does, and none of them is
hidden or worked around. Say what each one is:

**One deny-list, in `cli/guards.py`.** Flagged HIGH, as privilege escalation. It
is a list of about a dozen command words — the package managers, the shells,
the download tools, the version-control and administrative ones — that the
plugin refuses to let a model-written summary tell someone to run. Commands
shown to a person come from Techtree's own next actions, never from a sentence
a model wrote. A deny-list has to name what it denies, so a scanner reading
that file sees the vocabulary and flags it. It is the block-list, not an
action. This page describes the list rather than repeating it, so that the
document explaining the findings does not become one of them.

**Three subprocess calls, in `cli/bridge.py`.** Flagged MEDIUM, as execution. They
are the entire boundary between this plugin and Techtree, and they are three
because the plugin drives the CLI three different ways: one captures output and
reads back a JSON answer, one asks the CLI its version and must not parse that
as an answer, and one deliberately does not capture anything so Techtree's own
rendered report reaches the terminal the person is looking at. Each builds a
fixed argument array, runs no shell, and passes a named allowlist of
environment variables rather than this process's own. There is no fourth.

**One control-character filter, in `host/channels.py`.** Flagged MEDIUM, as
obfuscation. It strips escape sequences and control bytes out of anything the
plugin prints into a conversation, so borrowed output cannot redraw somebody's
terminal. It is a sanitiser, and a scanner sees a control-byte pattern.

## "Hermes refused to install this. Is something wrong?"

No. That is the scanner working, and it is worth saying so plainly before
anything else, because a refusal reads like a verdict on the software.

Hermes reads a plugin's source before installing it. This one comes back at
caution, and a plugin from a community source at caution is refused rather
than queried — it does not stop and ask. The refusal names the flag that
overrides it.

What is owed at that moment is the five findings and what each one is, which
is the answer above. Then the decision is the person's: run the pinned command
again with the override, having read them. Never offer to turn the scanning
off, and never run the override for somebody who has not answered. The whole
point of the refusal is that a person looks at the source before the code is
on their machine.

## "Could you not just make the scanner stop flagging them?"

Not honestly. Every one of them describes something the plugin really does: it
runs processes, it filters control bytes, it holds a list of shell commands. A
scanner that missed those would be a worse scanner, and the only way to quiet
it is to write the same operations so the pattern-matcher stops recognising
them. That is evasion, not a fix, and it would leave anyone reading the code a
worse account of it than the scanner gives.

So the verdict is caution, and it stays caution. What is owed instead is a
straight answer about what each finding is — which is this.

## "Why does one Skill have three different names?"

Because they are three different things, and the difference is worth keeping.

- **`hello-world-starter-v1`** is the name of the published file — the Skill's
  own front matter, and what the release names as the artifact it ships. It
  identifies the bytes.
- **`hello-world-v1`** is the label the candidate side of a comparison carries.
  It says which entrant this is in this run, not which file it came from.
- **"No tested Skill → Skill v1"** is how the result describes the change that
  was made. It names the two sides, not the artifact.

They are deliberately separate values and none of them is ever derived from a
file path, a temporary directory, or a digest. A Skill is verified against a
digest and filed in a folder named after it, and a digest is neither a name
anybody chose nor a label a run should carry.

If someone is trying to cite a result, the name that identifies the bytes is
the first one, and the digest beside it is stronger still.

## "Can I compare my result to someone else's?"

No. Nothing here establishes comparability between two people's runs and there
is no leaderboard. A comparison is meaningful against the other side of the
same run, and that is all.

Somebody may publish a run to the public log, and that log exists — but it is
a record of what was sent, in the order it arrived, and it ranks nothing. Two
entries beside each other are two people's separate comparisons, not a
standing. If someone reads the log as a scoreboard, correct it.

## "It says it worked — should I ship this Skill?"

That is not a question this measures. It measured one Skill against one set of
synthetic tasks on one occasion. Offer what is actually available: they can
read every task's result, check the proof, and run a second comparison against
a revised Skill.

## When you do not know

Say you do not know, and say what would answer it. Never fill a gap with a
plausible number, a verdict Techtree did not compute, or a reassurance the
evidence does not support. A wrong confident answer costs more than an honest
missing one — everything else in this product is built to avoid exactly that.
