"""Attach/remove the operator's W01 test key without printing it.

Run as root. The harness has not started its wallet turn yet. Keys arrive on
stdin; no Bankr login or network call is performed. Never replace a different
account. A root-only marker survives partial attachment so cleanup can retry.
"""
import json
import os
import pwd
import re
import stat
import sys
from pathlib import Path

FOLDER = Path("/home/bench/.bankr")
MARKER = Path("/work/bankr-access-supplied")


def folder_fd(create=False):
    bench = pwd.getpwnam("bench")
    if create and not FOLDER.exists():
        FOLDER.mkdir(mode=0o700)
        os.chown(FOLDER, bench.pw_uid, bench.pw_gid)
    fd = os.open(FOLDER, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != bench.pw_uid or stat.S_IMODE(info.st_mode) != 0o700:
        os.close(fd)
        raise ValueError("Bankr folder must be owner-only and owned by bench.")
    return fd, bench


def attach(key):
    if not re.fullmatch(r"bk_[A-Za-z0-9_-]{16,}", key):
        raise ValueError("Invalid Bankr key format.")
    directory, bench = folder_fd(create=True)
    try:
        try:
            existing = os.open("config.json", os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                               dir_fd=directory)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            with os.fdopen(existing) as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 16_384:
                    raise ValueError("Bankr config must be a small regular file.")
                record = json.load(file)
            if (not MARKER.is_file() or info.st_uid != bench.pw_uid
                    or stat.S_IMODE(info.st_mode) != 0o600 or record.get("apiKey") != key):
                raise ValueError("Refusing to replace existing Bankr access.")
            return
        if not MARKER.exists():
            marker = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(marker)
        config = os.open("config.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
        with os.fdopen(config, "w") as file:
            os.fchown(file.fileno(), bench.pw_uid, bench.pw_gid)
            json.dump({"apiKey": key, "apiUrl": "https://api.bankr.bot"}, file)
    finally:
        os.close(directory)


def revoke():
    if not MARKER.exists():
        return
    try:
        directory, _bench = folder_fd()
    except FileNotFoundError:
        directory = None
    if directory is not None:
        try:
            try:
                os.unlink("config.json", dir_fd=directory)
            except FileNotFoundError:
                pass
        finally:
            os.close(directory)
    MARKER.unlink()


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["attach"]:
            attach(sys.stdin.read().strip())
            print("attached")
        elif sys.argv[1:] == ["revoke"]:
            revoke()
            print("revoked")
        else:
            raise ValueError("Expected attach or revoke.")
    except Exception:
        # Library errors can include file contents; keep diagnostics generic.
        print("Bankr credential operation failed; no key was printed.", file=sys.stderr)
        sys.exit(1)
