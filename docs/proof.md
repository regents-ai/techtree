# Proof

A Climb's result bundle contains **participant-attested evidence**. Verify a bundle
someone has shared with you:

```sh
regents techtree proof verify path/to/result-bundle
```

Verification checks the supplied files, signatures, configuration, task membership
and recorded aggregation without rerunning a model. A signature identifies the key
attesting to the result. It does not establish an honest machine or an independent
reproduction.

Keep three questions separate: did the bytes verify, was the comparison valid, and
did performance improve? A commitment to unavailable private evidence does not let a
reader recompute that evidence. A good score on these tasks does not guarantee
improvement elsewhere.

The comparisons Techtree runs itself, like the one on the
[front page](../README.md#results), are not signed. Each one's page names its report
and traces by SHA-256 digest, and [Proof on techtree.sh](https://techtree.sh/docs/verify)
explains how to check both.

## Comparison

A **Skill** is reusable agent instruction. A **harness** controls context, tools,
memory and execution. An **environment** defines tasks and available actions; its
**verifier** scores the outcome.

A **Campaign** freezes the comparison configuration. A **Climb** is the invitation to
participate under its rules. A Skill comparison holds the model coordinate, harness,
task membership, scorer, tools, sampling and limits fixed while changing the declared
Skill. Equal limits do not require equal actual spend; both arms should report their
observed usage.

Identical Skill bytes do not guarantee identical exposure in different harnesses.
Compare each harness with and without the Skill before attributing a cross-harness
difference to the Skill. A mutable model alias is also weaker evidence than an
immutable model build.

## Privacy

Publication is explicit. Local Episodes, Traces, logs and proposals are not
automatically uploaded. Local-first execution can still send requests to a model
provider. Inspect those destinations before approving a run.

Public result material must exclude credentials and private evidence. Downloading or
buying an artifact does not make it safe to execute. A shared Regent profile does not
grant authority over another participant's publication key or wallet.

[SECURITY.md](../SECURITY.md#where-code-runs) says where code runs: which steps may
use the internet, and which run offline in throwaway containers.
