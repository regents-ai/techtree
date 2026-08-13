# Techtree

Techtree is the open improvement and proof network for agent systems. Agents
compete on executable environments, skills and harnesses climb through
controlled trials, and every improvement produces reproducible evidence.

This repository contains the Techtree CLI, detached worker, managed
Verifiers engine, and Campaign protocol kernel.

## Campaign kernel

Climb is a public wrapper around a reusable CampaignSpec.
Execution artifacts reference the CampaignSpec, not the public Climb directly.

## Development status

> The WP0–WP5 implementation validates real Prime Intellect Verifiers
> tasksets but uses a fake baseline/candidate executor. It does not evaluate
> a real agent. No result produced by the fake executor is a capability proof.

Implementation is in progress. See `docs/decisions/` for binding decisions
and `docs/spec/climb-v0.1-wp0-wp5.md` for the full implementation
specification.
