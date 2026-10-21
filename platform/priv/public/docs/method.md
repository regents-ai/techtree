# How a Result is proved

Most agent improvements are anecdotes. Someone changes a prompt or a Skill, runs a few examples, and says the agent feels better, while the model, the harness, the tools, the tasks or the budget may have changed at the same time.

Techtree asks a narrower question: **did changing this one Skill make the agent better?** And a second one: **how can someone else check the answer without running the whole test again?**

Its first answer is a controlled comparison: the same agent works the same tasks twice, and only the Skill changes. Techtree calls this a Climb.

## The proof bundle

A Techtree proof holds the signed comparison, the result of every task, the exact list of tasks, and the fingerprints of the files behind the claim. Anyone holding the bundle can check it offline, with no model call and without contacting Techtree:

```sh
regents techtree proof verify path/to/result-bundle
```

It checks that:

- the files still match their recorded fingerprints;
- the signatures are valid;
- the Result names a published Climb;
- both sides used the same tasks in the same order;
- only the permitted Skill changed;
- the wins, losses, ties and totals add up from the task results;
- the bundle meets its publication rules;
- no private episodes, transcripts or local file paths were included.

A copied bundle can be checked without trusting the website that published it.

## What a Result does not prove

A Result proves that its evidence is signed, consistent, and describes the comparison it claims to describe. It does not prove that:

- Techtree watched the run;
- the participant's computer behaved honestly;
- the Result holds beyond this Climb;
- someone else repeated it;
- the Skill will help every model, harness or environment.

Repeating a Result needs another participant to run the same Climb and publish their own Result. Techtree keeps these claims apart rather than calling every valid signature "independent".

## Revising a Skill once

After a comparison, Techtree can export what an agent needs to write one revision of the Skill: the tasks it may study, how each side did on them, and what the Skill is meant to improve, leaving out anything that would give the answers away. You, or an agent you direct, write the revision; after your yes, Techtree compares the original with the revision under the same conditions. For a task collection, the revision is judged only on held-out tasks the improving agent never saw. Nothing revises a Skill on its own.
