You are building one test task for an Agent Skill. A person reviewed and
approved the task below; you turn it into the files of a task package. You
cannot run anything: answer with the files, and Techtree will build and check
them on the person's machine, offline.

An agent will later be given the task in a Linux container with no network. It
reads `instruction.md`, works in the files the environment gives it, and leaves
its result where the instruction says. A program then grades what it left.

Write these files:

- `instruction.md`: what the agent is asked to do, stated completely, as the
  agent will read it. Name every input file and every file the agent must
  leave, by absolute path. Do not mention the tests, the solution or the
  grading.
- `environment/Dockerfile`: the container the agent starts in. Its first line
  is exactly `FROM {base_image}`, and no other image may be named. Use only
  `FROM`, `RUN`, `COPY`, `WORKDIR` and `ENV`; `COPY` takes files from the
  `environment/` directory by their plain relative names. The build has no
  network, so `RUN` cannot download or install anything. Keep the agent's
  files under `/app`.
- Any input files the Dockerfile copies, under `environment/`.
- `tests/test.sh`: the grading program, run by `bash` as `/tests/test.sh`
  in the same container after the agent has finished. It checks each success
  criterion exactly and writes `1` to `/logs/verifier/reward.txt` when all of
  them hold and `0` otherwise, creating `/logs/verifier` first. It may use the
  Python in the image, and any helper files you put under `tests/`, which is
  mounted at `/tests`.
- `tests/rubric.md`: the success criteria in words, one per line.
- `solution/solve.sh`: a reference solution, run by `bash` as
  `/solution/solve.sh` in a fresh container, that leaves a result the tests
  accept. It must work out the answer the way the Skill teaches rather than
  contain a copied answer where the task is to compute one.

The tests must fail when the agent does nothing, and pass for the reference
solution. They must accept every correct result and reject a plausible wrong
one, such as a result that follows a rule the Skill does not teach. Mark
`tests/test.sh` and `solution/solve.sh` executable.

Do not include the Skill's own files, `SKILL.md`, `task.toml`, hidden files,
or any credential. Do not write the reward file anywhere but in the tests.

Answer with one JSON object and nothing else, no prose and no code fence:

{"description": "one sentence saying what the task asks", "keywords": ["..."], "artifacts": ["/app/..."], "files": [{"path": "instruction.md", "text": "...", "executable": false}]}

`artifacts` lists, by absolute path, every file or directory the agent must
leave; none of them may contain another, and none may be under `/logs`. Each
file's `text` is its complete contents.

This building contract is adapted from the task-construction stage of NVlabs
Skill2Env (revision 9beb0b64a70290f862c8374bbef21f2ac88992ab, Apache-2.0).

The task follows, then the Skill.
