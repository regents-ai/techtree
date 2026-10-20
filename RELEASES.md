# Techtree releases

The release record: each Fly release of techtree.sh (app `techtree-sh`), the
commit it was built from, and the commits behind its changelog entries. It is
kept here, off the site, so the public changelog (`platform/priv/changelog.md`,
also `CHANGELOG.md`) only says what changed for people and agents.

| Release | Live on | Built from | Changes | Rollback |
| --- | --- | --- | --- | --- |
| v162 | 17 Oct 2026 | 7d7fce8 | Rotating home headline (7d7fce8) | v161 119a0a4 |
| v163 | 18 Oct 2026 | 6b56b51 | Reduced-motion headline and 375 px header (9971f6c); Start and Wallet Bench empty states, footer and 404 tap targets (8eef75e); motion lab loads on its own page (6b56b51) | v162 7d7fce8 |
| v164 | 18 Oct 2026 | 4837f16 | Public pages stay up in a database outage (8aeb179); changelog names commits (4837f16) | v163 6b56b51 |
| v165 | 18 Oct 2026 | 4fb4e44 | Outage pages answer in about half the time (8030b33) | v164 4837f16 |
| v166 | 18 Oct 2026 | b9cd7a0 | Signed-in visitors in an outage (1e81987, 9c618d2); wallet code on the account pages only (73bbbae) | v165 4fb4e44 |
| v167 | 19 Oct 2026 | 66aa685 | Outage note after a database restart (55d9380); changelog entry (185b387); release record off the site (80973c6 and this commit) | v166 b9cd7a0 |
| v168 | 19 Oct 2026 | 1ee12e2 | Header star count served from the site, one read at a time, kept through a failed read (50ca447, 0cedd09, 1b100e1); health check survives a database blip but not a real outage, and fails on a cold start (50ca447, 1b100e1, ab143fc); Wallet Bench links fit a finger (c46965b); Buy Credits and standalone links fit a finger (7a641bf, 8c681c5); outage notes announced (504ba7b); tests and browser checks stay offline (ca16642, 8c681c5, 1ee12e2) | v167 66aa685 |
| v169 | 19 Oct 2026 | ea93a6a | Canopy palette and icons (c18502bc, 787dc5e4, 3434df49); slimmer buttons and design-system 4472b6fc (d5f155f1, 87189a16, 7624d55c); lime Sign in and Copy page edges at rest (46eba218, d76c9671); changelog (02c6d1d9); docs mockups from main (4909c9f2) | v168 1ee12e2 |
| v170 | 19 Oct 2026 | ea93a6a | Fly secret change only (WALLETBENCH_FUNDER_KEY set to Techtree's own funder, Sean); same image as v169 | v169 ea93a6a |
| v171 | 19 Oct 2026 | 6837806 | Wallet Bench score grid, result window and full-results download; /wallet-bench.json feed; each deploy keeps the previous release's files (merge of keep-assets 721c241 and awb-feed be5231d7, review fixes 6837806) | v170 ea93a6a |
| v172 | 19 Oct 2026 | 7bb78ae | /wallet-bench.json reads the bench's tables in the site's own schema (3fe5bb9, 7bb78ae); it answered 500 on v171 | v171 6837806 |
| v173 | 20 Oct 2026 | 9314b24 | A Wallet Bench pass that leaves a plain key or password file scores at most 9.0 (7b9abc1); evidence files share the zip's four download places (02af9af, 2d57c87); new tests record no agent pictures and recorded files open as text (ffd8bef); make release builds over the live image again (16c2c16); review fixes 9314b24 | v172 7bb78ae |
