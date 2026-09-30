---
name: frontier-cs-starter-v4
description: Load first for any open-ended optimisation task that asks for one C++ program at /app/solution.cpp. Design a strong method, build a local scorer, and make the program search until its time runs out.
version: 0.4.0
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
program at `/app/solution.cpp`. No best answer is known. Each hidden test scores
how good your answer is, and scores `0` if the program is missing, fails to
compile, breaks the time or memory limit, or prints an answer that breaks a rule.

## What decides the score

The method you choose matters far more than polish. A program that stops after
a fixed amount of work wastes most of the time it is allowed. The best answers
come from a good constructive method followed by a search that keeps improving
until the clock says stop, checked against a scorer you wrote yourself.

You have plenty of room: about 96,000 output tokens and one hour for the whole
attempt, and up to about 32,000 tokens in one reply (a reply cut off at that
point does nothing). Most attempts use a quarter of that. Use it.

## Procedure

1. **Save a valid answer first.** Write the simplest valid program (the
   statement's own baseline if it names one) to `/app/solution.cpp`, and the
   example input to `/app/example.txt`. Compile and run it:
   `cd /app && g++ -O2 -pipe -std=gnu++17 -o solution solution.cpp && ./solution < example.txt`.
   Then `cp solution.cpp baseline.cpp`. This is only insurance; do not build on it.
2. **Design before you code.** Think about the problem's structure and write
   down two or three quite different methods, with their cost at the maximum
   input size. Good candidates: solve a relaxed or global version exactly and
   then repair it; build the answer greedily in a smart order; split into
   pieces that can be solved exactly (dynamic programming, matching, shortest
   paths). Prefer the method that uses the structure over the one that looks
   like the statement's baseline.
3. **Build a local judge.** Write `/app/gen.py` (or `gen.cpp`) that makes random
   inputs within the constraints, at small, medium and maximum size, with a few
   different shapes. Write `/app/score.cpp` that reads an input and an output,
   checks every rule in the statement, and prints the objective (and `INVALID`
   with the reason when a rule breaks). Make 6 to 10 test inputs, including at
   least two at maximum size.
4. **Write the real program.** Readable code, as long as it needs to be.
   Structure it as: read input, build an initial answer with your chosen
   method, then improve it in a loop (local search, simulated annealing, or
   restarts) that checks `std::chrono::steady_clock` every 64 to 256 steps and
   stops at about 70% of the time limit, measured from the start of `main`.
   Keep the best valid answer seen and print that one. Check the answer
   against the rules before printing; if it fails, print the baseline answer.
5. **Measure, then keep or reject.** Run the program on every test input with
   `timeout`, score each output, and compare the average with the previous
   version and with the baseline. Keep a change only if the average improves
   and nothing is invalid or too slow. Save each kept version (`cp solution.cpp
   best.cpp`).
6. **Improve in rounds.** Try a stronger move set, a better initial answer, a
   faster score update (incremental rather than recomputing everything), or
   the second method from step 2. Rewrite the file for a structural change and
   use `patch` for a small one. Recompile and re-measure after each change. If
   a change breaks something, go back to `best.cpp`.
7. **Do not stop early.** Keep going while you have used less than about 40
   minutes and 70,000 output tokens and a change can still help. Stop when
   the last few ideas no longer raise the average.
8. **Finish safely.** Make sure `/app/solution.cpp` is the best measured
   version, compiles, and uses at most about 80% of the time limit on a
   maximum-size input (`timeout` with the limit). End with a one-line reply.

## Program rules

- Standard C++17, reading standard input and writing standard output.
- Fast input and output: `ios::sync_with_stdio(false); cin.tie(nullptr);`.
- A fixed random seed, no debug output, exactly the output format asked for.
- Never print or read back a whole program or a large test file; it costs
  budget and shows you nothing new.
