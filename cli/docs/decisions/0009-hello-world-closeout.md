# 0009 — Founder closeout pack: Hello World naming and presentation scope

Status: binding (founder-supplied, 2026-08-13)
Source: `climb-v0.1-founder-closeout-helloworld` pack, delivered by the
founder. Supersedes the earlier `climb-v0.1-founder-closeout` pack.

Pack integrity, verified by the chief against `CHECKSUMS.json`
(all seven files matched byte size and SHA-256 exactly):

| file | bytes | sha256 |
|---|---|---|
| CHIEF_CLOSEOUT_DIRECTIVE.md | 12704 | `a8edc70163b8a9b00a82bf293e5526cdf181cd55b439ded127af9b40d9627865` |
| NAMING_AND_SCOPE_AMENDMENT.md | 3636 | `7301aba2fd04b5098115a6c6e7a73a41092cef60c7e260cf73256f446b72ea99` |
| RELEASE_COORDINATES_TEMPLATE.json | 4081 | `7a45fbef3cddac105e686de38d7f27044714d472142aa746ff5a20afaa809bb1` |
| FOUNDER_APPROVAL_PHRASES.md | 877 | `442f6cc4ddc0147b71c2da27afebae0e4a4b5851f7812fa03e842121478c0ae8` |
| README.md | 904 | `93aef06d2290afd6b396f2a634143be8a5ae7fb9f9d79fddb0db56dae76ea473` |
| skills/hello-world-starter-v1/SKILL.md | 1497 | `079912df46274a9b7baefc527ed4033f9f83939c8eeda5669869610f4eb0c988` |
| skills/skill-improver/SKILL.md | 4283 | `a9c5ebe9fd51bf33cc80cd346dba977648dd10d8c0dcf2d6b06a26b5aa6f93e9` |

The digests above identify the *drafts*. Final digests are produced in
Phase 1 after compatibility edits (if any) and appear in the founder
skill-approval packet.

## Binding changes

1. **Public naming.** Display title `Techtree Hello World`, subtitle
   `A toy Skill-uplift Climb`, slug `hello-world-climb`, reference
   `hello-world-climb@1`, campaign title `Hello World Skill Uplift`,
   starter Skill `hello-world-starter-v1`, result labels
   `Hello World Uplift Receipt` / `Hello World — Iteration 2`. Task
   family stays `BranchCode v1`. `HelloWorldBench` is forbidden.
   Pinned internal Python package/module names are not renamed for
   presentation. Every public description says this is a toy
   introductory mechanism demonstration, not a capability benchmark.

2. **`rich-terminal-output` is removed from the product release.** It
   is a local development Skill, not a shipped founder Skill. The
   released result path is: signed UpliftReport → deterministic
   presentation payload → deterministic Rich terminal renderer or
   deterministic compact gateway renderer → plugin relays the output.
   No host-model presentation completion exists in released v0.1. The
   plugin must not register `techtree:rich-terminal-output`, must not
   package the Skill, and `techtree_run_result` must relay deterministic
   CLI/gateway output without a host LLM call. Narrative/guard modules
   may remain only if unreachable from the released flow and excluded
   from release promises.

3. **ReleaseCore schema.** No production ReleaseCore has been issued,
   so `rich_output_skill_digest` is removed from the pre-release
   `techtree.release-core.v1` schema (no version bump), and all copies,
   goldens, and cross-repo equality fixtures are regenerated.

4. **Founder Skill set is exactly two:** `hello-world-starter-v1`
   (with the intentional calibration defect: rule 6 uses 7 × *total*
   character count instead of 7 × distinct-character count) and
   `skill-improver` (one-turn, full-file proposal). Both are supplied
   as drafts in the pack; workers make only compatibility edits
   required by committed code and never weaken guards.

5. **Calibration hard gate** (unchanged from 0007 R4): baseline 0–2/36,
   starter v1 20–27/36 (prefer 24), v2 ≥32/36, ≥6 task uplift,
   ≤1 regression.

## Chief sequencing decisions (recorded here, mine)

- The in-flight WP11-exec and WP11-engine work found uncommitted after
  the process exit is completed and committed *first*, before the
  Phase 0 naming migration, so per-ticket history stays reviewable.
- The paid engine reference rerun is deferred until after the naming
  migration lands, so the certification run references the final
  Hello World campaign digest instead of a superseded one. One rerun,
  not two.
- Phase 0 order across repos: techtree-python regenerates the
  ReleaseCore schema and catalog first; the plugin and Ash apply their
  naming/removal changes and refresh release copies after, so
  cross-repo equality fixtures never point at a shape that no longer
  exists.
- Founder sign-off gates are unchanged: the skill-approval packet
  (Phase 2) and the release-coordinate packet (Phase 6) both stop for
  the exact approval phrases in the pack; nothing publishes, tags,
  deploys, or flips `placeholder_release` before then.
