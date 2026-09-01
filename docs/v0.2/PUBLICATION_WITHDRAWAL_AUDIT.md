# Publication, bundle access, withdrawal, and privacy

WP0.7 (`techtree-31k.1.7`). This document settles which parts of the shipped
v0.1 publication protocol v0.2 inherits unchanged, which are the only additions
WP5 may make, and what WP0 implemented here rather than leaving to WP5.

It is an audit of code, not of intent. Every claim below names the file that
carries the behaviour, so a later reader can check the claim rather than
believe it.

## 1. The inherited write protocol, kept exactly

v0.2 extends the shipped publication protocol. It does not add a second one.

### 1.1 One write address, two documents

`POST /api/v1/publications` is the only address on the site that accepts a
body. A `techtree.publication-submission.v1alpha1` publishes a finished run and
a `techtree.publication-withdrawal.v1alpha1` withdraws one already published;
which arrived is read off a member each document's own signature covers, never
off the URL.

- `platform/lib/techtree_web/router.ex`
- `platform/lib/techtree_web/controllers/publication_controller.ex`
- `platform/lib/techtree/network/document.ex`
- `platform/lib/techtree_web/method_surface.ex` — every other method at every
  published address answers `405`, read off the routing table itself
- `platform/test/techtree_web/router_test.exs` — the routing table is pinned as
  a test, so a second write cannot appear quietly

v0.2 adds no second write address and no second document kind at this one.

### 1.2 The submitted bytes

The submission is a four-member document — `schema_version`, `run_id`,
`bundle_digest`, and `files` as a mapping of POSIX path to base64 — and a body
carrying a fifth member is refused. The exact request bytes are set aside as
they are read, before anything is decoded, and it is those bytes that every
digest and signature is checked against.

- `cli/src/techtree/publication/models.py` — `PublicationSubmission`
- `platform/lib/techtree_web/publication_body.ex` — the exact bytes are
  assigned at the parser, and the body is capped as it arrives
- `platform/lib/techtree/network/bundle.ex` — checks 2, 4 and 5

The volunteered contributor address travels in
`x-techtree-contributor-address`, beside the body and never inside it, because
the body is stored. That separation is the whole of the privacy argument and
v0.2 does not move it.

### 1.3 Verification depth

Seventeen checks run before a row exists, eight of them proof checks and the
rest admission checks, and the list of what this service deliberately does not
check is written down beside them rather than implied.

- `platform/lib/techtree/network/bundle.ex`

This is one proof system with two implementations of different depth — the
participant's offline verifier and the service's admission check — and the gap
between them is recorded. It is not a second proof system, and v0.2 adds
neither a second bundle format nor a second verifier.

### 1.4 Idempotence by proof digest

An entry is addressed by the bundle's own recomputed `payload_digest`. The same
digest with the same document returns the original entry and the original
stored receipt with `200`; a first acceptance is `201`; the same digest with a
different document is `409`; the same participant and run under a different
bundle is `409`. `log_sequence`, `id`, `accepted_at` and the receipt are all
chosen before the single insert, so a row cannot exist half written and a lost
response cannot produce a second receipt.

- `platform/lib/techtree/network/ingest.ex` — `conflict/1`, `run_conflict/1`
- `platform/lib/techtree/network/publication_entry.ex` — one create action,
  three identities, no destroy action

### 1.5 The server-signed receipt

The participant signs the run and the network countersigns that it accepted it.
The receipt is an envelope — payload, the digest of the payload's canonical
bytes, and a detached signature over that digest string — and the public half
of the network key is published at
`GET /api/v1/publication-keys/:key_id`, so a receipt is checkable by somebody
who trusts neither party. A build that cannot countersign refuses to accept
rather than recording something it cannot answer for.

- `platform/lib/techtree/network/receipt.ex`, `key.ex`
- `cli/src/techtree/publication/models.py` — `PublicationReceiptPayload`

### 1.6 Signed withdrawal and the append-only tombstone

A withdrawal is three members and no fourth, with no reason field, signed with
the same key that signed the run. The service looks that key up in the entry it
already accepted rather than believing one that arrived with the request. The
result is an appended `withdrawn` event and a date on the row saying the event
exists; nothing is deleted and no evidence is rewritten. Repeating a withdrawal
is replay-safe: the second one appends no second event.

- `platform/lib/techtree/network/withdrawal_request.ex`
- `platform/lib/techtree/network/publication_event.ex`
- `platform/lib/techtree/network/ingest.ex` — `withdraw/1`
- `platform/lib/techtree/network/publication_entry.ex` — `mark_withdrawn`, the
  only update action, accepting nothing but the date

### 1.7 Private raw Episodes and Traces

The proof directory has nowhere to put a transcript: an episode receipt carries
digests, task hashes, scores and a `trace_digest`, and the raw episodes stay on
the participant's machine. Check 16 refuses a submitted file carrying a raw
episode, a transcript, a prompt, a reply, a worker log, or a path on somebody's
own machine, and check 15 refuses a run whose own DataPolicy does not permit
publication.

- `platform/lib/techtree/network/bundle.ex` — checks 15 and 16
- `cli/docs/decisions/0038-public-run-log.md`

