# Handoff — Climb v0.1.1 released

Updated 2026-08-29 after the final CLI/Hermes fixes, public-route change,
v0.1.1 release re-pin, and public release. This supersedes every older
coordinate and scanner statement formerly in this file.

## Released coordinates

| Repository/artifact | Coordinate |
|---|---|
| techtree-python wheel source | `614daffbcbd294be4646adfdec26f95337c4f7ed` |
| CLI wheel | `techtree-0.1.1-py3-none-any.whl`, `sha256:51f720e0636d406d432a415b69001261744d4f70149307a0493a4f2019e4b5ce` |
| techtree-plugin | `ca22ee782f5572b179c665c2c2a33120171f0158` |
| techtree-ash | `d617b3d6cea0dc2c1873502792ddebfd062c49f6` |
| ReleaseCore | `sha256:07bfd0f0f07c4df08e879c2ff6dbb8e17c6363445e15be62c6ec9549989d67fa` |
| Bootstrap | `sha256:5def3b256aafab0a31b37d23f0eddb1cb033b90da251f3b3932fed62928c1e3f` |
| Catalog | `sha256:10a7fcc5de1951c14509947c0512a4eeb247a703cdf01cc3f268580979a7d12c` |
| Network key | `sha256:84ea8ffad2b0fc59f9db9f14b7d97f25c060e71b644dec316ecd582ac040b966` |

The v0.1.1 commits above are public. Tag `v0.1.1` points to the frozen wheel
source, PyPI serves the wheel at the digest above, and the stable site bootstrap
publishes the v0.1.1 CLI and Hermes coordinates.

## Public release verification

- Trusted-publishing workflow run `33269935072` rebuilt the tagged wheel,
  matched its approved digest, and published it to PyPI.
- A clean Python 3.12 container installed `techtree==0.1.1` without a package
  cache. `techtree --version` returned `0.1.1`, and offline release verification
  passed.
- An isolated Hermes home installed the public plugin commit. Plugin Doctor
  passed runtime discovery, manifest parsing, import, and registration for 17
  tools and 2 hooks.
- Fly release v41 (`QgDeJ3o11V2D7fmzmRnkpyx43`) deployed image
  `registry.fly.io/techtree-sh:deployment-01M17EVQ91HDADX2XCA7XN19F8`.
- The live bootstrap body and ETag both match
  `sha256:5def3b256aafab0a31b37d23f0eddb1cb033b90da251f3b3932fed62928c1e3f`.
  It names CLI 0.1.1 and Hermes commit
  `ca22ee782f5572b179c665c2c2a33120171f0158`.
- The stable pointer was moved back to the prior v0.1.0 bootstrap, verified by
  body digest and ETag, then moved forward and re-verified on v0.1.1.
- `/`, `/start`, `/results`, `/proofs`, `/docs`, the introductory Climb, and
  both published Result details returned 200. `/runs` returned 404, and the
  public pages had no browser errors or horizontal overflow at representative
  desktop and mobile widths.

The first post-approval image still carried the previously generated v0.1.0
bootstrap in `priv/catalog`; importing it therefore left v0.1.0 active. The
public contract did not change during that attempt. The catalog was regenerated
from the frozen CLI source with the approved v0.1.1 bootstrap, verified, and
deployed as Fly v41 before activation.

## What is finished

- The CLI no longer loops after engine verification. The fresh journey reaches
  the starter Skill and carries the draft digest through approval and publish.
- Existing valid proofs remain publishable; eligibility is derived from stored
  proof bytes rather than a stale flag.
- Hermes always names the next safe action. On a fresh Hermes 0.20.5 profile,
  the plain pinned community install is refused with CAUTION, five findings in
  three families, and no prompt. The guide then offers a separate reviewed
  `--force` command. Scanning stays enabled. The exact plugin installed and
  Doctor registered 17 tools and 2 hooks.
- Ash rejects a malformed publication digest as a 400 and keeps a valid unknown
  digest as a 404. The candidate bootstrap and checksums name the final Python,
  wheel, plugin, ReleaseCore, catalog, and founder-approved Skill bytes.
- Public result pages live only at `/results`; `/runs` is not retained as an
  alias. The publication submission endpoint remains `/api/v1/publications`.
- The preserved wheel carries the frozen source stamp and digest. A fresh Python
  3.12 tool install matched all 169 package files byte for byte.
- The public run log implementation covers verified admission, signed receipts,
  idempotence, arrival order, verified projections, private optional addresses,
  append-only withdrawal, and no raw-bundle route.

## Verification already completed

- Python: 3,289 passed, 1 skipped, and 298 deselected; generated artifacts
  matched.
- Plugin: 927 passed; format, types, and Doctor passed.
- Ash: 6 doctests and 417 tests passed at the committed candidate; 45 focused
  release tests also passed.
- Cross-repository release gate: 26 of 26 passed.
- Catalog verification: five objects and one public Climb passed.
- Selected existing proof: 339 of 339 offline checks passed.

The Ash commit includes the completed public-route, result-page, header,
restored agent setup prompt, Orange default, and release-pin work. The final
coordinate correction replaces a nonexistent plugin SHA with the exact frozen
plugin commit named above; no plugin or wheel byte changed. Its final full gate
passed after those changes.

## Existing proof selected for the final receipt

The founder directed this finish to use an existing verified proof because no
scientific artifact changed. Do not start a paid run.

| Field | Value |
|---|---|
| Run | `run_0d3e7fc4d24a406b8ae9de74f4edca34` |
| Files | 84 |
| Bytes | 238,376 |
| Proof digest | `sha256:a96bc70b67505832f2836694f0887b49991f7eda7fd7f6b87865d4ce24762c57` |
| Contributor address | none |
| Endpoint | `https://techtree.sh/api/v1/publications` |

The CLI displayed this payload and was interrupted at its final confirmation,
so this particular proof remains local. It excludes prompts, replies, episodes,
traces, and worker logs. Do not start another paid run: the separate live Hermes
run below completed the end-to-end publication path.

## Publication rehearsal is complete

The full Hermes journey later produced and published
`run_86bb7176135d49e3a0577630e952c7f3`. Ash accepted 84 proof files totaling
238,376 bytes, verified all 17 admission checks, and returned a signed receipt:

| Field | Value |
|---|---|
| Proof digest | `sha256:e8ef7cb4f906a3ca75310415dbeed2302d8e9d195ce7ed044d83ba7f4480ac91` |
| Receipt payload digest | `sha256:0cc5a2c89d295fad5596845c4c35ba67ca96f86f2b0eb1fdaf23ead46a4b150a` |
| Entry identifier | `72e151ba-205b-4385-9844-750222d7a105` |
| Log sequence | 1 |
| Network key | `sha256:84ea8ffad2b0fc59f9db9f14b7d97f25c060e71b644dec316ecd582ac040b966` |
| Contributor address | none |
| GitHub URL | none |

That signed v0.1.0 receipt records the viewing route in force when it was issued.
The v0.1.1 ReleaseCore and Ash candidate deliberately move public viewing to
`https://techtree.sh/results/<proof-digest>` without retaining `/runs` as an
alias. The submission endpoint is unchanged. No further signer rehearsal or
proof upload is required for the v0.1.1 release.

## Protected release boundary — completed

The founder approved the shipping improver Skill bytes
`sha256:d5a381bed8ae5ddd5bbd6035775154dc47d2cb11b1da14f11d30ed47ff371678`
and explicitly authorized the corrected v0.1.1 release on 2026-08-29. The
release actions and public verification are recorded above.
