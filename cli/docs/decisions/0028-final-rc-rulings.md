# 0028 — Final release-candidate rulings (author, founder-relayed)

Status: binding (author assessment relayed by the founder 2026-08-20;
adopted in full, with two timing facts disclosed below).

## Adopted rulings

1. **One final guided-revision attempt, absolute last.** The full
   value set frozen before the call; one generation request; the
   outcome — valid Skill v2, invalid proposal, generation limit,
   provider failure — is final. No further paid attempts, no model or
   prompt changes, no hidden retry.
2. **Guided revision ships as EXPERIMENTAL in v0.1 regardless of the
   final attempt's outcome.** Label: "Experimental guided revision".
   Copy: "Your Hermes model will make one proposal. It may fail to
   produce a usable revision, and the provider may still charge for
   the attempt. Techtree will not retry automatically." No published
   reliability rate; the packet records a diagnostic-attempt table
   (exact configuration, outcome, cost, failure classification) —
   never "N out of M odds" as a rate.
3. **Neutral, provider-agnostic failure copy.** The no-usable-proposal
   error reads: "The Host Hermes model reached the configured
   generation limit before returning a usable Skill proposal. The
   provider may have billed the request. This run's single
   guided-revision attempt has been used." Machine code:
   host_proposal_generation_exhausted. Local diagnostics may add
   reported token counts, stop reason, response digest, provider
   request ID. Private reasoning content is never displayed. (This
   supersedes the interim wording committed at plugin b4f6a5c5, which
   claimed the reasoning-vs-writing distinction the provider does not
   expose as a trustworthy field.)
4. **RC declaration sequence.** After the message/checksum fixes land:
   run all gates, declare ONE final RC commit, build and install the
   exact candidate wheel and plugin, and only then run acceptance.
   After the final attempt, ONLY the approval packet, release
   metadata, wheel-hash records, documentation, and the website
   release wrapper may change; any change to proposal composition,
   guards, approval, execution, receipts, or proof invalidates the
   attempt and requires recertification.
5. **The public site does NOT move to the stable channel before
   Gate 2** (amends decision 0027's pre-Gate-2 flip). techtree.sh
   keeps serving the honestly-placeholder preview
   (placeholder_release true, installation coordinates not yet
   published); the stable candidate ed7cb612… and floor da064357…
   stay STAGED, inactive. The founder onboarding journey runs against
   this preview. The stable pointer activates only after the exact
   Gate-2 approval phrase.
6. **The founder's twenty-minute journey uses packaged artifacts
   only**: the exact RC wheel, the exact plugin commit, isolated
   HOME/TECHTREE_HOME/HERMES_HOME/uv dirs, real prime login, real
   Docker, the preview bootstrap — never source worktrees. The
   scientific runs prove the evaluator; this journey proves
   distribution and onboarding.
7. **Orphaned-worker bound is a conditional blocker.** Documenting the
   hard-kill limitation is acceptable ONLY with evidence that
   orphaned child execution is independently bounded (child-side
   timeout or intrinsic episode/call/token ceilings, bounded
   worst-case spend, container exit without parent cleanup). The
   packet states maximum orphan duration and maximum theoretical
   spend. If the parent is the only enforcement, this is a v0.1
   blocker and gets fixed before release. Graceful stop
   (`techtree run cancel <run-id>`) is the documented path; manual
   cleanup is a crash fallback only.
8. **Gate-2 publication order for repository protection**: freeze
   privately → founder approval → repos public → immediately enable
   branch/ruleset protection → verify it → only then publish tags,
   wheel coordinates, and install instructions. The public install
   command is never advertised during the unprotected transition.
9. **Packet language discipline**: "Core Climb: release-certified.
   Guided revision: experimental." On success: "The final release
   candidate completed one live guided revision end to end" — never
   "guided revision is reliable." The no-upload claim stays narrow:
   "Techtree does not upload local Episodes, Traces, proofs, or Skill
   proposals. Model requests are sent to the selected providers."

## Timing facts disclosed

- The final attempt (authorized by the founder before this ruling
  arrived) launched on python 6c0b16a / plugin b4f6a5c5 — carrying
  the interim failure wording, not ruling 3's final wording. The
  attempt's host completion had already been made when this ruling
  landed; it was allowed to finish rather than wasting the paid,
  unrepeatable call. The wording refinement is a string-literal
  change landing immediately after; if the attempt succeeded, the
  error string was never rendered by it. Disclosed in the packet's
  change classification.
- The pre-Gate-2 stable-channel site flip had NOT been executed when
  ruling 5 arrived; it is cancelled outright. Nothing to unwind.
