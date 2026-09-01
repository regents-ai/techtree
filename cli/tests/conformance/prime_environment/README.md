# Techtree v0.2 Prime conformance environment

This is the exact deterministic environment proposed for Techtree's Prime
Hosted integration work. It exists to test infrastructure contracts, not agent
quality. Its four public tasks tell the subject the exact token to return, and
the only reward is a deterministic, case-sensitive exact match after trimming
outer whitespace.

The package exports a Verifiers v1 Taskset and an Env with one `subject` seat.
It contains no harness, tools, network client, secret, judge model, customer
data, or hidden answer. Local WP0 conformance uses Verifiers' model-free
`validate` command; publishing the package or running it against a model is a
separate protected action.
