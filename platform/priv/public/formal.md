# Formal

Formal verification: a proof shows that a precise model of the code keeps a stated property for every input the model allows, not only the inputs a test tried, and a computer checks every step. This page is experimental.

## Basics

A test tries the inputs someone picked. A proof covers every input the model allows.

- Property: the rule you need, such as "the total paid never passes the cap".
- Model: a precise description of the code, or of its design, that the proof is about.
- Proof: a step-by-step argument that a small checker program accepts.

## Limits

A proof covers the property as written and the model as built, under the assumptions it states.

- A property that misses the point gives a sound proof of the wrong thing.
- Anything outside the model, such as the compiler, the chip, other services or the people calling the code, is assumed, not proven.
- A proof about the design says nothing about whether the code follows it.
- In Anthropic's words, "Formally verified" does not mean "bug-free." [Source](https://www.anthropic.com/research/formal-verification)

## Frontier

Recent advances, newest first.

{{frontier}}

## Example

Funding Cap, proved. The Wallet Bench pays each agent it tests a small amount of USDC, and ETH for fees. This model describes how those payments stay within each run's total while several tests run at once, a failed try is retried, or a payment's result on Base is not known yet.

- Property: for each token, the payments the bench keeps, and the money that really moves on Base, never pass the run's total.
- Model: the design of the funding step, written in Quint, not the code itself. It assumes Base never undoes a finalized block, and that a Base server that is behind shows an older record, never a false one.
- Proof: Apalache proves both rules hold for runs of any length within the model's limits: three tests funded at once, a total of two payments of each token, and one retry each.
- Found: two ways past the total. If the database ran at repeatable read, three tests could each keep a payment against a total of two; a test on Postgres shows the same, and Techtree runs at read committed. And a Base server that is behind could make a lost payment look replaced, freeing room past the total; Techtree now reads Base at its finalized block, and the model was checked again.
- Code: the proof covers the design, not the code. A test on Postgres and tests against a stand-in Base server tie the two together.

[See the files on GitHub]({{example}}).

## Submit Code

Write to [build@regents.sh]({{mailto}}) with:

- The code, or a link to its repository.
- The property you need guaranteed, in plain words.
- Where it runs, such as a chain, a server or a device.

We reply by email with a proposed scope.
