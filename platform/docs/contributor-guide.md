# Contributing to the Techtree website

This repository serves the public face of Techtree Climb and also carries a
staged release candidate whose bytes are bound by an approval process. That
gives it a small number of hard boundaries and a set of copy rules that are
enforced by tests. Read this before changing anything.

## Paths that are bound to a release

```
priv/releases/**            a staged release candidate and its checksums
priv/bootstrap/**           the served release documents and the rollback floor
priv/catalog/**             generated; synced from the techtree CLI repository
lib/techtree/catalog/**     the release/catalog kernel
docs/release/**             the release runbooks, re-pinned on every release change
```

Changing bytes under these paths invalidates a release approval. If a change
seems to need one of them, it almost certainly belongs somewhere else — or it
is a release action, not a website change.

The site has **one write address, fixed by decision 0038**: `POST
/api/v1/publications`, which takes a signed publication or a signed withdrawal
and nothing else. Every other published route answers GET and HEAD only, and a
test asserts a 405 with an `Allow` header for anything else. Do not add a
second write, a form, a file upload, or any path a reader could post to from a
page. If a design seems to need one, it is the wrong design for this product.

## The copy guards are rulings, not lint

`test/techtree_web/release_copy_test.exs` and the page tests encode wording
decisions that were made deliberately. They will fail a change for saying
things that seem harmless. Each rule guards a real way readers have been — or
could be — misled:

- **Never quote a price.** Cost is whatever the reader's model provider
  charges. A figure on a page is a promise the product cannot keep.
- **Never say "nothing leaves your machine" unqualified.** Model calls do go
  to the provider. Say both halves in the same breath.
- **State the publication terms with their plain meaning.** A Climb's terms
  describe a *published* result, and starting a run publishes nothing: nothing
  is published unless the participant publishes a finished run themselves, and
  what travels then is that run's proof — the signed report and its receipts —
  and never the episodes. The shared `publication_note()` row must accompany
  the terms wherever they appear, and must say both halves.
- **Never promise a run is time-bounded**, and never state an exact score
  where the calibrated band belongs — the one exception is the published
  example result, whose every number is computed from the signed report the
  site ships.
- **Any GitHub address a reader could install from must be one immutable
  commit**, never a branch.
- **Never describe a phone or handheld journey.** It does not exist.
- **Never tell anyone to turn off install-time security scanning**, and where
  the scan is described, describe its actual expected result.
- **No machinery vocabulary on reader pages.** Document type names and
  implementation words stay on the protocol page, where naming them is the
  point.

If a guard blocks a change you believe in, open the discussion — do not weaken
the guard.

## Checks

```
mix check
```

must be fully green before any change is proposed: formatting,
`compile --warnings-as-errors`, and the full test suite including the copy
guards, the 405 method surface, and the release-candidate tests. Database
connection settings (`PGUSER`, `PGPASSWORD`, `PGHOST`) can be supplied as
environment variables; see the README.

## What the site is for

One sentence, and every design decision should serve it: a reader lands on one
page, hands one prompt to their agent, and ends up with a measured,
locally-verifiable comparison — with no account anywhere, and nothing sent
unless they decide to publish it.
