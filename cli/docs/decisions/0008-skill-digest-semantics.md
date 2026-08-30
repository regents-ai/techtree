# 0008 — Founder-Skill digest semantics (chief operational decision)

Status: binding unless Sean or the author overrules. Raised by WP10a.

Two different digest semantics apply to the three founder Skills, matching
how each is consumed:

1. **Starter subject Skill v1** — evaluated through the kernel, so it is
   pinned by its Techtree `SkillArtifact.root_digest` (the ordered
   content-tree digest the scanner computes). This is what the Campaign,
   drafts, and receipts already use.
2. **Operator Skills** (`techtree:rich-terminal-output`,
   `techtree:skill-improver`) — single SKILL.md files consumed by the
   plugin, never evaluated; pinned by the SHA-256 of the file's exact
   bytes (`sha256:<hex>` over the entrypoint bytes), which is what the
   plugin's loader verifies and what one-line `shasum` reproduces.

ReleaseCore and the bootstrap manifest carry all three under these
semantics; the release documentation states which digest kind each field
is. A future multi-file operator Skill would move to root-digest
semantics via an explicit decision, not silently.
