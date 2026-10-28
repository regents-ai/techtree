# Model substitution Climb — contract

**Status:** draft. Techtree checks the model change (`Techtree.Network.Result.model_change/4`); nothing else here is implemented, released or approved to spend.
**Founder directive:** 28 Oct 2026, 14:15Z: reproducible comparisons of open models before and after one change, such as an OBLITERATUS abliteration, are a first research program in Techtree.

A model substitution Climb is a Skill Climb with one thing swapped: the same agent, tasks, tools, settings and limits, and only the model's weights changed. It keeps the Skill Climb's Campaign (`techtree.campaign.v4`), paired task outcomes, signed bundle and offline verify. This document fixes what every repository must agree on.

## 1. The mutation kind

```json
"mutation_contract": {
  "kind": "model_substitution",
  "target_agent": "subject",
  "allowed_differences": ["/agents/subject/model/weights"]
}
```

A `model_substitution` contract has exactly these three members; the Skill counts (`minimum_skills`, `maximum_skills`) belong to the two Skill kinds only. The Campaign describes the baseline, so its `agents.subject.model` is the model without the change, and its harness carries the Skills both runs share (none or more, the same on both sides).

## 2. The open-weights model block

For a `model_substitution` Campaign, `agents.subject.model` is exactly:

```json
{
  "weights": {
    "repo": "Qwen/Qwen3-8B",
    "revision": "b968826d9c46dd6066d109eabc6255188de91218",
    "weights_root": "sha256:<64 hex>"
  },
  "tokenizer_digest": "sha256:<64 hex>",
  "chat_template_digest": "sha256:<64 hex>",
  "serving": {
    "engine": "vllm",
    "version": "0.11.0",
    "dtype": "bfloat16",
    "quantization": null,
    "max_model_len": 32768
  },
  "derivation": null
}
```

| Field | Rule |
|---|---|
| `weights.repo` | Non-empty text, or `null` for weights that live only on the operator's machine. |
| `weights.revision` | A 40-character lowercase commit of `repo`, or `null`. A revision never comes without a repo. The baseline always names both. |
| `weights.weights_root` | Section 3. |
| `tokenizer_digest`, `chat_template_digest` | Section 3. Must be the same on both sides. |
| `serving` | `engine` is `vllm`; `version` and `dtype` non-empty text; `quantization` non-empty text or `null`; `max_model_len` a positive integer. Must be the same on both sides. |
| `derivation` | `null` on the baseline. On the candidate, `null` or the record below. |

The derivation record says how the candidate's weights were made. It is shown on the Result and not compared, except for what it says about the weights:

```json
{
  "tool": "obliteratus",
  "tool_commit": "<40 hex>",
  "source": {"repo": "Qwen/Qwen3-8B", "revision": "<40 hex>"},
  "method": "advanced",
  "method_config_digest": "sha256:<64 hex>",
  "seed": 42,
  "weights_root": "sha256:<64 hex>"
}
```

`source` is the baseline's `weights.repo` and `weights.revision`; `weights_root` is the candidate's own `weights.weights_root`; `seed` is an integer or `null`; `tool_commit` a 40-character lowercase commit.

## 3. Digests over model files

One function computes a root over a set of files, and every digest below uses it. Model Climb v1's `ModelArtifact` base weights root (`docs/spec/model-climb-v1.md`, 3.2) is `weights_root` of the base model's checkpoint, computed by the same function. It lives in regents-cli; Techtree never reads model files and only compares the declared digests.

**`file_root(directory, names)`**

1. Take the regular files directly in `directory` (not in subfolders) whose names are in `names`. Symbolic links are refused, with one exception: in a Hugging Face cache snapshot folder (`…/models--<org>--<name>/snapshots/<40 hex>`), a link is followed when it resolves, possibly through that repo's `blobs/` folder, to a regular file inside the same cache (the repo's `blobs/` or the cache-wide `hub/blobs/` store current huggingface_hub uses). Any other link is refused. The bytes hashed are the same either way.
2. For each, the entry `{"path": <file name>, "digest": "sha256:" + lowercase hex SHA-256 of its exact bytes}`.
3. Sort the entries by `path`, comparing UTF-8 bytes.
4. The root is `"sha256:"` + lowercase hex SHA-256 of the RFC 8785 bytes of that list (regents-cli `techtree/canonical.py`, the same encoder as every other Techtree digest).

