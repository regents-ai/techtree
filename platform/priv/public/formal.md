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

## Submit Code

Write to [build@regents.sh]({{mailto}}) with:

- The code, or a link to its repository.
- The property you need guaranteed, in plain words.
- Where it runs, such as a chain, a server or a device.

We reply by email with a proposed scope.
