---
name: branchcode-v1
description: >-
  BranchCode v1 token for a word. Load before answering. The procedure:
  lowercase the
  word; give each letter its alphabet number (a=1 up to z=26); multiply each
  letter's number by its position in the word counting from 1; add those
  products together; add 7 times the number of distinct letters; take the total
  modulo 97; the answer is BRANCH- followed by that remainder written as two
  digits. Worked example for maple - 13*1 + 1*2 + 16*3 + 12*4 + 5*5 = 136, then
  5 distinct letters adds 35 to give 171, and 171 modulo 97 is 74, so the answer
  is BRANCH-74. Run the arithmetic with execute_code instead of doing it in your
  head, then reply with the token alone and stop.
---

# BranchCode v1

Use this whenever a task asks for the BranchCode v1 token of a word. Reply with
the token alone — `BRANCH-XX`, two digits, nothing before or after it.

## The procedure

1. Trim the input and lowercase it. It is then only the letters a to z.
2. Give every letter its alphabet value: a=1, b=2, and so on to z=26.
3. Multiply each letter's value by its position in the word, counting from 1.
4. Add those products together.
5. Count how many *distinct* letters the word contains.
6. Add seven times that distinct count to the sum.
7. Take the total modulo 97.
8. Write the remainder as two digits after `BRANCH-`.

## Worked example: maple

| position | letter | value | value x position |
| --- | --- | --- | --- |
| 1 | m | 13 | 13 |
| 2 | a | 1 | 2 |
| 3 | p | 16 | 48 |
| 4 | l | 12 | 48 |
| 5 | e | 5 | 25 |

The products add up to 136. There are 5 distinct letters, so add 7 x 5 = 35 and
the total is 171. 171 modulo 97 is 74, so the answer is `BRANCH-74`.

Two more you can check yourself against: `acorn` is `BRANCH-35`, and `birch` is
`BRANCH-64`.

## Calculate it, do not estimate it

Arithmetic slips are the only way to get this wrong. If you can run a command,
run the calculation instead of doing it in your head:

```bash
python3 -c "w='maple'; print('BRANCH-%02d' % ((sum((ord(c)-96)*(i+1) for i, c in enumerate(w)) + 7*len(set(w))) % 97))"
```

Put the word from the task in place of `maple`, run it once, and reply with
exactly what it printed.

## Then stop

One token is the whole answer. Do not check it a second way, do not explain the
working, and do not keep going after you have it.