An empty set is refused.

| Digest | `names` |
|---|---|
| `weights_root` | Every file whose name ends in `.safetensors`. `model.safetensors.index.json`, `config.json` and anything in a subfolder (a `repair_adapter/`, for example) are not weights. |
| `tokenizer_digest` | Those present of `tokenizer.json`, `tokenizer.model`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`. |

`chat_template_digest` is `"sha256:"` + lowercase hex SHA-256 of the template's bytes: `chat_template.jinja` when the checkpoint has one, otherwise the `chat_template` member of `tokenizer_config.json` (a string as its UTF-8 bytes; a list of named templates as its RFC 8785 bytes). A checkpoint with neither is refused.

Test vector: two files `model-00001-of-00002.safetensors` holding the 5 bytes `hello` and `model-00002-of-00002.safetensors` holding `world` give the list

```
[{"digest":"sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824","path":"model-00001-of-00002.safetensors"},{"digest":"sha256:486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7","path":"model-00002-of-00002.safetensors"}]
```

and the root `sha256:4e70f644497973aaaf7a6870ac92f125a87ad4a5017e714291de392629d5918a` (checked against both Techtree's and Python's encoders, 28 Oct 2026).

## 4. The comparison the CLI writes

The two runs' `configuration`s are compared leaf by leaf, as `diff_values` in regents-cli `techtree/manifests/compare.py` does for Skill Climbs. Every differing pointer must lie within `/agents/subject/model/weights`, or be `/agents/subject/model/derivation` itself (the baseline's `null` against the candidate's record). The report's `manifest_comparison` lists all of them, in pointer order, with `controlled: true`, no violations and `allowed_differences` as in section 1. Identical weights roots are a violation: the pair measures nothing.

The comparison status is `controlled`: the weights are pinned exactly, so the warning a hosted model gets for naming no build does not apply.

## 5. The `model_change` check

Beside `skill_change`, Techtree checks a `model_substitution` Result's two runs. It refuses with `submission_model_change_invalid`, naming the pointer where it can, unless every rule holds:

1. The Campaign's `mutation_contract` is exactly section 1.
2. The report's comparison is controlled, has no violations, allows exactly `/agents/subject/model/weights` and lists at least one difference.
3. Both runs' `agents.subject.model` are open-weights blocks written exactly as section 2.
4. The baseline's model is the Campaign's, member for member, and names its weights by repo and commit.
5. Techtree's own leaf-by-leaf comparison of the two configurations finds no difference outside the weights and the derivation record. A Skill, a tokenizer, a chat template, a serving setting, a sampling setting or a limit that differs is refused, whether or not the report admits it.
6. The two weights roots differ.
7. The baseline carries no derivation record; a candidate record names the candidate's own weights root and the baseline's repo and commit.
8. The report's list of differences is exactly the one Techtree worked out, so a difference the report leaves out, or one it invents, is refused.

What passes is the two runs' weights and the derivation record.

## 6. The OBLITERATUS adapter (regents-cli)

`regents techtree model import-obliteratus <checkpoint dir>` (name for the CLI lane to settle) turns an OBLITERATUS checkpoint into the candidate's model block, and the source model's snapshot into the baseline's. It reads files only: no OBLITERATUS code is imported, vendored or run by Techtree or regents-cli, which keeps both MIT and clear of OBLITERATUS's AGPL-3.0 terms. Shapes below are from OBLITERATUS `main` at 43b5d6d (28 Oct 2026).

**`abliteration_metadata.json`** comes in two shapes.

- The pipeline export (`abliterate.py`, `_build_metadata`): `source_model` (a Hub repo id, or a local path), `provenance.obliteratus_git_commit`, `provenance.obliteratus_git_dirty`, `provenance.obliteratus_version`, `provenance.source_model_revision`, `technique`, `method`, `method_config` (an object), `seed` (absent when unset), and `concept` with `id`, `version`, `pack_hash`, `validation_verdict` and, when one was exported, `repair_adapter: {path, merged, base, base_verified}`.
- The distributed checkpoint writer (`checkpoint_writer.py`): `{"schema_version": 2, "artifact_id", "checkpoint_provenance": "checkpoint-provenance.json", "conversion_manifest", "state_classification", "lost_state"}`. The facts are then in `checkpoint-provenance.json`.

**`checkpoint-provenance.json`** (`checkpoint_provenance.py`, `build_provenance`; `schema_id` `obliteratus.artifact-provenance`, `schema_version` `1.0.0`): `artifact_id`, `record_digest`, `obliteratus_commit`, `converter {name, version, commit}`, `base_model` and `sources[]` as `{kind: local|hub|generated, identity, revision, digest}`, `tokenizer` in the same shape, `lineage[]` with `event_type` (`surgery` for an abliteration), `output_digests`, `configuration_digest`.

**The derivation record it writes:** `tool` `obliteratus`; `tool_commit` from `provenance.obliteratus_git_commit` (or `obliteratus_commit`); `source` the baseline's repo and revision; `method`; `method_config_digest` the RFC 8785 digest of `method_config`; `seed` or `null`; `weights_root` computed (section 3) over the checkpoint.

**It refuses, one clear error each:**

- No OBLITERATUS commit, or `obliteratus_git_dirty` is not `false`.
- No `source_model_revision` (or no `base_model.revision` that is a 40-character commit), so the original cannot be named exactly. A `source_model` that is a local path is accepted only as a Hugging Face cache snapshot (`.../models--<org>--<name>/snapshots/<40 hex>`), which gives the repo and revision; any other path is refused, and no local path is ever written into a block.
- The checkpoint's tokenizer digest or chat template digest differs from the source snapshot's.
- `concept.repair_adapter` present with `merged` not `true`: the served weights would not be the hashed ones.
- A `checkpoint-provenance.json` whose `lineage` holds no `surgery` event, or whose `output_digests` do not include every `.safetensors` file's digest the adapter computed.

It never trusts a digest it did not compute: every digest in the block is computed from the files.

## 7. Open questions

- The pipeline export re-saves the tokenizer (`tokenizer.save_pretrained`), which may rewrite `tokenizer_config.json` byte for byte; the distributed writer copies source files unchanged. Whether a pipeline export ever passes the tokenizer rule is to be measured on a real checkpoint before the first run.
- `config.json` is in no digest. An abliteration that edits it (for example, removing a quantization block) changes the served model without changing `weights_root`.

## 8. The open_weights route

Settled by the regents-cli lane (regents-cli main 5e33684, `docs/model-substitution.md`, "The open_weights route"; `src/regents_cli/techtree/model_server.py`):

1. Each side has its own vLLM server, named by the base address of its OpenAI-compatible API (`http` or `https`, ending in `/v1`, no user, password, query or fragment).
2. Each side is served under its own `weights.weights_root` as the served model name, so the traces record which weights answered and the sides cannot be swapped unnoticed.
3. Before a run, `GET <base>/models` must list that name with `max_model_len` equal to the block's `serving.max_model_len`, and `GET <server>/version` must answer `serving.version`; otherwise `model_server_mismatch` (unreachable or key missing: `model_server_unreachable`; bad address: `model_server_url_invalid`, never repeated).
4. A key comes from `VLLM_API_KEY` and is never written to an answer, input or log.
5. The addresses belong to the run, not the Campaign or the proof bundle; the bundle holds each side's model block.
6. dtype, quantization and the bytes loaded stay the operator's statement; an independent rerun checks it.

## 9. Operating notes from the CPU rehearsal (28 Oct 2026)

- Run OBLITERATUS from a git checkout at a clean commit, so its export records the commit and `dirty: false`; an install from git without a `.git` folder records `null`, which the import refuses.
- OBLITERATUS's pipeline export re-saves the tokenizer under transformers 5 (different bytes, identical behaviour). Before importing, copy the source snapshot's tokenizer files back into the export; the tokenizer rule is unchanged.
- Export in the dtype the block serves (`--dtype bfloat16` for a bfloat16 model), so the served weights are the digested ones.
