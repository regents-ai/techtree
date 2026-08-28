# 0038 — The public run log

Status: **binding** (founder ruling, 2026-08-27). Three sub-questions
were answered on 2026-08-27, the design below was put to the founder,
and he directed that it be built — "do the receipt upload, and the UI
for it" — with the address schema in the additions section given in his
own words. It stopped being a draft when the build started.

## What the founder asked for

An append-only log of runs that participants publish, shown on the site
newest first, with a detail page per entry showing each task. The stated
purpose: make the site feel real and alive.

Three sub-questions were answered on 2026-08-27.

1. **Identity is only what is signed.** Nothing a submitter writes ever
   appears on the site. A future release may let somebody sign for an EVM
   address or an ENS name; that would be a new attestation kind, not a
   free-text field.
2. **It ships in v0.1.** A feed that arrives after launch is empty during
   the one week it most needs not to be.
3. **A published entry is withdrawn, never deleted.** Withdrawal is an
   appended event.

## Why this is smaller than it looks

The protocol was built for this and then stopped one step short.

- The proof directory is 364 KB and contains **no transcripts**. An
  episode receipt carries digests, task hashes, scores and a
  `trace_digest` — never a prompt or a reply. The raw episodes, all
  11 MB of them, are outside it.
- The DataPolicy the participant already accepts says
  `uplift_report: public`, `aggregate_scores: public`,
  `redacted_trace_projection: public`, and
  `candidate_skill.public_release: required_for_climb`. It says
  `raw_episodes.server_upload: prohibited`, which is exactly what the
  proof directory already excludes. Publishing the bundle is on the
  permitted side of a line this policy already drew.
- `revocation.immutable_published_proofs_remain: true` — the policy
  already contemplates published proofs that stay put. That is the
  founder's withdrawal ruling, written down before it was asked.