### 1.8 Billing labels are private by default

There is no billing or cost member anywhere in the publication submission, the
stored entry, the projection, or either receipt today, and v0.2 introduces
none by default. The v0.2 provider work keeps a billing-principal label private
unless a participant opts in explicitly in the publication intent
(`docs/v0.2/DECISION_LEDGER.md`), and the upstream lock records the Prime
billing principal as `not_exposed_as_safe_provider_record`
(`docs/v0.2/UPSTREAM_CONTRACT_LOCK.json`). Nothing in WP0 changes that, and a
public billing label remains a founder decision rather than a default.

## 2. What is confirmed absent

- **No `/api/v1/results` route.** `platform/test/techtree_web/router_test.exs`
  proves this twice, and it is worth being exact about how. Its route-list test
  asserts the whole published surface as a literal list, so an address absent
  from that list answers no method at all; `/api/v1/results` is absent. Its
  absent-route test then asserts that `/api/v1/results` is a `404` — for `GET`
  and `POST` specifically, not for every method. The list is the stronger of
  the two. v0.2 adds no such route.
- **No second proof system.** One bundle format, one signed manifest, one
  receipt envelope shape, one withdrawal document. The service's admission
  check is a documented subset of the participant's offline verifier, not a
  rival implementation.
- **No second publication protocol.** WP5 extends the shipped submission,
  receipt, withdrawal and projection rather than standing up a parallel one.

## 3. What WP5 adds, and nothing else

1. **The `techtree.published-result.v1` read projection** at
   `GET /api/v1/publications/:bundle_digest`. The route exists and answers
   today, but with `techtree.publication-entry.v1alpha1`
   (`platform/lib/techtree/network/projection.ex`). WP5 replaces that
   envelope — a hard cutover, not a second shape beside it — and adds the
   orthogonal evidence facets: artifact integrity, comparison validity,
   execution location, execution observation, trace coverage, model pin
   strength, Skill projection, and the reproduction list, each rendered
   separately, with uplift gated on valid comparison evidence.
2. **Facet persistence.** The facets have to be stored before they can be
   projected, and that is new columns on `PublicationEntry` and a migration.
   WP5 owns it.
3. **Rerun proofs.** A new proof and compatibility comparison per
   provider-hosted rerun, never a mutation of the source proof.
4. **Filters** by Climb, Skill, harness, model, location, trace coverage and
   rerun kind, with no "top" sort and no ordering but arrival.
5. **The public presentation** of all of the above, including whatever the
   detail page offers about the bundle address.

## 4. What WP0 implemented here

The decision rule for this ticket was: implement the bundle read route and its
withdrawal behaviour only if the platform already stores the exact submitted
bytes, so that it is a small addition with no schema, persistence or migration
change. It does, so it was implemented.

**The evidence.** `TechtreeWeb.PublicationBody.read_body/2` assigns the exact
request body for `POST /api/v1/publications`; the controller hands that binary
to `Ingest.accept/3`; `Bundle.verify/1` carries it through as `raw`; and
`Ingest.attributes/4` writes it to `PublicationEntry.submission_bytes`, a
`:binary` attribute written once in the single create action, touched by no
update action and by no destroy action. Serving it needed one route, one
controller action, and an attribute that was already selected on the existing
read. No new attribute, no snapshot change, no migration — `mix ash.codegen`
generates nothing after these changes, which is the check that says so.

**What was added.**

- `GET /api/v1/publications/:bundle_digest/bundle` returns the stored bytes,
  byte for byte, never parsed and written out again, with
  `Cache-Control: no-store`, `Content-Type: application/json`, and an entity
  tag that is the digest of those bytes.
- A withdrawn entry answers `410 Gone` there, while its metadata, its appended
  withdrawal event and its receipt stay exactly where they were. `410` rather
  than `404`: the run was published and countersigned, and saying it never
  arrived would be this site disagreeing with its own record and with every
  copy already in somebody's hands.
- Withdrawal cannot reach copies already downloaded, and those go on verifying
  offline. That is what a signature is for, and no copy is claimed back.

Changed: `platform/lib/techtree_web/router.ex`,
`platform/lib/techtree_web/controllers/publication_controller.ex`,
`platform/lib/techtree/network/publication_entry.ex`,
`platform/lib/techtree/network/projection.ex`,
`platform/lib/techtree/network/receipt.ex`,
`platform/lib/techtree_web/live/runs_live/show.ex`, `platform/README.md`, and
the pinned route list. Four of those — `publication_entry.ex`, `projection.ex`,
`receipt.ex` and `runs_live/show.ex` — changed in prose only: each said the
stored bytes are never served, which decision 0038 deferred to v0.2 rather than
forbade (§6.2), and leaving it in place would have made the code documentation
false. `README.md` gained the new address and the `410` status beside the other
refusals.

Guarded by `platform/test/techtree_web/controllers/publication_bundle_controller_test.exs`,
which posts a submission written out with indentation no encoder here produces
and asserts the answer comes back with that indentation intact — a re-encoding
fails it.

## 5. What WP0 deliberately did not implement

