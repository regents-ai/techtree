# Handoff — finishing Climb v0.1

Updated 2026-08-28 after the final CLI/Hermes fixes and release re-pin. This
supersedes every older coordinate and scanner statement formerly in this file.

## Current candidate

| Repository/artifact | Coordinate |
|---|---|
| techtree-python | `2e714835469dc0a3fb4bece3ed2f861317fe4d7c` |
| CLI wheel | `sha256:5565e553f2e29a145711d5b13f6c03760a99b6c17d404e4a36768513a7660040` |
| techtree-plugin | `db827e714094c89514ea63d3ace1c97e6698589d` |
| techtree-ash release records | `a7d3797aea202f09efd3dcbbe9d94ab937796888` |
| ReleaseCore | `sha256:c92b602e8097a6498c49f52587a486f46f2cfd0a7adfe5cb082c5e98527e40a1` |
| Bootstrap | `sha256:3fdadeeb3f435fe08232e401c38751345b4809e9b1bb4202c892b43464c73c76` |
| Catalog | `sha256:10a7fcc5de1951c14509947c0512a4eeb247a703cdf01cc3f268580979a7d12c` |
| Network key | `sha256:84ea8ffad2b0fc59f9db9f14b7d97f25c060e71b644dec316ecd582ac040b966` |

Nothing has been pushed, made public, tagged, deployed, activated, or uploaded
to PyPI.

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
- The preserved wheel carries the frozen source stamp and digest. A fresh Python
  3.12 tool install matched all 169 package files byte for byte.
- The public run log implementation covers verified admission, signed receipts,
  idempotence, arrival order, verified projections, private optional addresses,
  append-only withdrawal, and no raw-bundle route.

## Verification already completed

- Python: 3,277 passed, 1 skipped; generated artifacts matched.
- Plugin: 922 passed; format, types, and Doctor passed.
- Ash: 6 doctests and 475 tests passed on the repinned shared tree; 24 focused
  candidate and receipt-route tests also passed.
- Cross-repository release gate: 26 of 26 passed.
- Catalog verification: five objects and one public Climb passed.
- Selected existing proof: 339 of 339 offline checks passed.

The separate visual task was idle when the final Ash gate passed. Its visual
files remain uncommitted and must not be overwritten or staged from this release
work. Rerun the gate only if that task changes the tree again.

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
so it has not left the machine. It excludes prompts, replies, episodes, traces,
and worker logs.

## The only remaining rehearsal

The server currently reachable on port 4010 has no network signing key and
correctly returns `network_key_unavailable`. It cannot produce an acceptable
receipt. Do not substitute an ephemeral key: the CLI will reject a receipt that
does not match the ReleaseCore's pinned public key.

The founder/operator must start the staged Ash server behind trusted local HTTPS
with `PHX_HOST=techtree.sh`, `TECHTREE_BOOTSTRAP_CHANNEL=stable`, and the real
`TECHTREE_NETWORK_SIGNING_KEY` in that operator shell. Point the CLI at that
trusted HTTPS address with `TECHTREE_PUBLICATION_ENDPOINT`; the pinned network
key remains non-overridable. The chief must never read or copy the private key.

After the endpoint is ready and the founder has explicitly approved the exact
payload above, run:

```sh
TECHTREE_PUBLICATION_ENDPOINT=https://<trusted-local-host>/api/v1/publications \
  uv run techtree publish run_0d3e7fc4d24a406b8ae9de74f4edca34 \
  --yes --reviewed-on host-agent
```

Then verify the returned receipt with the CLI, repeat the identical command to
confirm the same receipt and one log entry, and record the receipt digest,
entry identifier, and final Ash full-gate result in
`release/founder-release-approval-packet.md`. These are one rehearsal, not new
feature work.

## Protected release boundary

The founder has approved the shipping improver Skill bytes
`sha256:d5a381bed8ae5ddd5bbd6035775154dc47d2cb11b1da14f11d30ed47ff371678`.
That does not authorize release publication.

No push, public visibility change, tag, deploy, activation, PyPI upload, or
public release is authorized until the exact final phrase from
`docs/spec/closeout-helloworld/FOUNDER_APPROVAL_PHRASES.md` is received with the
committed approval packet's digest. Publishing the selected proof also requires
its own exact payload consent because the historical Gate-2 phrase explicitly
did not authorize uploading proof bundles.
