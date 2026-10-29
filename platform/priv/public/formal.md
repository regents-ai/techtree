# Techtree Formal

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

Funding Cap, in progress. The Wallet Bench pays each agent it tests a small amount of USDC, and ETH for fees. This model describes how those payments stay within each run's total while several tests run at once, a failed try is retried, or a payment's result on Base is not known yet.

- Property: for each token, the payments counted, and the money that really moves on Base, never pass the run's total.
- Model: the design of the funding step, written in Quint, not the code itself. It assumes Base never undoes a payment it has included, and that reads from Base agree.
- Status: the model is still being written, so no result is claimed yet.

[See the files on GitHub]({{example}}).

## Submit Code

Write to [build@regents.sh]({{mailto}}) with:

- The code, or a link to its repository.
- The property you need guaranteed, in plain words.
- Where it runs, such as a chain, a server or a device.

We reply by email with a scoped quote. The work is paid, and the price is set once the scope is agreed.
