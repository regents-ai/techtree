# Relay coverage profiles

This directory will contain released, adapter-specific
`RelayCoverageProfile` documents after WP0 captures the upstream Relay
contract.

A profile defines the exact events Techtree expects from one admitted adapter,
the sources from which those expectations are derived, and the blind spots
that remain. Complete coverage is calculated; it is never manually asserted.
The only complete status is `complete_for_profile`.

Profiles pin both their schema version and `relay-coverage-v1` calculation
version. They distinguish Relay not being requested from Relay being requested
but unavailable.

Do not add private traces, credentials, environment dumps, or unsanitized
provider responses here.
