# Proof grades

Every result carries a grade describing how strongly it is evidenced. The
grade is about *control and evidence*, never about whether the number is
impressive.

## What a grade covers

- **Control** — were both sides identical apart from the one declared change?
  Same tasks, same model, same runtime, same configuration.
- **Evidence** — is there a proof bundle that someone can check offline: the
  receipts, the commitments, the signatures?
- **Attestation** — is it signed by a key that identifies who ran it?

## What no grade means

- It does not mean anyone else reproduced the result. A local proof is
  evidence of what happened on this machine, not a second opinion.
- It does not mean the Skill will help on tasks outside the set that ran.
- It does not mean the numbers are good. A well-evidenced result showing no
  improvement has exactly the same grade as one showing a large improvement.

## Warnings are not failures

A comparison can be fully controlled and still carry a warning — for example
when a model provider does not expose an immutable revision for the model
alias that was used. Report the warning in the words the result gives. Never
drop a warning to make a result sound cleaner, and never describe a warned
result as if it had no warning.

An actual mismatch is different: it makes a comparison invalid, not warned.

## Verifying

`techtree_proof_verify` re-checks a stored proof offline, from the bytes the
run wrote. It reports integrity, scientific, and attestation checks
separately, so a failure tells you which kind of trust broke. Nothing is
fetched and nothing is uploaded to do it.
