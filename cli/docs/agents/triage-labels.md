# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps
those roles to the actual label strings used in this repo's issue tracker
(beads — see `issue-tracker.md`).

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use
the corresponding label string from this table.

Labels are free-form in beads — there is no create-label step. Apply and
remove them with:

```bash
bd label add <id> ready-for-agent
bd label remove <id> needs-triage
bd list --label needs-triage          # the triage queue
bd label list-all                     # every label in use
```

`wontfix` is a label, not a status. Pair it with a close:
`bd label add <id> wontfix && bd close <id> --reason "..."`.

Edit the right-hand column to match whatever vocabulary you actually use.
