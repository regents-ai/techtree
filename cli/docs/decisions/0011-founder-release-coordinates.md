# 0011 — Founder-decided release coordinates and license

Status: binding (founder decisions, 2026-08-13).

1. **License: MIT everywhere.** Both founder Skill files keep
   `license: MIT` in frontmatter (as drafted), and all three
   repositories (techtree-python, techtree-plugin/techtree-hermes,
   techtree-ash) adopt MIT. The repository `LICENSE` placeholder is
   replaced with the MIT text naming the founder as copyright holder.
   This unblocks Skill hashing: no frontmatter license edit is needed
   beyond what 0010 already directs.

2. **CLI wheel origin: PyPI, distribution name `techtree`.** Install
   coordinate `uv tool install techtree==0.1.0` with the wheel SHA-256
   pinned in BootstrapRelease. Chief verified 2026-08-13 that
   `techtree` is unclaimed on PyPI (`/simple/techtree/` → 404).
   Claiming the name and publishing happen only at the founder's final
   release approval (Phase 7).

3. **Plugin repository: `github.com/regents-ai/techtree-hermes`.**
   The bootstrap pins `hermes plugins install
   https://github.com/regents-ai/techtree-hermes --ref <40-char
   commit> --enable`. Chief verified the `regents-ai` org exists. The
   repo is created/pushed only at the founder's final release approval
   — nothing is pushed to GitHub before then.

Open coordinates still placeholder: troubleshooting documentation URL,
provider profile string, host Hermes tested range, image digests in
BootstrapRelease (produced by the release build itself).
