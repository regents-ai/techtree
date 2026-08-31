# Issue tracker: beads (`bd`)

Issues for this repo live in **beads** — a local Dolt database at `.beads/`
in the repo root. There is no GitHub Issues workflow here; `gh issue` is not
used for tracking work.

The database is discovered by walking up from the current directory, so `bd`
only resolves from inside `techtree-python/`. From the workspace root
(`~/Documents/techtree-climb/`) it fails with `no beads database found` —
use `bd -C techtree-python <command>` or `cd` into the repo first.

Issue IDs are prefixed `techtree-python-` (e.g. `techtree-python-85a`).

## Conventions

- **Create an issue**: `bd create "<title>" -d "<description>" -p P1 -t task`
  Use `--body-file -` with a heredoc for multi-line descriptions, and
  `--acceptance "..."` for acceptance criteria.
- **Read an issue**: `bd show <id>` (add `--json` for structured output).
  Comments are separate: `bd comments <id>`.
- **List issues**: `bd list` (open by default), `bd list --label <label>`,
  `bd list --all` to include closed. `bd search "<text>"` for full text.
- **Find claimable work**: `bd ready` — open issues with no active blockers,
  excluding in-progress, blocked, and deferred.
- **Claim work**: `bd update <id> --claim` (atomic; sets assignee and
  `in_progress`).
- **Comment**: `bd comments add <id> "..."`. Use `bd note <id> "..."` to
  append to the issue's own notes field instead of the comment thread.
- **Apply / remove labels**: `bd label add <id> <label>` /
  `bd label remove <id> <label>`. Also available inline on update:
  `bd update <id> --add-label <label> --remove-label <label>`.
- **Close**: `bd close <id> --reason "..."`; `bd reopen <id>` to undo.
- **Link work**: `bd link <blocked-id> <blocker-id>` creates a blocks
  dependency (second argument blocks the first). `--type related` and
  `--type parent-child` are also available; `bd dep list <id>` shows both
  directions.
- **Hierarchy**: `bd create ... --parent <id>` for children of an epic;
  `bd children <id>` lists them.

## When a skill says "publish to the issue tracker"

Create a bead with `bd create`. Put the spec body in the description
(`--body-file -`) and design notes in `--design-file -` when the skill
distinguishes the two. Link it to its parent epic with `--parent` if one
exists.

## When a skill says "fetch the relevant ticket"

Run `bd show <id>` followed by `bd comments <id>`. The user will normally
pass the bead ID directly.

## Pull requests as a request surface

**No.** External PRs are not a request surface for this repo — beads is the
only inbound queue that triage reads.

## Wayfinding operations

Used by `/wayfinder`. Beads has first-class parent/child and dependency
edges, so the map is a bead and tickets are its children.

- **Map**: a bead labelled `wayfinder:map` holding the Notes /
  Decisions-so-far / Fog body.
  `bd create "<effort> map" --label wayfinder:map --body-file -`
- **Child ticket**: `bd create "<question>" --parent <map-id> --label
  wayfinder:research|wayfinder:prototype|wayfinder:grilling|wayfinder:task`.
  The ticket type is carried by that label; `bd children <map-id>` lists them.
- **Blocking**: `bd link <ticket-id> <blocker-id>` — real dependency edges,
  not a text line. `bd dep cycles` catches accidental loops.
- **Frontier**: `bd ready` already applies blocker-aware semantics; filter
  to the effort with `bd ready --label wayfinder:task` or by walking
  `bd children <map-id>`.
- **Claim**: `bd update <ticket-id> --claim` before any work.
- **Resolve**: `bd comments add <ticket-id> "<answer>"`, then
  `bd close <ticket-id> --reason "<gist>"`, then append a context pointer
  (gist + bead ID) to the map's Decisions-so-far via
  `bd note <map-id> "..."`.

## Git and sync

Do not run `git` or `bd dolt push` on the agent's own initiative. This repo
runs the conservative beads profile documented in `CLAUDE.md`: report
changed files and proposed commands at handoff and wait for approval.
