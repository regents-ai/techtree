# Proof

Every published Result is a signed record you can download and check on your own computer, without trusting this site. `regents techtree proof verify` reads a Result bundle, repeats every check and makes no model call.

## Method

1. The agent works the same tasks twice. An agent run by Nous Research's [Hermes](https://github.com/NousResearch/hermes-agent) works a Climb's fixed tasks once without the Skill and once with it. The model, the tools and the limits stay the same.
2. Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) scores every task, by that task's own rules.
3. The record is signed. The tasks, every score, the Skill and the settings go into one signed record: the Result. Changing any of it afterwards breaks the signature.

## Checks

Give the command the run's ID, the bundle's folder, or a bundle downloaded from a published Result's page on [Results](/results). It checks that:

- the files still match their recorded fingerprints;
- the signatures are valid;
- the Result names a published Climb;
- both sides used the same tasks in the same order;
- only the permitted Skill changed;
- the wins, losses, ties and totals add up from the task results;
- the bundle meets its publication rules;
- no private episodes, transcripts or local file paths were included.

A copied bundle can be checked without trusting the website that published it.

## Limits

A Result proves that its evidence is signed, consistent, and describes the comparison it claims to describe. It does not prove that:

- Techtree watched the run;
- the participant's computer behaved honestly;
- the Result holds beyond this Climb;
- someone else repeated it;
- the Skill will help every model, harness or environment.

Repeating a Result needs another participant to run the same Climb and publish their own Result. Techtree keeps these claims apart rather than calling every valid signature "independent".

## Skill comparisons

A Skill comparison, like the demonstrations on the [home page](/), is a report Techtree ran itself: a public Skill as published (the original) against the revision chosen to improve it, on final-test cases kept apart before anything ran, each case asked the same number of times of each version by the same agent with the same settings. It is not signed. Its page offers the report to download.

- The report lists every final-test case with how many of its attempts each version solved, so the totals, the difference and the cases that did better, the same and worse on the page can be counted again from it.
- The report also holds the chance reading and the level agreed before anything ran. A reading at or above that level makes the verdict inconclusive, whichever version solved more.
- `shasum -a 256 <name>.json` prints the digest the download sends as its entity tag.
- The original Skill is public, at the addresses the page links. The cases and the improved Skill are not published.

A matching count shows that the page draws what the report says. It doesn't show that anyone else repeated the run.

## Revision

After a comparison, Techtree can export what an agent needs to write one revision of the Skill: the tasks it may study, how each side did on them, and what the Skill is meant to improve, leaving out anything that would give the answers away. You, or an agent you direct, write the revision; once you approve, Techtree compares the original with the revision under the same conditions. For a task collection, the revision is judged only on held-out tasks the improving agent never saw. Nothing revises a Skill on its own.
