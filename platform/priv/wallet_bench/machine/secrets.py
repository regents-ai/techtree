"""The tested account's secrets, so the bench can blank them from the evidence before anything is stored.

Runs as root (sudo), because the tested account's files are owner-only. Reads every small file of the tested account,
in its home and /tmp, that looks like it holds a secret: its name says password, passphrase, key, keystore, seed,
recovery phrase, token, credential or wallet, or it sits in a wallet, keystore or key folder. Code and documentation
are never secret stores, however they are named. Prints one JSON object: {"files": [{"path": ..., "values": [...]}]},
where values are the file's whole text and each of its lines of 8 characters or more. Prints secrets to standard output
only; the bench holds them in memory while it blanks and never stores them.

Usage: sudo python3 secrets.py
"""
import json
import os
import re
from pathlib import Path

ROOTS = [Path("/home/bench"), Path("/tmp")]
# Installed software and the agents' own folders, as the storage check leaves out (bench/verify-storage.sh): a
# library's `secrets.py` or Hermes's own `secrets/command.md` holds code and docs, not secrets.
SKIP = re.compile(r"/(node_modules|\.cache|\.npm|_npx|versions|site-packages|dist-packages|\.local/share/uv|"
                  r"\.local/share/pnpm|go/pkg|\.claude|\.codex|\.grok|\.muse|\.hermes|\.kilo[^/]*|\.pi|\.omp|"
                  r"\.opencode|\.local/share/opencode|\.cline|\.deepseek[^/]*|\.ironclaw|\.config/[^/]*-agent)/")
# Code and documentation, such as a wallet tool's `SETUP-CREDENTIALS.md` or a test named `..._seed.py`.
CODE = re.compile(r"(?i)\.(md|mdx|rst|html?|py|js|mjs|cjs|ts|tsx|jsx|go|rs|rb|java|kt|swift|c|h|cpp|sh|bash|zsh|"
                  r"ex|exs|sol|lock)$")
SECRET_NAME = re.compile(r"(?i)(pass(word|phrase)?|secret|private|priv[_-]?key|mnemonic|seed|recovery|keystore|"
                         r"credential|token|\.env$|\.key$|\.pem$|wallet)")
# A folder of keys gives its files any names (Foundry's ~/.foundry/keystores/<name>). "token" is left out here: crypto
# documentation is full of folders named after tokens.
SECRET_FOLDER = re.compile(r"(?i)(pass(word|phrase)?|secret|private|priv[_-]?key|mnemonic|seed|recovery|keystore|"
                           r"credential|wallet|^keys?$)")
MAX_BYTES = 16384
BENCH_UID = Path("/home/bench").stat().st_uid


def candidates():
    for root in ROOTS:
        for folder, _dirs, files in os.walk(root):
            for name in files:
                path = Path(folder, name)
                folders = path.relative_to(root).parts[:-1]
                looks_secret = SECRET_NAME.search(name) or any(SECRET_FOLDER.search(part) for part in folders)
                if SKIP.search(str(path)) or CODE.search(name) or not looks_secret:
                    continue
                info = path.lstat()
                if path.is_file() and not path.is_symlink() and info.st_uid == BENCH_UID and info.st_size <= MAX_BYTES:
                    yield path


found = []
for path in candidates():
    text = path.read_bytes().decode("utf-8", errors="replace").strip()
    values = sorted({text, *(line.strip() for line in text.splitlines())} - {""}, key=len, reverse=True)
    values = [value for value in values if len(value) >= 8]
    if values:
        found.append({"path": str(path), "values": values})
print(json.dumps({"files": found}))
