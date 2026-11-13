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

A Skill comparison, like the case study on the [home page](/), is a report Techtree ran itself: one model on the same held-out tasks, once without the Skill and once with it, with the same settings. It is not signed. Its page offers the report and the traces, every task's exchange with the model, to download, and names each by its SHA-256 digest.

- The traces' digest is the SHA-256 of the file's exact bytes: `shasum -a 256 <name>.traces.jsonl` prints the hex after `sha256:`.
- The report's digest is the SHA-256 of the RFC 8785 canonical JSON of its `schema_version`, `kind` and `spec`.
- Every task's two scores are in the report, so the wins, ties, losses and solved counts on the page can be counted again from it.

Matching digests show that the files are the ones the page describes. They don't show that anyone else repeated the run.

## Revision

After a comparison, Techtree can export what an agent needs to write one revision of the Skill: the tasks it may study, how each side did on them, and what the Skill is meant to improve, leaving out anything that would give the answers away. You, or an agent you direct, write the revision; after your yes, Techtree compares the original with the revision under the same conditions. For a task collection, the revision is judged only on held-out tasks the improving agent never saw. Nothing revises a Skill on its own.
