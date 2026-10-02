---
name: tasksmith-starter-v1
description: A plain first approach to making a described change in a Python repository, checked against the repository's own tests. Use when a task asks you to change code in /workspace to match a written description.
---

# Making a described change in a repository

1. Read the task's instructions to the end before touching anything. Write down every name,
   signature, default value, error message and behaviour they state. Those exact details are
   what gets checked.
2. Find the code. Search the repository for the names the instructions use and read the files
   around them, including the neighbouring tests, so the change fits how the code already works.
3. Make the smallest change that does everything the instructions ask. Keep the repository's
   own style, naming and import patterns. Do not edit or delete existing tests.
4. Check it. Run the existing tests closest to the code you changed with `python -m pytest`
   and the narrowest path that covers it. There is no network, so do not install anything.
   Then write a few lines of Python that call the new or changed code the way the instructions
   describe, and run them.
5. Re-read the instructions and tick off each detail you wrote down in step 1 against the code.
   Fix anything missing, then stop.
