---
name: frontier-cs-starter-v1
description: Solve an open-ended C++ optimisation problem with a feasible answer first, then improve it within the time limit.
version: 0.1.0
author: Regents Labs
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [techtree, frontier-cs, optimisation, cpp, evaluation]
    related_skills: []
---

# Techtree Frontier-CS Starter Skill

Use this Skill when a task gives you an open-ended optimisation problem from the
**Frontier-CS Open-Ended** Climb and asks for a C++ program. These problems have
no known best answer. Every test file is scored on how good your answer is, and
an answer that breaks any rule scores `0` for that file.

This starter is deliberately basic: it gets a valid answer every time and makes
one simple improvement pass. There is plenty of room for a better Skill.

## Procedure

1. Read the whole statement. Write down, in your own words, the input format, the
   output format, every rule an answer must satisfy, and how the score is worked
   out.
2. Note the time limit and memory limit. Plan to finish in at most 70% of the time
   limit.
3. Write the simplest program that always prints a valid answer: the baseline the
   statement describes, or the most obvious safe construction. Correct beats clever.
4. Write a small checker of your own, from the statement's rules, that says
   whether an answer is valid and what it would score. Run it on the sample input
   and on a few inputs you make up, including the smallest and largest sizes the
   constraints allow.
5. Only once every answer is valid, improve it: start from the valid answer and
   repeatedly try a small change, keeping it only when the answer stays valid and
   scores better. Stop by checking the clock, well before the time limit.
6. Keep the valid baseline answer in hand throughout, and print it if anything in
   the improvement step goes wrong.

## Program Contract

- Write standard C++17 that reads from standard input and writes to standard
  output, and save it where the task says.
- Compile it with `g++ -std=c++17 -O2` and fix every warning that points at a
  real mistake before you finish.
- Use fixed random seeds so the program behaves the same on every run.
- Read and write with fast input and output; large test files are normal.
- Print exactly the output format the statement asks for, with no extra text.
