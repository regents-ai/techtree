# 0030 — Public site rebuild on the OpenResearch composition

Date: 2026-08-25. Founder directive, recorded verbatim in spirit; the
directive text lives with the founder's message and epic
techtree-python-8j2. Everywhere the directive says v0.2 it means v0.1.

## Ruling

The techtree-ash public surface is rebuilt on the OpenResearch
interaction reference (openresearch.sh screenshots supplied by the
founder): its product clarity and local operating model, with
Techtree's own colors and design — never its trade dress. The
distinction is binding copy-direction: OpenResearch helps agents
explore research directions; Techtree helps agents improve a declared
component and prove which change caused the result. Its graph is a
research graph; Techtree's graph is an evidence graph.

## Binding surface decisions

1. Hero: "Improve a Skill. Prove it worked." plus one 30–45-word
   paragraph (fixed in ticket 8j2.2), plus the quiet label
   "Local preview · v0.1 development release". No six-modes list and
   no internals jargon above the fold.
2. Header: Techtree · GitHub · Docs · View a proof. No sign-in, no
   account anywhere, no top-level Protocol nav (docs carry it).
3. One primary CTA (Install Techtree), one secondary (View a verified
   run); the CLI block renders from the active content-addressed
   release record; never a hard-coded version coordinate in a template.
4. Homepage has exactly four regions: hero+graph · Run/Improve/Prove ·
   one real campaign or verified comparison · trust boundary + footer
   ("A Regents Labs project").
5. The proof graph is real product data. Every node corresponds to a
   served artifact; no invented uplift figures; the score band, never
   an exact score. One reusable component across homepage, campaign
   pages and the verified-run page.
6. Visual system: one dark neutral surface, one Techtree accent,
   state colors reserved (green/amber/red/gray), sans + mono, 1px
   borders, CSS/SVG only, prefers-reduced-motion respected.

## Amendment to decision 0024

0024's agent-first hero placement is superseded: the public page
answers "what is this?" before "what kind of user are you?". One
canonical installation for everyone; "Use from Hermes" and "Use from
your terminal" move into the Quickstart. The agent-first JOURNEY is
unchanged — /skill.md, the release objects, agent-readable install
metadata and the 0024 next-step response rule all stand.

## v0.1 / v0.2 split

All frontend parts ship in v0.1 (tickets 8j2.1–8j2.8). Deferred to
v0.2 with tickets: public proof ingestion with downloadable bundles
and reproduction attestations (8j2.9 — v0.1 publishes nothing and the
site is GET/HEAD-only); docs version selector and the generated CLI
reference pipeline (8j2.10); the Fabric harness matrix and Codex path
(8j2.11); `techtree up` and the local daemon/dashboard layering
(8j2.12, folds into the cjj design brief).

## Unchanged constraints

The release freeze holds: priv/releases/**, priv/bootstrap/**,
priv/catalog/**, lib/techtree/catalog/**, the router's method surface
and docs/release/** are out of bounds for the UI work; the copy
guards, the 405 test, the candidate tests and the 25/25 cross-repo
verifier must stay green; the ash-regents skill is mandatory; workers
never run git. Starting point is branch wip/public-evidence-site
(a716c6b), whose visual reference and docs pages the founder approved.
