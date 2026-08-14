# Uninstalling Techtree, and what stays behind

Uninstalling the Techtree package does not delete your Techtree data. That is
deliberate — a run's evidence and the key that signed it are yours, and a
package manager removing a package is not you asking for your evidence to be
destroyed — but it is only honest if the leftovers are named. This page names
them, and gives the commands that remove each one.

The headline: **your private signing key survives an uninstall.** It is one
file, it is not recoverable once deleted, and every proof you have already
produced was signed with it.

## The retention promise

Techtree keeps everything it produces on the machine that produced it. It does
not upload your Episodes, Traces, receipts, proof bundles, or Skill proposals,
and it has no code path that could: the CLI never writes to the network except
to install the evaluation engine and to fetch the starter Skill. Model
inference is the exception, and it is not a small one — running a comparison
sends prompts and completions to the model provider whose credentials you
configured, under that provider's policies and retention, which Techtree
neither sets nor can delete on your behalf.

So there are two different questions with two different answers. *What has
Techtree kept?* Everything below, all of it local, all of it removable with
`rm`. *What has your model provider kept?* Whatever their policy says; ask
them, not us.

Removing local data does not invalidate anything you have already shared. A
proof bundle you copied elsewhere still verifies from its own bytes.

## Upgrading, and runs made by an older version

Upgrading the package does not touch anything a run has already written. It
also does not go back and rewrite those files to suit the new version, and that
is on purpose: a finished run is a record of what actually happened, and
editing it afterwards would make it a record of something else.

One consequence is worth stating plainly. A run recorded by an earlier version
of Techtree may be one a newer version cannot open. `techtree run status`,
`techtree run result`, and `techtree uplift context` will tell you so and stop
there. Nothing has been lost and nothing is damaged — the run's files are
exactly the bytes that were written — and the part that matters most still
works from those same bytes:

```bash
techtree proof verify <run-id>
```

That check is self-contained. It reads the run's own proof bundle, needs no
network and no Techtree account, and is unaffected by which version of Techtree
is installed now.

## What `uv tool uninstall techtree` removes

```bash
uv tool uninstall techtree
```

That removes the package and its two executables — `techtree` and
`techtree-worker` — and the isolated environment uv built for them. It removes
nothing else. In particular it does not touch the Techtree home, the evaluation
engine inside it, uv's own caches, or the container image.

## What stays, and exactly where

### 1. The Techtree home — including your private signing key

One directory holds all local state. Its default location is the
platform's user-data directory for an application named `techtree`:

```text
macOS    ~/Library/Application Support/techtree
Linux    ~/.local/share/techtree
Windows  %LOCALAPPDATA%\techtree
```

If you passed `--home PATH` when running commands, your state is under that
path instead. `--home` is the only thing that moves it; there is no
environment variable a user sets to relocate it.

```text
<techtree-home>/
├── config.toml                          local preferences, active engine
├── identities/
│   ├── executor-private-key.bin         ← YOUR PRIVATE Ed25519 SIGNING KEY
│   └── executor-public.json             the public half, safe to share
├── runs/<run-id>/                       everything one comparison produced
│   ├── inputs/                          the run's own copies of what it ran
│   ├── verifiers/                       raw engine output, including
│   │                                    traces.jsonl — your subject transcripts
│   ├── taskset/                         the taskset lock and validator output
│   └── proof/                           the signed, portable proof bundle
├── drafts/<draft-id>/                   prepared but unstarted submissions
├── cache/skills/<sha256-...>/           Skills Techtree fetched and verified
└── engines/<sha256-...>/                the evaluation engine, with its .venv
```

`identities/executor-private-key.bin` is the file to think hardest about. It is
the private half of the Ed25519 key this machine generated, it is what signs
your receipts and reports, and it is written `0600` and never copied anywhere
by Techtree. Deleting it is irreversible: there is no escrow, no backup, and no
recovery. A new key is generated the next time one is needed, and proofs signed
by the old key remain verifiable by anyone holding the matching
`executor-public.json` — but you cannot sign as that identity again.

`engines/` is usually the largest thing here by a wide margin: it contains a
full Python environment for the evaluation engine.

### 2. uv's caches, outside the Techtree home

Installing the engine downloads wheels through uv, which caches them in uv's
own cache directory, and may install a Python interpreter that uv manages.
Neither is Techtree's to place and neither is removed with the package:

```bash
uv cache dir          # prints the cache location
uv cache clean        # empties it — shared with your other uv projects
```

uv-managed interpreters live under uv's own data directory
(`~/.local/share/uv/python` on Linux and macOS) and are listed and removed with
`uv python list` and `uv python uninstall`.

Both are shared with everything else you use uv for, so clearing them affects
more than Techtree. That is why Techtree does not clear them for you.

### 3. The container image

Evaluation runs the subject inside a pinned container. Techtree never pulls
that image and never deletes it — it checks that your Docker daemon already
holds it and refuses to run if it does not — so if it is on your machine, you
or your daemon put it there, and removing it is a Docker operation:

```bash
docker image rm python@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff
```

## Removing everything

There is no `techtree uninstall` and no purge command. Removing local state is
a filesystem operation you run yourself, deliberately, because every command
below destroys evidence that cannot be recreated.

Look before you delete:

```bash
ls -la "$HOME/Library/Application Support/techtree"     # macOS
ls -la "$HOME/.local/share/techtree"                    # Linux
```

Then, in the order that goes from safest to least reversible:

```bash
# 1. The evaluation engine only. Frees the most space; re-installable with
#    `techtree setup`. Keeps every run, proof, and your key.
rm -rf "$HOME/.local/share/techtree/engines"

# 2. Runs and drafts. Deletes your comparisons, transcripts, and proof
#    bundles. Copy out anything you want to keep first.
rm -rf "$HOME/.local/share/techtree/runs" "$HOME/.local/share/techtree/drafts"

# 3. Everything, including the private signing key. Irreversible.
rm -rf "$HOME/.local/share/techtree"

# 4. The package itself.
uv tool uninstall techtree
```

On macOS substitute `$HOME/Library/Application Support/techtree` for
`$HOME/.local/share/techtree` in each command, and if you used `--home`,
substitute the path you gave it.

Then, if you also want the shared artifacts back: `uv cache clean` and the
`docker image rm` above.

## What this page cannot promise

Two things are outside what any command here reaches, and are stated rather
than implied.

Techtree cannot reach into your model provider. Prompts and completions sent
during a run are subject to that provider's retention policy, and deleting your
Techtree home does not delete them.

Techtree cannot find copies you made. A proof bundle is designed to be portable
and to verify away from the machine that made it; if you have sent one
somewhere, removing your local state does not recall it.
