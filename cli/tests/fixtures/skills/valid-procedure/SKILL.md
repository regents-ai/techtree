# Branch code procedure

Use this procedure when a task asks you to read a short instruction and apply
it to a code branch.

## Steps

1. Read the whole task before writing anything.
2. Restate the requested change in one sentence.
3. Apply the change to the smallest surface that satisfies it.
4. State plainly what you changed and what you did not.

## Credentials

Never paste a credential into this skill. Refer to the environment variable
by name instead:

```bash
export TECHTREE_MODEL_API_KEY=${TECHTREE_MODEL_API_KEY}
```

The runtime reads the variable named below and nothing else.

```yaml
credential_env: TECHTREE_MODEL_API_KEY
```

## Notes

Further reference material lives in `reference/notes.md` and the worked
examples live in `data/examples.json`.