- **No facet persistence and no facet projection.** The metadata route still
  answers `techtree.publication-entry.v1alpha1`. Renaming the envelope to
  `techtree.published-result.v1` before the facets exist would ship a document
  wearing the WP5 name without the WP5 members, which is the compatibility trap
  this repository forbids. The rename lands with the facets, in WP5, as one
  cutover.
- **No browser controller and no page change.** `/results/:bundle_digest` is
  untouched, and no public page offers a bundle download. WP5 owns public
  presentation.
- **No change to `cli/`.** The CLI has no client for the read route, and its
  prose needs no edit: it described the stored bytes being served back, which
  is true as of this change. What is left is the contradiction inside decision
  0038 that produced the confusion, recorded in §6.2 rather than fixed.

## 6. Where the plan text and the shipped code disagree

### 6.1 The plan describes WP5's target in the present tense

`docs/plan/v0.2.md` §"Publication-service dependency" reads as a statement of
current fact: "The existing metadata route … returns a
`techtree.published-result.v1` envelope. Exact submitted publication bytes are
available at `GET /api/v1/publications/:bundle_digest/bundle`." Neither was
true when this audit started. The bundle route is now true; the envelope name
is not, and will not be until WP5.

`HANDOFF.md` states the same thing correctly, as an addition ("keeps … adds
`techtree.published-result.v1`"). The plan paragraph should be reworded to
match, so a reader cannot mistake a target for a shipped behaviour. Not fixed
here: `docs/plan/v0.2.md` is the binding contract, and rewording it is a scope
change rather than a WP0.7 deliverable. It belongs to a follow-up scope ticket.

### 6.2 Decision 0038 contradicts itself about serving the stored bytes

The contradiction is not between the CLI and the decision. It is inside the
decision.

0038's wire contract fixes the submission at four members "because the bytes
are stored and served back at a public address" (line 219). Its blocker 8 says
"The exact submission bytes are stored and never served" (line 344), and its
list of what is deliberately out of the release names bundle download among
them. Both sentences are binding text in the same document.

`cli/src/techtree/publication/models.py` follows the first half — the
contributor address travels in a header "because the run log serves a stored
submission back at a public address" — and so described a behaviour v0.1 did
not have. The platform followed the second. Neither implementation was wrong
about the decision; the decision was two-minded, and each side read the half in
front of it.

The privacy conclusion holds under either reading, which is why nothing unsafe
came of it: keeping the volunteered address out of the stored body is right
whether or not that body is ever served, and it is what made this route safe to
build at all. As of this change the CLI's prose is accurate and the platform's
has been corrected, so no code needs an edit. What remains is 0038's own
inconsistency, which an amendment should settle by striking blocker 8's
"never served" now that v0.2 serves them. Recorded here rather than amended:
`cli/docs/decisions/` is binding and amending it is a founder act.

### 6.3 "Withdrawal removes discovery" contradicts the shipped log

This is the one that needs a founder answer.

The shipped code keeps a withdrawn entry in the log listing, marked, on
purpose. `platform/lib/techtree/network/query.ex` states the rule: "A withdrawn
entry is still on the log … a log that quietly dropped the withdrawn entries
would be a log with holes in it that nothing explained." Decision 0038 says the
same: "The entry stays, marked withdrawn."

`docs/v0.2/DECISION_LEDGER.md` and `docs/v0.2/TICKETS.md` say WP5's withdrawal
"removes discovery" and "removes a Result from normal discovery while
preserving immutable stored evidence, metadata, receipt, and append-only
tombstone."

Those cannot both hold. Either "discovery" means the log listing, in which case
WP5 reverses a shipped v0.1 behaviour and 0038 needs an amendment; or it means
only the ranked, filtered and browsable surfaces WP5 adds, with the append-only
log itself unchanged. WP0 did not choose. See §7.

## 7. Founder decisions surfaced

1. **What "removes discovery" means for a withdrawn entry** (§6.3). Does WP5
   drop withdrawn entries from `GET /api/v1/publications` and `/results`, or
   does it leave the append-only log as it is and exclude them only from the
   new filtered surfaces? The first requires amending decision 0038.
2. **Whether the `techtree.published-result.v1` rename waits for the facets.**
   WP0 assumed yes and shipped no rename. If the name is wanted sooner, that is
   a founder call about shipping a versioned envelope that will gain members.
3. **Public billing labels.** Still private by default, still opt-in per
   publication intent, still unbuilt. Nothing in v0.2 should make one public
   without an explicit intent member the participant sets.

## 8. Follow-ups

- A follow-up scope ticket to reword `docs/plan/v0.2.md` §"Publication-service
  dependency" into the additive tense `HANDOFF.md` already uses (§6.1).
- WP5 to replace the metadata envelope and add facet persistence in one
  cutover, and to decide the public page's relationship to the bundle address.
- WP5 to carry the answer to §7.1 into `Techtree.Network.Query` and into
  decision 0038 if the answer is the first one.
- An amendment to decision 0038 settling its own contradiction (§6.2): its
  blocker 8 still says the submitted bytes are never served, which v0.2 has
  now made false, while its wire contract already said they are.
