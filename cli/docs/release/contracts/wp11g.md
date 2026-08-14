# Execution contract — WP11g (ndq.3.7): security, privacy, no-upload review

Binding: decisions 0014, 0015, 0023; spec wp9-wp11 §9.12–9.13, §15.8.
Blocked by: WP11e (reviews its captures).

## Purpose
Final release security review with an executable methodology — the ten
SEC tickets are done; this pass proves the assembled artifacts and the
live journeys uphold them.

## Supply chain
wheel SHA-256 · plugin full commit · lockfiles frozen · no unpinned
production dependency · no arbitrary package index · no install-time
script from model input · no auto-update · no shell=True (argv arrays
only) · ReleaseCore equality across repos.

## Local permissions (verify actual modes on disk)
~/.techtree 0700 · plugin state root 0700 · proposal temp root 0700 ·
private key 0600 · logs 0600 · temporary proposed SKILL.md 0600.

## Secrets — recursive scrubber adversarial cases
Bearer token · token in URL userinfo · token in query string · quoted
JSON API key · private key block · nested list/dict · package-manager
stdout/stderr.

## No-upload evidence — three complementary methods, all required
1. STATIC route/client audit: no receipt/proof/Trace upload method
   exists; the ash release surface is GET/HEAD only.
2. INSTRUMENTED application network log: record method, host, route
   for every Techtree-owned HTTP client during the journeys; assert no
   mutation request to techtree.sh.
3. E2E destination capture: expected destinations only (package
   origin, plugin origin, Docker registry, selected model providers,
   read-only techtree.sh); assert no unexpected Techtree artifact
   destination. TLS capture shows destinations without bodies — the
   method log supplies the method evidence.

## Verifiers push
push disabled in compiled config · disabled in resolved config ·
uploader module/path never invoked.

## Plugin Skill conflict scan — record the limitation
The deterministic scan may miss paraphrases. v0.1 does NOT add an
LLM-based semantic scanner. Instead require: exact founder Skill
digest pinning · manual security review checklist · negative tests for
known conflicting instructions · the hardcoded safety envelope stays
authoritative (the founder Skill cannot override one-turn / no-upload
/ no-auto-run). Record paraphrase detection as a limitation scoped to
future untrusted operator Skills.

## Outputs
release/security-review.json · security-review.md ·
network-method-log.json · destination-capture.json · a finding
disposition table. Every accepted limitation names: risk · why
accepted · scope · future ticket.

## Stop conditions
Any mutation request to techtree.sh · any upload path reachable · any
permission mode looser than specified · any scrubber case leaking.
