# Techtree Cyber Assist sample report

A sample that reviews Techtree's own Agent Wallet Bench, which we own and may examine, the way a Cyber Assist customer's product would be reviewed. The review read the bench's source and its public pages on 27 October 2026, and sent no crafted requests to any live site.

## Result

**One validated finding, medium priority, now fixed.** The step that hides secrets in the bench's public test records could miss a private key, a Bankr access key or a Zerion agent token when the tool that printed it used colour. We checked the 260 published files from the two agents whose records contain colour and found no secret exposed. The weakness was fixed, verified and released on 28 October 2026.

| Finding | Priority | Status |
| --- | --- | --- |
| Secrets printed in colour could pass the hiding step | Medium | Fixed, verified and released 28 October 2026 |
| The hiding step also hid the bundled checksums | Low | Fixed and released 28 October 2026 |

## Risk for an agent integration

The bench publishes everything an agent does while it sets up a wallet. Its own findings show why that needs care: all 35 working wallets left their key, login or unlock password in a plain file; three agents typed a private key into a command; one agent made a hidden copy of its Bankr access key and deleted it later. A record of that work is only safe to publish if every secret in it is hidden first.

## Investigation

Before a record is stored, it passes two safeguards:

1. Known secrets. At the end of a test, the bench reads the account's secret-looking files and hides their values wherever they appear.
2. Secret shapes. It then hides anything shaped like a key or token.

The second safeguard is the only protection for a secret that is not in a file the first one reads at the end: a key printed and then deleted, a key kept inside the agent's own folder, a file whose name does not look secret, or a large file.

## Validation

A terminal colours text by placing a short code in front of it, and that code ends in a letter. The rules for a private key, a vendor access key and Zerion's agent token only started matching after a character that is not a letter or digit, so a key printed straight after a colour code was missed. The same happened after a written line return, and for a key starting with a capital "0X".

We copied the rules unchanged and ran them on test values that hold nothing:

| Input | Hidden? |
| --- | --- |
| A private key, plain | Yes |
| The same key on a new line inside a record | Yes |
| The same key printed in green | **No** |
| The same key after a colour code, as stored inside a record | **No** |
| The same key after a written line return | **No** |
| The key starting with a capital "0X" | **No** |
| A Bankr access key, plain | Yes |
| A Bankr access key printed in bold | **No** |
| A Bankr access key after a written line return | **No** |
| A Zerion agent token printed in colour | **No** |

Colour does reach the records. [Prime Agent's Zerion wallet test](https://techtree.sh/wallet-bench/e503a55b-da38-4f54-858c-a4822327fb8f) drove the Zerion tool through a simulated terminal, and its transcript holds 34 colour codes. [Grok Build's Bankr wallet test](https://techtree.sh/wallet-bench/11acaad4-8b27-49e5-8175-26db59b80ab8) holds 906 in one file. Across all 85 results, only these two agents' records contained colour codes, and in all 260 files of their 7 results no key or token follows a colour code or a line return.

## Impact

A working private key or access key would have been published in a public evidence file and in the test's download, readable by anyone, if two things met: a secret printed in colour or after a line return, and that secret not left in a file the first safeguard reads. Bench wallets hold nothing today, but the Money test, listed as coming soon, sends real USDC to bench wallets, and a Bankr access key controls a hosted Bankr account. Likelihood: low to moderate. Harm: a lost key. Priority: medium, to fix before the Money test runs.

## Repair

Proposed in this review: let each rule also start right after a colour code or a written line return, keep the colour code itself visible in the record, and accept a capital "0X". On the ten inputs above this hid all ten secrets, kept the colour codes and left an ordinary wallet address visible.

Released on 28 October 2026: every rule for a secret's shape now starts that way, also after other written control characters. In the same release the site writes each test's checksum file itself, from the published files, after secrets are hidden. Tests recorded before then keep their older checksum file.

## Fix verified

1. The bench's own hiding tests now include keys, access keys and agent tokens after colour codes and written line returns, and keys starting with "0X". They pass in the released version alongside every earlier case.
2. The ten inputs above were run again through the released version: all ten secrets hidden, the colour codes kept, and an ordinary wallet address left visible.

## Scope and open questions

Reviewed: the hiding step and its two safeguards, where records are stored and served, the guide the site gives agents about keys and sign-in, and how the Techtree plugin limits what the regents command can see. Read from public pages only: 85 test records and 260 evidence files.

Not covered, or still uncertain:

- How often wallet tools print secrets in colour in practice. The tools we saw used colour for prompts and status lines.
- No new wallet test has run through a simulated terminal since the release.
- The separate regents command and its sign-in client, account sign-in, and anything that needs a live probe.

Start a conversation about [Techtree Cyber Assist](/services/cyber-assist).
