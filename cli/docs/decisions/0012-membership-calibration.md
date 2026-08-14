# 0012 — Introductory membership adjusted to make the calibration band reachable

Status: binding (chief decision under the closeout directive's explicit
remedy clause, 2026-08-13). Founder may veto before paid calibration.

## Finding (static analysis, zero spend)

The intentional starter defect (7 × total characters instead of 7 ×
distinct characters) yields the correct answer exactly on
all-unique-character inputs. The frozen 36-task membership contains 15
such inputs, so a subject following starter v1 perfectly scores at most
15/36 — a hard miss of the ratified band (20–27/36, prefer 24). The
recorded reference run (36/36 with the correct Skill) shows arithmetic
reliability is not the limiter; the membership composition is.

Every alternative singular defect was priced and none lands in band
(weight change, dropped term, zero-indexing, a=0 mapping, modulo 96:
0/36; half-input distinct: 1/36; repeats-counted-twice: 15/36). The
defect family is effectively binary, so the defect is not a usable
lever. The two rules never collide on failed tasks (7·e mod 97 ≠ 0 for
all occurring duplicate excesses), so v2 uplift stays unambiguous.

## Decision

Adjust the public introductory membership — the remedy the closeout
directive prefers ("Prefer adjusting only the public introductory
membership or the singular intentional defect if calibration misses
the band"):

- Swap 9 repeated-character inputs for all-unique inputs, targeting
  exactly 24 agreement tasks (the preferred calibration point);
  12 disagreement tasks remain, comfortably above the ≥6 v2-uplift
  requirement.
- The scorer and the answer rule are untouched; only which inputs are
  in the public introductory membership changes.
- The regeneration happens in ONE opening that also adopts
  hello-world derivation labels for the campaign and data policy
  (previously kept as procedure-transfer-dev-*@1 solely to avoid
  orphaning recorded evidence — this change orphans it anyway, and the
  paid re-record was already scheduled by 0009).
- Cascade accepted: proving inputs → membership commitment → campaign
  and policy digests → taskset validation receipt and evidence →
  catalog → ReleaseCore. All regenerated, drift-checked, and
  re-recorded by the already-planned paid sitting.

## Ratifications from the same report

- Starter Skill install location:
  `release/skills/hello-world-starter-v1/SKILL.md` (founder-owned
  release input, beside `release-inputs.json`; the CLI ships no Skill
  bytes and the website serves the artifact).
- The 0010 item 2 CLI disclosure lives in `techtree skill starter`
  output (`Purpose: intentionally incomplete introductory Skill`) —
  the command that hands over the Skill and knows what it is; the
  mounted Skill's silence is contract-tested.
- The deferred engine reference rerun and the calibration comparison
  are one paid sitting, two comparisons (a comparison has two
  variants; the 0→36 reference proof needs the correct Skill as its
  candidate). Estimated programme: ~USD 1.04 (~1.56 with 50%
  contingency) against ~3.70 remaining; every run under the 1.00 cap.
