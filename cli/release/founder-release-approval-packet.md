# Founder release approval packet — Climb v0.1

Status: release candidate ready for the final operator rehearsal. This packet is
not an approval. Nothing has been pushed, made public, tagged, deployed,
activated, or published to PyPI.

The final approval must use the exact phrase in
`docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md` and the SHA-256 of
this file as committed.

## Exact candidate

| Coordinate | Value |
|---|---|
| Release | `climb-v0.1.0` |
| Python source | `2e714835469dc0a3fb4bece3ed2f861317fe4d7c` |
| Wheel | `techtree-0.1.0-py3-none-any.whl`, `sha256:5565e553f2e29a145711d5b13f6c03760a99b6c17d404e4a36768513a7660040` |
| Hermes plugin | `db827e714094c89514ea63d3ace1c97e6698589d` |
| Ash candidate records | `a7d3797aea202f09efd3dcbbe9d94ab937796888` |
| ReleaseCore | `sha256:c92b602e8097a6498c49f52587a486f46f2cfd0a7adfe5cb082c5e98527e40a1` |
| Bootstrap | `sha256:3fdadeeb3f435fe08232e401c38751345b4809e9b1bb4202c892b43464c73c76` |
| Campaign | `sha256:ebf029abb266ca74c2def50eb23030511bab0e929c6bf4a68691f9b5afd554b1` |
| Climb | `sha256:a3a5e9c5f9b40d4f08fad54852377e201fd0d6dd4acfa4c565a0edfac324a236` |
| Catalog | `sha256:10a7fcc5de1951c14509947c0512a4eeb247a703cdf01cc3f268580979a7d12c` |
| Engine | `sha256:29b1bbb8327d8f1a9ade03ff4504695ad3783ae34aaaa559e5c6bf9fc95e879b` |
| Network key | `sha256:84ea8ffad2b0fc59f9db9f14b7d97f25c060e71b644dec316ecd582ac040b966` |

The published plugin command remains the plain pinned command. A fresh Hermes
0.20.5 profile refuses that command because a community plugin with a CAUTION
scan is blocked. The guide truthfully presents a separate reviewed `--force`
retry, keeps scanning enabled, and explains the five findings in three
families. The retry installed and enabled the exact commit above; Doctor found
17 tools and 2 hooks.

## What changed after certification

The final increment adds the opt-in public run log and fixes the CLI/Hermes
onboarding path. It changes no Campaign, Climb, task membership, engine,
subject, sampling, budget, scoring, or founder Skill byte. The complete path
classification is in `release/post-certification-change-classification.json`.

Per the founder's instruction on 2026-08-28, this finish uses an existing
verified proof instead of paying to repeat unchanged inference. The selected
proof is `run_0d3e7fc4d24a406b8ae9de74f4edca34`; it passed 339 checks offline
without fetching anything. It is participant-attested and grade P1, not
independently reproduced or platform-witnessed.

Gate 1 approved the starter Skill. On 2026-08-28 the founder separately
approved the shipping improver Skill bytes
`sha256:d5a381bed8ae5ddd5bbd6035775154dc47d2cb11b1da14f11d30ed47ff371678`
after reviewing the one-line correction recorded in ticket
`techtree-python-dme`. That approval does not authorize release publication.

## Public run log

Decision 0038 ships an append-only, arrival-ordered public log, not a
leaderboard. Publication is opt-in. The CLI shows the exact proof-only payload
before consent; prompts, replies, episodes, traces, and worker logs remain
local. Ash verifies the bounded submission, signs an acceptance receipt, and
serves only verified projections. Reposting identical bytes returns the same
receipt and does not create a duplicate. A contributor address is optional,
unverified, stored privately, and absent from public projections. Withdrawal
appends status and does not erase the accepted entry. Raw bundle download and
public reproduction import are not part of v0.1.

An earlier staged HTTPS rehearsal exercised admission, countersigning,
idempotence, arrival order, all 36 task rows, address privacy, and the absence
of raw-bundle routes. It is supporting evidence, not the final receipt for the
candidate above.

The final selected payload shown by the candidate CLI is:

- run: `run_0d3e7fc4d24a406b8ae9de74f4edca34`
- files: 84
- bytes: 238,376
- proof digest: `sha256:a96bc70b67505832f2836694f0887b49991f7eda7fd7f6b87865d4ce24762c57`
- contributor address: none
- endpoint: `https://techtree.sh/api/v1/publications`

The preview was aborted at the confirmation prompt, so this exact payload has
not left the machine. Final publication requires the founder/operator to start
the staged Ash endpoint with the founder-held signing key whose public half
matches the pinned network key, then explicitly approve this payload. No final
receipt or entry identifier is claimed until that succeeds.

## Verification

| Check | Result |
|---|---|
| Python full gate | 3,277 passed, 1 skipped; generated artifacts matched |
| Plugin full gate | 922 passed; format, types, Doctor, 17 tools and 2 hooks passed |
| Ash full gate | 6 doctests and 475 tests passed on the repinned shared tree |
| Ash receipt and candidate checks | 24 passed after repinning |
| Frozen wheel inspection | The preserved wheel's digest and provenance stamp match the candidate |
| Fresh wheel install | Python 3.12; all 169 package files matched the wheel |
| Cross-repository release gate | 26 of 26 passed |
| Selected proof | 339 of 339 checks passed offline |

The wheel contains 174 members: 169 package payload files and five packaging
metadata files. Its embedded provenance stamp names the Python source commit
above.

The separate visual task was idle when the final Ash gate ran. Its uncommitted
shared-tree work is not included in the Ash candidate-record commit above; if
that task changes the tree again, rerun this gate before approval.

## Limits on claims

- Public copy uses the calibrated 20–27 of 36 band, never a guaranteed score.
- Historical cost is an estimate from recorded tokens, never a promised bill.
- The provider exposes a model name, not an immutable model-build identifier.
- The proof establishes integrity and internal consistency, not honest
  execution or independent reproduction.
- Model calls go to Prime; “nothing leaves the laptop” is false.
- The release is a proof of concept for the Verifiers/Hermes/Techtree stack,
  not a benchmark, production evaluation suite, or validated uplift claim.

## Remaining authority boundary

Before final approval: complete the founder-key staged receipt replay and record
the receipt identifiers here.

Even after those checks, no push, public visibility change, tag, deploy,
activation, PyPI upload, or public publication is authorized until the founder
supplies the exact final release approval phrase with this committed packet's
digest. That phrase's historical `Not authorized` list predates decision 0038;
publication of the exact reviewed proof is therefore kept as a separate,
payload-specific consent boundary rather than inferred from Gate 2.
