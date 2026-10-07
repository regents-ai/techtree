"""The tested account's secrets, so the bench can blank them from the evidence before anything is stored.

Runs as root (sudo), because the tested account's files are owner-only. Reads every small file of the tested account,
in its home and /tmp, whose path looks like it holds a secret (a password, passphrase, key, keystore, seed, recovery
phrase, token or credential), and prints one JSON object: {"files": [{"path": ..., "values": [...]}]}, where values
are the file's whole text and each of its lines of 8 characters or more. Prints secrets to standard output only; the
bench holds them in memory while it blanks and never stores them.

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
SECRET = re.compile(r"(?i)(pass(word|phrase)?|secret|private|priv[_-]?key|mnemonic|seed|recovery|keystore|"
                    r"credential|token|\.env$|\.key$|\.pem$|wallet)")
MAX_BYTES = 16384
BENCH_UID = Path("/home/bench").stat().st_uid


def candidates():
    for root in ROOTS:
        for folder, _dirs, files in os.walk(root):
            for name in files:
                path = Path(folder, name)
                if SKIP.search(str(path)) or not SECRET.search(str(path.relative_to(root))):
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
