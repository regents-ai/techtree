# Techtree Verify sample report

A sample that tests Techtree's own Agent Wallet Bench the way a Verify customer's product would be tested. Every result was observed on 27 October 2026 between 23:05 and 23:40 UTC, using only the page visits and downloads any visitor can make.

## Result

**12 of 14 checks passed. Two failed; neither changes a score.**

- Every score on the page matches the published scores file, and all 85 result links open a result that agrees with it.
- The headline numbers reproduce from the published data: 35 wallets left a plain key or password file, 4 safety failures in 85 judged tests, and 42 of 45 installs passed.
- **Failure 1, medium:** the checksum file in each test's download held no checksums. A checksum is a fingerprint that proves a file is unchanged. Every line of this file was hidden, so a reader could not check the files with it. The checksums the site lists for each file still worked.
- **Failure 2, low:** the full test page has no download button. The download is offered only in the result window opened from the score grid.

## Agreed workflows

| Workflow | Expected behaviour |
| --- | --- |
| Read the scores | The page and the scores file show the same scores, and each agent's overall score is the average of its scored boxes. |
| Open a result | Each score opens a result with the same score, verdict, agent and wallet tool. |
| Check the evidence | Each result offers a download, and each recorded file can be checked against a published checksum. |
| Follow a wrong link | An unknown test shows a clear "not found", never an error page or someone else's result. |

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| 1. The bench page loads | Pass | Opened in 0.36 seconds |
| 2. The scores file loads | Pass | Read at 23:05:53 UTC |
| 3. Page and scores file agree | Pass | All 23 rows and every box identical |
| 4. Overall score is the average of scored boxes | Pass | 23 of 23 rows; for example 2.0, 9.0, 9.0 and 9.0 average 7.25, shown as 7.3 |
| 5. Headline numbers reproduce | Pass | 27 plain password files and 8 plain key files make 35; 1 wallet and 3 install safety failures make 4; 40 and 45 judged tests make 85 |
| 6. Every result link opens and agrees | Pass | 85 of 85 open with the same score, verdict, agent and wallet tool |
| 7. The full test page opens | Pass | 3 of 3 sampled pages open |
| 8. The download arrives as a named zip file | Pass | Named after its test |
| 9. Each evidence file matches its listed checksum | Pass | 38 of 38 files in the sampled result |
| 10. The bundled checksum file can be used | **Fail** | 18 of 18 lines hidden, in all 4 files opened |
| 11. The download is offered on every view of a result | **Fail** | Offered in the result window, missing on the full test page |
| 12. An unknown test shows "not found" | Pass | The page, the record, the download and each file all answer "not found" |
| 13. The text versions for agents load | Pass | The page and its text version both load |
| 14. An unknown result on the bench page shows "not found" | Pass | "Not found" |

## Failures, reproduced

**1. The checksum file holds no checksums.** Open [this test's checksum file](https://techtree.sh/wallet-bench/e51ecab5-8380-4453-8c2c-58612a9045ef/evidence/T2/SHA256SUMS). Each line shows "[redacted]" where the checksum should be. Cause: before it stores a record, the bench hides anything that looks like a private key. A checksum looks like one, so it was hidden too. Suggested fix: write the checksum file after secrets are hidden. Recheck: open a new test's checksum file and confirm each line checks its file.

**2. No download on the full test page.** Open [the full test page](https://techtree.sh/wallet-bench/e51ecab5-8380-4453-8c2c-58612a9045ef): no download. Open [the same result from the score grid](https://techtree.sh/wallet-bench?test=wallet&result=e51ecab5-8380-4453-8c2c-58612a9045ef): "Download full results" is there. A reader who follows a link from the scores file lands on the full page and misses it. Suggested fix: offer the download on the full test page too. Recheck: open any full test page and download from it.

## Noticed, not counted

- A test's record keeps costs with stray digits, for example 0.105512800000000009 dollars. The page shows $0.11 correctly.
- In one install test the judge noted that the bench's list of changed files was empty although the tool was installed. The judge treated it as a gap in the bench, not a false claim by the agent.

## The repeatable suite

One script that takes a few minutes, paced well inside the site's request limit and safe to run against the live site after every release:

1. Compare every score on the page with the scores file (checks 1 to 4).
2. Recount the headline numbers and fail if they differ from the published findings (5).
3. Open every result, its full page and its record, and compare them (6, 7).
4. Check each download's type and name (8, 11).
5. Check a sample of evidence files against their checksums (9, 10).
6. Ask for unknown tests and expect "not found" (12, 14).

It prints the same table as above, with the evidence for any failure.

## Status on 28 October 2026

- Failure 1 is fixed and released. Each test run from 28 October 2026 carries a checksum file made from its published files. Tests recorded earlier keep their older checksum file.
- Failure 2 is still open.

Start a conversation about [Techtree Verify](/services/verify).