- The uplift report already carries `primary_result` (the feed row) and
  `task_deltas` (the detail page, 36 entries with both sides' rewards).
- `PublicationStatus` already exists with `not_requested`, `pending`,
  `published`, `blocked`, `failed`. Today every report is
  `not_requested`, because `_PUBLICATION_ELIGIBLE` is a hardcoded
  `False` whose comment says why: "Upload does not exist: no route, no
  credential, no server."
- The site can verify a submission with nothing added to it. Ed25519
  signing and verification work in this Elixir install through OTP's own
  `:crypto`; no dependency is needed. Confirmed by running it.

## What it is, stated so it cannot drift

**A log, not a leaderboard.** Ordered by arrival and never by score. No
rank, no position number, no "top", no sort control. The Climb's own
manifest says `leaderboard: {enabled: false}` and that does not change.

**Every field shown is derived from bytes that verify.** The identity is
the executor key's fingerprint. The agent is the harness and version the
Campaign pins. The model is the subject model. The scores come from the
signed report. No submitter-supplied string is stored or rendered, which
removes impersonation, spam and moderation as categories rather than
managing them.

**Participant-attested, still.** The site checks that a bundle is
internally consistent and signed by the key it names. It does not
reproduce the run and never will on this path. Every entry says so.

## The four promises this changes

Each is guarded by a test today. None may be quietly edited.

1. **The site accepts nothing.** `TechtreeWeb.MethodSurface` answers
   every mutating method with 405 and "this address publishes and does
   not accept anything", and `router_test.exs` pins the exact route
   list. This gains exactly one write address, named in the plug's own
   documentation.
2. **"Techtree does not upload your results."** On four pages. Becomes:
   nothing is uploaded unless you publish a run yourself, and then only
   the receipt, never the episodes.
3. **The plugin cannot open a network connection.** Left true:
   publishing is a CLI command only. The plugin may offer it as a next
   action for a person to run, and reaches no network itself.
4. **"No leaderboard, and no submission goes anywhere"** in the operator
   Skill. Rewritten to say what the log is and is not.

## What is deliberately not in this release

Raw episodes, transcripts, participant display names, accounts, sorting
by score, comparison between entries, reproduction attestations, and
bundle download. `/proofs/<digest>` download and reproduction
attestations remain techtree-python-8j2.9, for v0.2.

## Founder additions, 2026-08-27

Three, taken after the draft above.

### The offer at the end of a run

A finished, verified result offers publishing as one of its next actions,
the way every other step in this product is offered: Techtree emits it,
the host agent reads it, and a person answers. It carries
`requires_user_confirmation`, so the agent asks rather than acts.

The agent may then run the command on the person's behalf, through the
same surface `climb start` already uses — `--yes --reviewed-on
host-agent` records that the approval was given in the conversation. That
path is built and trodden and there is no reason to invent a second one.

The plugin's own guarantee is unchanged and must stay exactly as precise
as it is: no plugin module can open a network connection. The CLI it
invokes can, and only after a person has said yes. Copy that blurs those
two is a copy defect.

### The packet the server returns

A **publication receipt**, signed by the network. It carries the log
sequence, the bundle digest, when it was accepted, which checks ran and
which passed, and the address the entry now lives at.

The participant signed their run; the network countersigns that it
accepted it. That symmetry is worth having on its own, and it is what a
future reward could be required to present. It means the site holds a
key of its own and publishes the public half at a stable address, so a
receipt can be checked by anyone, including by somebody who does not
trust us.

The CLI writes the receipt into the run directory as a new file. A
completed run's existing files are never modified; this is an addition,
which is what append-only permits.

### A voluntarily shared EVM address

Asked for once, at publish time, optional, defaulting to no.

**It is never public.** It is not on the feed, not on the detail page,
not in any endpoint's response, and not in the submitted bundle. It is
stored apart from the submission, keyed by the executor key, and the
public log is unchanged by whether one was given.

**It is recorded as unverified, because it is.** A string somebody typed
is not proof of control of an account. The stored field says so in its
name. When signing for an EVM address or an ENS name arrives, that is a
different and verified kind alongside this one, not a repair of it.

**Nothing may be promised for it.** The internal intention is to be able
to reward participants later. That intention is not a commitment, and
copy which implies somebody will receive something of value in return
for an address is a promise this project cannot keep and should not
make. The wording says what is true: an address can be left, it is kept
for the possibility of recognising contributors later, and nothing is
being offered in exchange today. This is a hard boundary and belongs in
the copy guards with the others.

A person can ask for the address to be removed, and removal means
removal — it is not part of the append-only evidence, it is a detail
somebody volunteered about themselves.

## The wire contract, fixed here so the two halves cannot drift

Both sides of this feature were built at once, from opposite ends, and
they disagreed on four things: where a volunteered address travels, the
schema version, the shape of the file set, and the shape of the receipt.
Each disagreement would have made publishing fail outright. The contract
is therefore written down once, here, and both implementations conform
to it rather than to each other's reading.

### The request

`POST` to the configured run-log address, over `https` only, with no
query string and no fragment: a submission travels in a request body and
never in a URL.

```json
{
  "schema_version": "techtree.publication-submission.v1alpha1",
  "run_id": "run_<32 hex>",
  "bundle_digest": "sha256:<64 hex>",
  "files": { "<posix path inside the proof directory>": "<base64 of the file's bytes>" }
}
```

`files` is a mapping and nothing else. It carries no per-file digest and
no per-file size, deliberately: those would be claims the submitter
wrote, and the receiving side must take every digest from the bundle's
own signed manifest instead. The document has exactly these four
members; a body carrying anything more is refused, because the bytes are
stored and served back at a public address.

The volunteered address travels in the `x-techtree-contributor-address`
header, for that same reason, and is never echoed.

### The response

**Amended 2026-08-27, after the flat shape below proved unbuildable.**
The founder's ruling requires the client to check that "the payload
digest matches the payload bytes", and a flat receipt has no payload
digest and no structural way for two implementations to agree on which
members a signature covers — which is the exact drift this contract
exists to prevent. So the receipt is an envelope, the shape every other
signed document in this protocol already uses.

```json
{
  "payload": {
    "schema_version": "techtree.publication-receipt.v1alpha1",
    "id": "<the log's own identifier for this entry>",
    "run_id": "run_<32 hex>",
    "log_sequence": 7,
    "bundle_digest": "sha256:<64 hex>",
    "accepted_at": "<RFC 3339, UTC, Z-suffixed>",
    "checks": [ { "id": "...", "passed": true, "detail": "..." } ],
    "entry_url": "https://techtree.sh/runs/sha256:<64 hex>",
    "public_key": { "algorithm": "ed25519", "key_id": "sha256:…", "public_key": "<base64>" }
  },
  "payload_digest": "sha256:<sha256 of the canonical bytes of payload alone>",
  "signature": { "algorithm": "ed25519", "key_id": "sha256:…", "signature": "<base64>" }
}
```

The signature is over the ASCII digest string, not over the document.
It is the countersignature the founder asked for: the participant signed
the run, and the network signs that it accepted it. The public half is
pinned in ReleaseCore, so a receipt is checked against the key the
*release* names rather than against one the answer supplied — a server
that invented a key and signed with it proves nothing.

### Withdrawal

By `POST` to the same address. This site gains exactly one write
address, so the two documents are told apart by their schema version
rather than by a second route.

```json
{
  "payload": {
    "schema_version": "techtree.publication-withdrawal.v1alpha1",
    "bundle_digest": "sha256:<64 hex>",
    "requested_at": "<RFC 3339, UTC, Z-suffixed>"
  },
  "payload_digest": "sha256:<canonical digest of payload>",
  "signature": { "algorithm": "ed25519", "key_id": "sha256:…", "signature": "<base64>" }
}
```

Three members and no fourth. No reason field, ever — nothing a submitter
writes reaches the site. No public key either: the receiving side looks
the participant's key up in the publication it already accepted and
checks the signature's key id against it, and that lookup is the whole
of the authorisation.

The answer is an envelope carrying
`techtree.publication-withdrawal-receipt.v1alpha1`, the bundle digest,
when it was withdrawn, the entry URL and the network's public key.

Every shape here is exported as a JSON Schema under
`schemas/v1alpha1/`, so an implementation is built against a generated
file rather than against this prose.

`checks` is the list the receiving side actually ran, not a constant. A
receipt naming no check is refused by the participant's own CLI.

## Founder ruling, 2026-08-27 — the log ships inside v0.1

The public run log is v0.1 scope: a working `techtree publish`, an ingest
address, a newest-first log and a detail page. That requires a new wheel
freeze, a new plugin and release-coordinate pin, a regenerated
BootstrapRelease and a replacement Gate-2 packet.

**It does not require more paid evaluation.** No Campaign, engine,
taskset, subject execution, scorer, receipt generation or comparison
logic changes, so nothing scientific moved and nothing is re-run for
money. Every canonical proof is re-verified offline and the publication
journey is walked, but a post-run command is not a reason to pay for
model inference again.

### The command

`techtree publish <run-id>`. Not `techtree proof publish`. Nothing has
been released, so this is a hard cut with no alias: `proof` keeps
`verify` and nothing else.

### Ten blockers, closed before the re-freeze

1. The command name, above.
2. Every stale comment saying the contributor address travels in the
   body. It travels in `x-techtree-contributor-address` and the entire
   privacy argument rests on that separation, so prose that contradicts
   it is not a typo. The CLI's table says **Log sequence**, never
   "Position": a sequence is not a rank and may have gaps.
3. Redirects. The transport's docstring says none are followed and
   `urlopen` follows them by default, so a redirect could forward both
   the proof and the private address header to another origin. Refuse
   them, require `application/json`, and read the size cap **plus one**
   byte — reading exactly the cap does not prove the response ended.
4. The endpoint and the network's Ed25519 **public** key are pinned in
   ReleaseCore. A receipt is verified against that pinned key before the
   CLI writes it: payload digest matches the payload, key id is the
   pinned one, signature verifies, run and bundle match what was sent,
   the entry URL is https on the pinned origin, and every reported check
   passed. An unverified receipt is never written down.
5. A stable release publishes without any environment variable. The
   override stays for development, and the review prints the endpoint
   actually resolved.
6. Idempotence by bundle digest, on both sides. A lost response and a
   retry return the original entry and the original receipt: same
   digest and same bytes is `200`, first acceptance `201`, same digest
   with different bytes `409`, same participant and run with a different
   bundle `409`. The CLI's receipt write converges the same way.
7. The wire is the four-member submission already fixed above, and the
   server treats `run_id` and `bundle_digest` as assertions to check
   against the signed bundle rather than as inputs to trust.
8. The exact submission bytes are stored and never served. A public
   address returning the file mapping is a bundle download however it is
   wrapped, and 0038 defers that. `entry_url` is the verified detail
   page.
9. Only Campaign digests the active release admits are accepted. This is
   the anti-spam boundary and it is deliberate: v0.1 is not a generic
   proof-hosting service.
10. Withdrawal is implemented rather than promised: `techtree withdraw`
    signs a canonical request with the same participant key that signed
    the run, the server verifies it against the accepted entry and
    appends a `withdrawn` event. The entry stays, marked withdrawn. A
    public promise with no executable path would be worse than neither.

### Four questions the chief put to the founder, and the answers

**Server-side verification depth: the eight checks that exist**, plus
the new content scan and DataPolicy check — not a second full
implementation of the offline verifier. The eight are the substance:
file digests against the signed manifest, envelope digests, signatures,
key identity, admitted Campaign, recomputed counts, committed membership
in order. What they omit is linkage and proof-grade bookkeeping that the
participant's own offline check already covers. Two independent
implementations of all 339 that disagree by one check would reject
honest submissions, and the canonical encoder alone needed a hundred-file
cross-check to get right. The decision records which checks the server
does not run, so the gap is stated rather than implied.

**The network key id is the sha256 of the public key**, as every other
key id in this protocol is. A receipt naming a key it does not carry is
then caught for free. Rotation is a new key and therefore a new id, and
ReleaseCore pins which one this release trusts.

**A run is addressed by its bundle digest**, `/runs/sha256:…`, so the URL
is derivable from the proof itself and two people publishing the same
bundle land on the same page. A row identifier would exist only inside
our database; a sequence number in the URL would read as a rank.

**The staged publication runs against a throwaway local instance** of the
deployed build, over https, with the packaged wheel. Nothing is deployed
and no public surface is touched before Gate 2. The Fly deployment is
proven by the post-publish smoke check that is already a ticket.

### One thing stated honestly rather than promised

Removal of a volunteered address means removal from the active system
and from any future use. It is **not** a claim of erasure from database
backups, which this release does not implement and will not imply. Per-row
encryption with the key destroyed on removal would make the stronger
claim true; until that exists the copy says the weaker one.

### Two questions kept separate

*Offline proof verification* asks whether a signed report overclaims
relative to its own grade and rights. It never demands agreement with a
later build's publication rules — that is the regression already fixed,
and it would have invalidated every certification proof this release
rests on.

*Server admission* applies the current policy independently, to
immutable proof facts. Old proofs stay valid; the publication service
still gets to decide what it admits today.
