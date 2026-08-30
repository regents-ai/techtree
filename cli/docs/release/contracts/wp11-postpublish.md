# Execution contract — WP11-postpublish: public-coordinate smoke + rollback check

Binding: decision 0023; closeout directive Phase 7. ACTIVATES ONLY
AFTER the founder's `APPROVE CLIMB V0.1 RELEASE`. Alters no approved
bytes.

## Purpose
After publication, prove the public path delivers exactly the approved
bytes, and prove rollback works.

## Verify
public wheel hash (downloaded from PyPI) equals the approved SHA-256 ·
public plugin commit (fetched from github.com/regents-ai/
techtree-hermes) equals the approved 40-char commit · served bootstrap
digest equals the approved BootstrapRelease digest · starter object
URL serves bytes matching the approved file digest · a fresh install
from PUBLIC coordinates completes · doctor passes on that install ·
the website is read-only (GET/HEAD only) · the rollback pointer
switch works and is then switched back.

## Explicitly not done
No rebuilds · no new paid scientific evaluation unless a public
artifact's bytes differ from the certified bytes (which is itself a
stop-and-report event) · no changes to any release object.

## Output
The final launch report: all public URLs, digests, install argv,
smoke results, and rollback commands.

## Stop conditions
Any public artifact whose bytes differ from the approved digest —
stop, do not "fix forward", report to the founder.
