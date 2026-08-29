# Founder release approval packet — Climb v0.1

Status: v0.1.1 release candidate ready for final approval. This packet is not an
approval. The existing v0.1.0 release and public result remain live; the v0.1.1
commits have not been pushed or tagged, the wheel has not been uploaded to
PyPI, and the Ash commit has not been deployed.

The final approval must use the exact phrase in
`docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md` and the SHA-256 of
this file as committed.

## Exact candidate

| Coordinate | Value |
|---|---|
| Release | `climb-v0.1.0` |
| Python wheel source | `614daffbcbd294be4646adfdec26f95337c4f7ed` |
| Wheel | `techtree-0.1.1-py3-none-any.whl`, `sha256:51f720e0636d406d432a415b69001261744d4f70149307a0493a4f2019e4b5ce` |
| Hermes plugin | `ca22ee782f5572b179c665c2c2a33120171f0158` |
| Ash candidate | `3211712e4b821009cee3250c0c92fda803fdb9a9` |
| ReleaseCore | `sha256:07bfd0f0f07c4df08e879c2ff6dbb8e17c6363445e15be62c6ec9549989d67fa` |
| Bootstrap | `sha256:f288817ef25f1e06de0547eff1445cb387fb222005082d9bd445e10f93db0a58` |
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

Per the founder's instruction on 2026-08-28, this finish does not pay to repeat
unchanged inference. The existing verification anchor is
`run_0d3e7fc4d24a406b8ae9de74f4edca34`; it passed 339 checks offline without
fetching anything. It is participant-attested and grade P1, not independently
reproduced or platform-witnessed. A later full Hermes journey supplied the live
publication evidence below.

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

Automated and staged checks exercised admission, countersigning, idempotence,
arrival order, all 36 task rows, address privacy, and the absence of raw-bundle
routes. The full Hermes journey then published a real proof through the live
endpoint.

The successful live publication is:

- run: `run_86bb7176135d49e3a0577630e952c7f3`
- files: 84
- bytes: 238,376
- proof digest: `sha256:e8ef7cb4f906a3ca75310415dbeed2302d8e9d195ce7ed044d83ba7f4480ac91`
- receipt payload digest: `sha256:0cc5a2c89d295fad5596845c4c35ba67ca96f86f2b0eb1fdaf23ead46a4b150a`
- entry identifier: `72e151ba-205b-4385-9844-750222d7a105`
- log sequence: 1
- admission checks: 17 passed
- contributor address: none
- GitHub URL: none
- endpoint: `https://techtree.sh/api/v1/publications`

The receipt is signed by the pinned network key. It was issued while v0.1.0's
viewing route was active. The v0.1.1 ReleaseCore and Ash candidate move public
viewing to `https://techtree.sh/results/<proof-digest>` and intentionally keep
no `/runs` alias. The publication endpoint is unchanged. No further paid run,
signer rehearsal, or proof upload is required.

## Verification

| Check | Result |
|---|---|
| Python full gate | 3,289 passed, 1 skipped, 298 deselected; generated artifacts matched |
| Plugin full gate | 927 passed; format, types, Doctor, 17 tools and 2 hooks passed |
| Ash full gate | 6 doctests and 479 tests passed at `3211712e4b821009cee3250c0c92fda803fdb9a9` |
| Focused release checks | 99 Ash tests passed after the final route and release re-pin |
| Frozen wheel inspection | The preserved wheel's digest and provenance stamp match the candidate |
| Fresh wheel install | Python 3.12; all 169 package files matched the wheel |
| Cross-repository release gate | 26 of 26 passed |
| Selected proof | 339 of 339 checks passed offline |

The wheel contains 174 members: 169 package payload files and five packaging
metadata files. Its embedded provenance stamp names the Python source commit
above.

The Ash candidate includes the completed public-route, result-page, header,
restored agent setup prompt, Orange default, and release-pin work. Its full gate
passed after those changes.

## Limits on claims

- Public copy uses the calibrated 20–27 of 36 band, never a guaranteed score.
- Historical cost is an estimate from recorded tokens, never a promised bill.
- The provider exposes a model name, not an immutable model-build identifier.
- The proof establishes integrity and internal consistency, not honest
  execution or independent reproduction.
- Model calls go to Prime; “nothing leaves the laptop” is false.
- The release is a working technical preview of the
  Verifiers/Hermes/Techtree stack, not a benchmark, production evaluation
  suite, or validated uplift claim.

## Remaining authority boundary

No additional technical rehearsal is required before final approval.

No v0.1.1 push, tag, deploy, activation, or PyPI upload is authorized until the
founder supplies the exact final release approval phrase with this committed
packet's digest. The live proof publication above was separately and explicitly
approved; it is evidence, not implied authority for any further upload.
