# Techtree commands

Every `regents techtree` command, written before it is built. A command that is not
described here does not exist yet. Techtree's commands are native code in regents-cli: they
run a local engine, check signed proofs and write files, which a plain request description
cannot say. So this folder has no `commands.json`. The regents-cli chief builds each one from
its section here.

This file starts with the two commands added for reruns (decision 67 c) and public Skills
(decision 68 a). Each existing command gets its section here when it next changes.

Every command also takes `--json` (print the answer as JSON) and `--base-url URL` (the site's
address; also `TECHTREE_BASE_URL`). A refusal prints the site's `code`, `message` and `hint`
and exits non-zero.

## regents techtree skill fetch \<root_digest\>

- **What it does:** downloads a published Skill by its fingerprint, checks every file against
  that fingerprint, and writes the files to a folder. It never runs anything in the Skill.
- **Who may run it:** anyone (public).
- **What it changes:** nothing on the site. It writes files on this machine.
- **Route:** `GET /api/v1/skills/{root_digest}` → `getSkill`
- **Inputs:**
  - `<root_digest>`: the Skill's fingerprint, `sha256:` and 64 lowercase hex characters, as a
    Result page or `GET /api/v1/publications/{bundle_digest}` shows it (`skill_digest`).
  - `--to DIR`: where to write the files. Left out: `./<skill name>-<first 12 hex>`. The
    command refuses a folder that exists and is not empty.
- **Answer:**
  `{"skill": <SkillArtifact>, "files": [{"path", "content_base64"}, …], "results": [<bundle digest>, …]}`.
  - `skill` is the `skill.json` the Result's proof carried (`techtree.skill.v1alpha1`).
  - `files` holds one entry for each file `skill.files` lists, in the same order.
  - `results` lists the published Results that carried this Skill and are not withdrawn,
    newest first.
- **Refusals:**
  - 400 `invalid_skill_digest`: the fingerprint is not in that form.
  - 404 `skill_not_found`: no published Result that is not withdrawn carried this Skill.
  - On this machine, before writing anything: `skill_fingerprint_mismatch` when a file's
    bytes or the file list do not give the fingerprint asked for, and `skill_path_invalid`
    when a path would land outside `DIR`.

Server:

```text
root_digest must be "sha256:" + 64 lowercase hex      else 400 invalid_skill_digest
entries = published Results whose skill_digest == root_digest, not withdrawn, newest first
no entries                                           -> 404 skill_not_found
bundle  = the newest entry's stored bundle bytes, read as submitted
skill   = bundle member "skill.json"
files   = bundle member "skill/<path>" for each path in skill.files
answer 200 {"skill", "files", "results": entries' bundle digests}
  Content-Type: application/json; X-Content-Type-Options: nosniff; Cache-Control: public, max-age=300
```

This machine:

```text
answer = GET /api/v1/skills/<root_digest>
for each file: sha256(bytes) == listed digest, size == listed size, path is POSIX relative
  with no "..", no leading "/", no backslash, and a listed suffix (.md .txt .json .yaml .yml)
root_digest recomputed from skill.files (RFC 8785 canonical JSON of the sorted list) == asked
any check fails  -> refuse, write nothing
otherwise        -> write each file under DIR and print the folder and the Results it came from
```

- **Server needs:** the Skill inside each published proof (68 a, below), and the
  `skill_digest` the site already keeps on every published Result. The answer is data: the
  site serves the files as base64 inside JSON and never runs, renders or imports them.
- **History:** 2026-10-05 added.

## regents techtree climb prepare --rerun-of \<bundle_digest\>

- **What it does:** makes a local draft that reruns a published Result. The draft uses the
  same Campaign and the same Skill, with a new pair of runs (without and with the Skill) on
  this machine, signed with this machine's publisher key. `climb start`, `climb run` and
  `climb publish` then work on it as on any draft.
- **Who may run it:** anyone set up for Climbs. The runs use this person's own model access,
  as every Climb does.
