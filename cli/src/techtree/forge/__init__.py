"""The local task forge. ``docs/plan/repo2rlenv-local-lane.md``.

A forge build turns one local repository into Harbor tasks with Repo2RLEnv's
``commit_runtime`` pipeline and then qualifies every emitted task without a
model: a fresh container from the task image must fail the task's tests
unrepaired and pass them with the recorded reference patch. What passes is a
task package a local agent can be evaluated on; what fails is recorded with the
reason and is not offered.
"""
