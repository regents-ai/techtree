# 0024 — iOS out; agent-first Hermes community onboarding

Status: binding (founder ruling, 2026-08-14). Supersedes the
phone/gateway framing of WP11f and the reference-gateway-profile
decision (spec wp9-wp11 §4.4's REFERENCE_GATEWAY selection is
resolved as: none in v0.1).

## 1. Scope ruling

iOS is not part of Climb v0.1. No iOS app, no named phone client, no
claim that a live phone path was certified. All iOS, phone-app, and
Regent-app references are removed from release tickets, copy,
acceptance claims, and the Gate-2 packet. (Engineering-internal
docstrings about small-screen rendering in the compact renderer are
design rationale, not release claims, and stay.)

## 2. The reference onboarding path

Hermes community user → gives one prompt to their existing Hermes
agent → Hermes reads the pinned Techtree plugin instructions → shows
the exact install plan → explicit user approval → installs and
enables the plugin → one Hermes restart/reset → plugin
installs/verifies techtree-python → Doctor → Hello World Climb.

Hermes officially supports installing third-party plugins from a Git
repository and enabling them explicitly; installed plugin tools load
when Hermes starts.

## 3. WP11f replaced

ndq.3.6 becomes "WP11f — Agent-first Hermes community onboarding
E2E". Acceptance proves:
1. A user with Hermes already installed can paste one instruction.
2. Hermes reads the exact pinned GitHub release instructions.
3. It explains prerequisites, commands, cost, provider disclosure,
   and local-data policy.
4. It asks before installing anything.
5. It installs/enables the exact plugin release.
6. It tells the user to restart/reset Hermes once.
7. After restart, the plugin offers the pinned CLI installation.
8. It asks before installing the CLI.
9. It runs release verification and Doctor.
10. It starts Hello World only after the paid-run approval.
11. Every CLI/plugin response includes the useful next step.
12. No command uses `main`, `latest`, or an unpinned package
    coordinate.

The WP11-gateway-profile ticket is closed as superseded: there is no
gateway to pin.

## 4. Website hero/install copy (binding copy)

Primary block — "Give this to your Hermes agent":

```text
Read the pinned Techtree installation guide at
https://techtree.sh/start. Review the exact GitHub plugin release and
installation commands with me. Ask for my approval before installing
software or spending model credits. Install and enable the Techtree
Hermes plugin, tell me when Hermes must be restarted, then use the
plugin to install and verify the Techtree CLI and run the Hello World
Climb. Do not upload my local evaluation artifacts.
```

The rendered page may substitute an exact commit-specific GitHub URL
from BootstrapRelease, e.g.
`https://github.com/regents-ai/techtree-hermes/tree/<FULL_COMMIT>`.
Never hardcode `main` in the prompt.

Alternate human path:

```text
Prefer installing it yourself?

1. Install the exact pinned Hermes plugin shown below.
2. Restart Hermes.
3. Ask: "Set up Techtree and run the Hello World Climb."
```

The exact commands come from the verified BootstrapRelease, never
duplicated manually in website prose.

## 5. GitHub README opening (binding copy, plugin repo)

```markdown
# Techtree for Hermes

## Give this repository to your Hermes agent

Paste this into Hermes:

> Read this repository's pinned Hello World installation instructions.
> Explain the exact commands, prerequisites, expected model cost, and
> privacy terms. Ask before installing the plugin, installing the
> Techtree CLI, or starting a paid run. After the plugin is enabled,
> tell me when to restart Hermes, then continue with Techtree Doctor
> and the Hello World Climb.

Techtree runs a neutral agent and a Skill-enabled agent against the
same toy tasks, shows the measured difference, and creates a signed
local receipt you can verify offline.
```

## 6. New-to-Hermes copy (binding copy)

"New to Hermes Agent? Hermes is an open-source agent made by Nous
Research. Nous Portal provides model access, hosted tools, and
cloud-hosted Hermes under one account. Explore it at
https://portal.nousresearch.com/."

With the precise qualifier directly below it: "Techtree Hello World
currently requires a Hermes host where you can install the plugin and
CLI, access a terminal, run Docker, and authenticate with Prime. The
Nous Portal cloud-hosted path is not yet a separately certified
Techtree execution environment."

## 7. Next-step response rule

Every successful plugin and CLI response ends with one immediate
action, e.g.: "Plugin installed. Next: restart Hermes so Techtree's
tools are loaded." · "Techtree CLI installed and verified. Next: run
Techtree Doctor." · "Doctor passed. Next: inspect the Hello World
Climb." · "Hello World prepared. Next: review the Skill-only change
and estimated maximum cost." · "Run started: run_… Next: ask me for
its status at any time." · "Receipt verified locally. Next: inspect
the measured difference or request one Skill revision."

The existing NextAction machinery is the vehicle; the rule is that no
successful surface ends without one.

## 8. Change discipline

All copy changes land under 0022 item 4 (copy classification, full
battery). The plugin is frozen at its certified commit; its README
and response-copy changes are classified non_scientific_copy in the
Gate-2 packet.
