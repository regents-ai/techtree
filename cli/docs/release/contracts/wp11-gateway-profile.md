# Execution contract — WP11-gateway-profile: pin the reference gateway

Binding: decision 0023; spec wp9-wp11 §4.4. A one-page FOUNDER
decision, not a coding project. Blocks WP11f.

## Purpose
Spec §4.4 deliberately leaves REFERENCE_GATEWAY as a release-test
choice. WP11f cannot claim a certified gateway journey without naming
one. This ticket records the founder's selection.

## The decision records
gateway name · gateway version or commit · Host Hermes version ·
approval mechanism (how the human approves on that surface) ·
message-size limits · tool-call capabilities · session-reconnect
behavior · supported phone client.

## Output
release/acceptance/gateway-profile.json + a decision-doc entry or
note. Other gateways remain "should work, not certified" (spec §4.4).

## Founder decisions required
The selection itself. The founder should name the gateway they
actually use to reach Hermes from a phone; the chief prepares the
profile fields once named.