- **What it changes:** nothing on the site. It writes a draft on this machine.
- **Route:** `GET /api/v1/publications/{bundle_digest}/bundle` → `getPublicationBundle`
  (existing).
- **Inputs:** `<bundle_digest>`: the published Result's bundle digest, as its page and
  `GET /api/v1/publications/{bundle_digest}` show it. There is no Climb argument: the
  Result names its Campaign.
- **Answer:** the draft's folder, the Climb and Campaign it reruns, and the Skill's
  fingerprint.
- **Refusals:**
  - 404 `publication_missing`: no Result is published under that digest.
  - 410 `publication_withdrawn`: its publisher withdrew it.
  - On this machine: the bundle's offline check fails, or
    `rerun_campaign_not_in_release` when its Campaign is not one in this release. Results
    made under `techtree.campaign.v3` cannot be rerun.

This machine:

```text
bundle   = GET /api/v1/publications/<bundle_digest>/bundle; check it offline in full
campaign = the bundle's Campaign digest; must be a Campaign in this release
           else refuse rerun_campaign_not_in_release
skill    = the bundle's skill.json and skill/ files (68 a); root_digest must equal the
           candidate experiment's Skill digest
draft    = ordinary draft: that Campaign, that Skill, a new baseline and candidate run
report   = when published, the uplift report carries "rerun_of": <bundle_digest>
```

Server, when a report with `rerun_of` is published (`POST /api/v1/publications`):

```text
rerun_of is null                         -> as today
original = the published Result with bundle_digest == rerun_of (withdrawn or not)
           none                          -> 422 rerun_original_unknown
original.campaign_spec_digest == this report's campaign_spec_digest
                                         else 422 rerun_campaign_mismatch
original.skill_digest == this proof's skill root_digest
                                         else 422 rerun_skill_mismatch
store rerun_of in the Result's assessment; nothing else changes
```

- **Pages:** a rerun's page names the Result it reruns and says whether it was signed by the
  same publisher key or another one. The original's page lists its reruns and counts them as
  Results, never as people: "2 reruns", not "2 people". A rerun from another key is still a
  report from someone's own machine, not independent reproduction, and one person can hold
  many keys.
- **Server needs:** `rerun_of` in `techtree.uplift-report.v3`, signed with the rest of the
  report. The relation is stored in the Result's existing assessment, with no new table.
- **History:** 2026-10-05 added.

## What a published proof carries for its Skill (68 a)

From `techtree.campaign.v4` on, a proof bundle (`techtree.local-proof-bundle.v1alpha2`) carries
its candidate Skill: `skill.json` (the existing SkillArtifact, as canonical JSON) and
`skill/<path>` holding each listed file's raw bytes, all listed in the bundle manifest. Those
`skill/` files are the only bundle members that are not JSON documents. Publishing a Result makes
its Skill public. Each Climb's data policy already says so
(`candidate_skill.public_release: required_for_climb`, the Skill owned by its participant), and
`climb publish` says it in plain words before anything is sent.

The site accepts a proof only when its Skill holds all of these. `climb publish` checks the
same list before anything leaves the machine:

```text
skill.json root_digest == the candidate experiment's Skill digest        skill_fingerprint_mismatch
every file's bytes give its listed digest and size                       skill_fingerprint_mismatch
paths: POSIX relative, unique, sorted, no "..", no leading "/", no "\",
       suffix .md .txt .json .yaml or .yml, SKILL.md present             skill_path_invalid
at most 32 files, each at most 128 KiB, 256 KiB in all                   skill_too_large
no file contains a private key or an API key:
  "-----BEGIN … PRIVATE KEY-----", sk-…, sk-ant-…, ghp_…, github_pat_…,
  AKIA + 16, xox[abprs]-…, "0x" + 64 hex standing alone                  skill_contains_secret
```

A refused proof is not published, and the answer names the file and the check it failed.
