You are planning test tasks for one Agent Skill. You propose; a person reviews
your proposal, and nothing is built until they approve it.

The Skill is below, file by file, exactly as its author wrote it. Read all of
it. Then propose at most {max_tasks} distinct tasks, each one a workflow the
Skill actually teaches, that an agent could be given as a self-contained job
in an offline Linux terminal and graded by a program.

A good task:

- is something the Skill instructs, not something it merely mentions;
- has a result a program can check exactly, from files the agent leaves;
- is stated clearly enough that two careful experts would agree on the
  answer;
- can be solved by an expert within a few hours;
- is hard because of what it asks, not because of its volume;
- would be worth doing for someone who uses the Skill.

A task must not need a network, a live account, a graphical interface, or
knowledge that is not in the Skill or the task's own files. Different tasks
exercise different parts of the Skill; do not propose the same workflow twice
with new inputs.

For each task give:

- `name`: a short lowercase name, letters, digits and hyphens;
- `summary`: one sentence saying what the agent is asked to do;
- `scenario`: the situation the agent starts in and the files it is given;
- `success_criteria`: the checks a program makes on the result, each one a
  sentence that is either true or false of the agent's output;
- `verifier_strategy`: how the checking program decides each criterion,
  including how it tells a correct answer from a plausible wrong one.

Answer with one JSON object and nothing else, no prose and no code fence:

{"tasks": [{"name": "...", "summary": "...", "scenario": "...", "success_criteria": ["..."], "verifier_strategy": "..."}]}

These planning criteria are adapted from the planning stage of NVlabs
Skill2Env (revision 9beb0b64a70290f862c8374bbef21f2ac88992ab, Apache-2.0).

The Skill follows.
