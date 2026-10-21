# Repo2RLEnv

Turn a repository into practice for agents. Repo2RLEnv is Techtree's first planned service: turning real software and its repair history into environments where agents can practice, test better Skills, and show what actually improved. Building and checkout are not open yet.

## What it brings together

Repo2RLEnv will make tasks from a repository's history and connect them to Prime Intellect's Verifiers and prime-agent, NVIDIA NeMo's Fabric and Relay libraries, and Nous Research's Hermes Agent. Techtree binds the environment, the agent's settings, the Skill versions and the results into evidence you can inspect, so you can decide which changes your agent should keep.

## How an environment will be built

1. Admit: pin the repository, revision, history and rights.
2. Generate: build the tasks as a task package.
3. Qualify: check a clean build, reset, controls and a reference repair.
4. Deliver: keep the evidence, as a fixed release and a qualification report.

The first planned lane is Python repositories that use pytest, with supported pull-request history. It is not support for any repository. Agent evaluation follows as a separate job, and model training belongs to a later release.

These are planned integrations, not a claim that the service is available today. Each supported combination must pass its own qualification, and improvement is measured rather than guaranteed.
