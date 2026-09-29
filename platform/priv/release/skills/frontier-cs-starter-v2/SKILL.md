---
name: frontier-cs-starter-v2
description: Load first - output budget rules for any solution.cpp task. Write the problem's own scoring baseline as a valid program straight away, compile and test it, then improve it in small patches while budget remains.
version: 0.2.0
author: Regents Labs
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [techtree, frontier-cs, optimisation, cpp, evaluation]
    related_skills: []
---

# Techtree Frontier-CS Starter Skill

Use this Skill for an open-ended optimisation problem that asks for one C++
program at `/app/solution.cpp`. There is no known best answer. Each test scores
by how good your answer is, and scores `0` if the program is missing, does not
compile, breaks a limit or prints an answer that breaks a rule.

## Your budget

- Each reply stops after about 8,000 tokens, thinking included. A reply that is
  cut off does nothing: no file is written and no command runs.
- The whole attempt stops after about 32,000 output tokens. Whatever is in
  `/app/solution.cpp` at that moment is what gets scored.
- So think briefly and act early: keep the thinking in each reply to about
  2,000 tokens. Do not work out the best algorithm before you have a file. A
  plain valid answer beats a clever one that never gets written.

## Procedure

1. Read the Scoring section. It defines a baseline answer: for example "build
   nothing", the identity order, or a simple greedy it describes step by step.
   The baseline is always valid, and on many problems it earns a fair share of
   the marks.
2. In your next reply, call `write_file` for `/app/solution.cpp` with a short
   program that prints exactly that baseline. In the same reply, write the
   statement's example input to `/app/example.txt`.
3. Compile and run it in one command:
   `cd /app && g++ -O2 -pipe -std=gnu++17 -o solution solution.cpp && ./solution < example.txt`.
   Fix any error with `patch`.
4. Once it works, run `cp /app/solution.cpp /app/baseline.cpp`. From now on you
   always have a valid answer to fall back to.
5. Improve only while you have budget left. Make one small change at a time,
   such as a greedy pass or a local search that only keeps changes that stay
   valid and score better, and that stops by the clock at half the time limit.
   Apply it with `patch`, never by writing the whole file again. Compile and run
   the example after each change. If it breaks, run
   `cp /app/baseline.cpp /app/solution.cpp`.
6. Finish with a one-line reply. Do not print or read back the whole program.

## Program rules

- Standard C++17, reading standard input and writing standard output.
- Fast input and output: `ios::sync_with_stdio(false); cin.tie(nullptr);`.
- Fixed random seeds, no debug output, exactly the output format asked for.
- Keep the program short; every line you write costs budget.
