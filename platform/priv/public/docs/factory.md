# Factory

Prime Intellect's Model Factory puts training, serving and improving a model you own on one system. This guide lists what a company needs before its first run, in order, and where Techtree helps. Techtree is independent of Prime Intellect and uses its open tools.

## Decide

Owning a model pays when one task repeats often, has a clear right answer, and costs you today in fees, speed or control. Before any training, try a cheaper existing model and a better prompt or Skill. If that gets you there, stop. Techtree: [Skills](/services/skills), and the first step of [Models](/services/models).

## Test

Write the test before anything else. Set aside cases the model will never train on, and score them the same way every time. This test decides whether training worked, and later whether each new version is ready for real work. Techtree: [Evals](/services/evals).

## Tasks

Training needs tasks an agent can attempt, and a score for each attempt. Package them as an environment for Prime Intellect's Verifiers, which Model Factory trains and evaluates on; Harbor's format is supported too. Check the scoring before you train on it: reference solutions pass, known wrong answers fail, and an empty attempt scores zero. Techtree: [Environments](/services/environments).

## Baseline

Measure what you run today and the small open model you plan to train, on the same test, several times over. The gap between them is the target.

## Train

Prime Intellect's hosted training takes a prime-rl configuration file and runs it on its machines; Prime Intellect bills that machine time itself. Start with training on your accepted examples. Add reinforcement learning once the scoring has been checked. Agree a budget cap before the run. Techtree: [Models](/services/models) writes and checks the plan. Techtree has not yet published a training run of its own; the Models page marks each step Tested or Planned.

## Deploy

Model Factory serves a trained model from an endpoint in the OpenAI format, on demand or on dedicated machines. Before it takes real work, test the trained model on the cases it never saw, and compare the full running cost with what you pay now.

## Improve

Keep a record of what the model does in real use. Turn its failures into new tasks, review each one, train again, and run the same test before the new version goes into service.

## Dedicated

When training has become routine, Prime Intellect offers dedicated Model Factory deployments with reserved machines, arranged with its team. You arrive with the three things that take longest to get right: a test, an environment, and a recipe that has already run.

## Start

Bring one task you repeat and a few examples of good and bad work. [Contact](/#begin) · [Model Factory](https://www.primeintellect.ai/model-factory) · [Hosted training](https://docs.primeintellect.ai/hosted-training/getting-started)
