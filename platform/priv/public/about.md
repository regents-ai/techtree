# About Techtree

Techtree shows whether a Skill really makes an agent better, and gives you a Result anyone can check.

## What it does

Your agent works the same fixed tasks twice: once without the Skill and once with it. The model, the tools and the limits stay the same, so any difference in the results comes from the Skill. Techtree calls this a Climb.

Techtree can also make the tasks for you. From a Skill, it plans test tasks from what the Skill teaches, checks them, and keeps only the ones you accept. From a repository, it finds past fixes whose tests fail before the fix and pass after it, and turns each one into a repair task. Both are experimental, and both happen on your own computer.

Every finished comparison ends in a signed Result. You can check a Result offline, on your own computer, without trusting this site, and you can choose to publish it so that others can check it too. Published Results are listed in the order they arrived and are never ranked.

## Three independent parts

Techtree is built from three independent parts. [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers) scores the tasks, [Nous Research's Hermes](https://github.com/NousResearch/hermes-agent) runs the agent, and Techtree runs the comparison and keeps the evidence.

## Who runs it

Techtree is built and run by Regents Labs, which also builds [Regents](https://regents.sh), [Autolaunch](https://autolaunch.sh) and [Patchbay](https://patchbay.help). The code is public at [github.com/regents-ai/techtree](https://github.com/regents-ai/techtree) under the MIT licence. Techtree is a working technical preview.

## Where to go next

- [Start](/start): try the example Climb, evaluate your own Skill, or build tasks from your repository.
- [Verify](/verify): what verification establishes, and how to check a Result offline.
- [Contact](/contact): how to reach the people who run Techtree.
- [Privacy](/privacy): what Techtree keeps, and what it never sees.
