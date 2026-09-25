You are planning test tasks for one Agent Skill. You propose; a person reviews
your proposal, and nothing is built until they approve it.

The Skill is below, file by file, exactly as its author wrote it. Read all of
it. First say what the Skill claims to improve: at most {max_tasks} claims, each
one something an agent does better by following the Skill, with the
observable behavior that would show it in the files an agent leaves. Then
propose at most {max_tasks} distinct tasks, each one testing exactly one of
those claims, that an agent could be given as a self-contained job in an
offline Linux terminal and graded by a program. Every claim is tested by at
least one task.

For each claim give:

- `claim_id`: `C1`, `C2` and so on, in order;
- `statement`: one or two sentences saying what the Skill claims to improve;
- `observable`: the behavior a program could see in an agent's result that
  would show the claim holds.

Each task is one kind of case for its claim:

- `positive`: a case where following the Skill should produce the correct
  observable behavior;
- `boundary`: a case at the edge of where the claim applies;
- `counterexample`: a case where a naive or over-eager application of the
  Skill would give a wrong result, or where the Skill should not change the
  correct outcome. It guards against the Skill overreaching.

A good task:

- is something the Skill instructs, not something it merely mentions;
- has a result a program can check exactly, from files the agent leaves;
- is stated clearly enough that two careful experts would agree on the
  answer;
- can be solved by an expert within a few hours;
- is hard because of what it asks, not because of its volume;
- would be worth doing for someone who uses the Skill.

A task must not need a network, a live account, a graphical interface, or
knowledge that is not in the Skill or the task's own files. A task asks for a
result; it does not repeat the Skill's instructions. Different tasks exercise
different parts of the Skill; do not propose the same workflow twice with new
inputs.

For each task give:

- `name`: a short lowercase name, letters, digits and hyphens;
- `claim`: the `claim_id` of the one claim it tests;
- `kind`: `positive`, `boundary` or `counterexample`;
- `summary`: one sentence saying what the agent is asked to do;
- `scenario`: the situation the agent starts in and the files it is given;
- `success_criteria`: the checks a program makes on the result, each one a
  sentence that is either true or false of the agent's output;
- `verifier_strategy`: how the checking program decides each criterion,
  including how it tells a correct answer from a plausible wrong one.

Write every text value as plain text on one line, with no line breaks, tabs
or formatting codes. Answer with one JSON object and nothing else, no prose
and no code fence, giving the claims first and then the tasks:

{"claims": [{"claim_id": "C1", "statement": "...", "observable": "..."}], "tasks": [{"name": "...", "claim": "C1", "kind": "positive", "summary": "...", "scenario": "...", "success_criteria": ["..."], "verifier_strategy": "..."}]}

These planning criteria are adapted from the planning stage of NVlabs
Skill2Env (revision 9beb0b64a70290f862c8374bbef21f2ac88992ab, Apache-2.0).

The Skill follows.
