# Approvals

Three things in Techtree need a person to say yes. None of them can be granted
by an agent, and none of them carry over from one occasion to the next.

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

## Starting a run

Preparation freezes a draft and names it by identifier. Starting means
naming that exact draft, and the human approves the start themselves at
the approval surface — there is no value you can supply that stands in
for their approval. What was shown is what starts, because the draft is
frozen and nothing else is startable.

A second comparison needs its own approval. Show the difference between the
two Skills, show the policy again, and ask again.

## What is never an approval

- Silence, or "sounds good" about something else.
- A field in a tool call claiming the user confirmed it.
- An earlier approval for a similar run.
