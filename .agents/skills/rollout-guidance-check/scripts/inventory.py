#!/usr/bin/env python3
"""Inventory guidance surfaces without executing repository code or printing copy.

Reads fixed Git revisions and optional working changes. File coverage is exhaustive
within the recorded roots; line-level signals are candidates, not semantic proof.
Only the explicitly selected output directory is written.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import html
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

SKIP_PARTS = {".git", "node_modules", "deps", "_build", ".venv", "venv", "__pycache__",
              ".next", "build", "dist", "coverage", "cache", ".cache"}
PRIVATE_PARTS = {".siwa", ".ssh", ".aws", ".gnupg", "credentials", "wallets",
                 "secrets", ".secrets", ".credentials", ".docker", ".kube", ".azure"}
PRIVATE_NAMES = {".npmrc", ".pypirc", ".netrc", "_netrc", ".git-credentials",
                 ".dockercfg", ".authinfo", "auth.json", "auth.toml", "auth.yaml",
                 "auth.yml", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                 "settings.json", "wallet.json", "service-account.json"}
PRIVATE_NAME_PATTERN = re.compile(
    r"(?:^|[._-])(?:credentials?|secrets?|private[-_]?keys?|access[-_]?tokens?|keystore)(?:[._-]|$)", re.I)
KEY_EXTENSIONS = {".pem", ".key", ".p8", ".p12", ".pfx", ".ppk", ".keystore"}
BINARY = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2",
          ".ttf", ".mp4", ".mov", ".mp3", ".wav", ".zip", ".gz", ".pdf", ".beam",
          ".sqlite", ".db", ".pem", ".key", ".p8", ".p12", ".pfx", ".keystore", ".lock", ".map"}
SOURCE = {".ex", ".exs", ".heex", ".eex", ".leex", ".html", ".tsx", ".jsx",
          ".ts", ".js", ".mjs", ".cjs", ".py", ".swift", ".rs", ".go", ".sol",
          ".sh", ".bash", ".zsh", ".css", ".scss", ".svelte", ".vue"}
PROSE = {".md", ".mdx", ".rst", ".adoc", ".txt", ".strings", ".stringsdict",
         ".xcstrings", ".po", ".pot"}
PATTERNS = {
    "tooltip_accessibility_help": re.compile(r"tooltip|aria[-_]label|aria-describedby|\btitle\s*[=:]|\bplaceholder\s*[=:]|accessibilityLabel|\.help\(", re.I),
    "tool_schema_description": re.compile(r"input[_S]chema|output[_S]chema|modelContext|registerTool|\bdescription\s*[:=]|operationId|readOnlyHint|pairing_required", re.I),
    "cli_help_example": re.compile(r"\bregents(?:-cli)?\b|--help|add_argument\(|@click\.|typer\.(?:Option|Argument)|\bhelp\s*=|argparse|epilog", re.I),
    "error_recovery_copy": re.compile(r"\b(?:hint|next_steps|put_flash|add_error|error_message|refusal)\b|gettext\(|validation.*message", re.I),
    "handoff_prompt": re.compile(r"pairing.message|copy.{0,20}(?:agent|command|prompt)|send.{0,15}your.agent|system_prompt|system_message|instructions\s*[:=]", re.I),
    "inline_developer_docs": re.compile(r"@moduledoc|@doc\b|^\s*///|^\s*/\*\*|^\s*(?:\"\"\"|''')|@notice|@dev\b"),
    "route_generator_binding": re.compile(r"/agents\.md|/skill\.md|/llms\.txt|/capabilities|sync_api_contract|regent_ui\.assets|usage_rules\.sync|external_resource|File\.read!", re.I),
    "release_auth_gate": re.compile(r"approved_rules|starts_at|unified_activity_starts_at|agent_grants_enabled|release_status|minimum.*version|cli_release|prelaunch", re.I),
}


def git(repo: Path, *args: str, check: bool = True) -> bytes:
    return subprocess.run(["git", "--no-replace-objects", "-c", "core.fsmonitor=false", "-C", str(repo), *args], check=check,
                          env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout


def exclusion(path: str) -> str | None:
    p = Path(path)
    if any(part.lower().startswith(".env") and part.lower() != ".env.example" for part in p.parts):
        return "settings_never_read"
    if any(part.lower() in PRIVATE_PARTS for part in p.parts) or p.name == "launch.json":
        return "private_runtime_never_read"
    if KEY_EXTENSIONS.intersection(s.lower() for s in p.suffixes):
        return "private_key_never_read"
    private_data_name = p.suffix.lower() not in SOURCE | (PROSE - {".txt"}) and PRIVATE_NAME_PATTERN.search(p.name)
    if any(p.name.lower() == name or p.name.lower().startswith(name + ".") for name in PRIVATE_NAMES) or private_data_name:
        return "credential_filename_never_read"
    if any(part in SKIP_PARTS for part in p.parts):
        return "dependency_or_build_output"
    if p.suffix.lower() in BINARY or p.name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "mix.lock", "uv.lock", "Cargo.lock"}:
        return "binary_lock_or_source_map"
    if p.suffix.lower() in {".log", ".jsonl"}:
        return "runtime_log_or_transcript"
    # First-party generated vendor assets are included; third-party vendoring is not.
    if "vendor" in p.parts and not any(part.startswith("regent_") for part in p.parts):
        return "third_party_vendor"
    if any(x in path for x in ("contracts/lib/", "lib/forge-std/", "lib/openzeppelin-", "lib/solady/")):
        return "third_party_vendor"
    return None


def classify(path: str, text: str) -> tuple[list[str], dict[str, list[int]], str]:
    p = Path(path)
    low = path.lower()
    tags = set()
    if p.suffix.lower() in PROSE or p.name.lower().startswith(("readme", "changelog")):
        tags.add("authored_document")
    if p.name in {"AGENTS.md", "CLAUDE.md"} or "usage-rules" in low:
        tags.add("developer_agent_instructions")
    if "/skills/" in "/" + low or p.name == "SKILL.md":
        tags.add("skill_or_skill_resource")
    if any(x in low for x in ("priv/public/", "priv/legal/", "priv/static/skill", "public/docs")):
        tags.add("public_product_document")
    if "openapi" in low or "api-contract" in low or p.name in {"tools.json", "commands.json", "tool_manifest.json", "capabilities.json"}:
        tags.add("machine_contract")
    if "/cli/" in "/" + low or "regents_cli/" in low or p.name == "COMMANDS.md":
        tags.add("cli_source_or_description")
    if any(x in low for x in ("_web/", "/components/", "/live/", "assets/js/", "assets/css/", "/views/")) or p.suffix in {".swift", ".heex", ".eex", ".tsx", ".jsx", ".strings", ".xcstrings"}:
        tags.add("human_ui_source")
    if any(x in low for x in ("webmcp", "public_tools", "capabilit", "mcp_server", "tool_definitions", "tool_manifest")):
        tags.add("agent_tool_surface")
    if "prompt" in low or "pairing_message" in low or "agent_start" in low:
        tags.add("handoff_prompt")
    if "/test" in "/" + low or "/spec/" in "/" + low or p.name.endswith((".test.ts", ".spec.ts")):
        tags.add("test_or_fixture")
    if any(x in low for x in ("/handoff", "/archive", "/evidence", "/audit", "changelog", "/release-notes")):
        tags.add("historical_or_review_record")
    generated = any(x in low for x in ("assets/vendor/regent_", "src/regents_cli/platforms/",
                                      "priv/static/openapi", "priv/static/api-contract"))
    if generated:
        tags.add("generated_or_copied_surface")
    hits: dict[str, list[int]] = {}
    for num, line in enumerate(text.splitlines(), 1):
        for tag, pattern in PATTERNS.items():
            if pattern.search(line):
                hits.setdefault(tag, []).append(num)
                tags.add(tag)
    if p.suffix in SOURCE:
        tags.add("code_candidate")
    if not tags:
        tags.add("unclassified_text_review_required")
    role = "generated_or_copy" if generated else "source_or_reference"
    if "test_or_fixture" in tags:
        role = "test_evidence"
    return sorted(tags), hits, role


def record(repo_name: str, repo: Path, path: str, version: str, data: bytes, rows: list, max_size: int):
    base = {"repo": repo_name, "root": str(repo), "path": path, "version": version,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if len(data) > max_size:
        rows.append(base | {"status": "oversize_not_classified", "categories": ["manual_review_required"]})
        return
    if b"\0" in data:
        rows.append(base | {"status": "binary_not_classified", "categories": []})
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        rows.append(base | {"status": "non_utf8_not_classified", "categories": ["manual_review_required"]})
        return
    tags, hits, role = classify(path, text)
    rows.append(base | {"status": "inventoried", "categories": tags, "role": role,
                        "lines": len(text.splitlines()), "signal_lines": hits})


def scan_repo(name: str, repo: Path, requested_ref: str, overlay: bool, rows: list, max_size: int, allow_fallback: bool = False) -> dict:
    ref = git(repo, "rev-parse", "--verify", requested_ref + "^{commit}", check=False).decode().strip()
    fallback = False
    if not ref:
        if not allow_fallback:
            raise ValueError(f"Requested revision unavailable in {repo}: {requested_ref}; no substitute scanned")
        ref = git(repo, "rev-parse", "--verify", "HEAD^{commit}", check=False).decode().strip()
        fallback = True
        if not ref:
            rows.append({"repo": name, "root": str(repo), "path": ".", "version": "unavailable",
                         "status": "repository_has_no_commit", "categories": []})
            if overlay:
                loose_docs(name, repo, rows, max_size)
            return {"name": name, "root": str(repo), "requested_ref": requested_ref,
                    "ref": None, "checkout_HEAD": None, "fell_back_to_HEAD": True,
                    "unavailable_reason": "repository_has_no_commit", "checkout_changed_during_scan": False}
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    # --long records size; paths may contain whitespace, so split only the header.
    entries = git(repo, "ls-tree", "-r", "-z", "-l", ref).split(b"\0")
    wanted = []
    for entry in entries:
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, kind, oid, size = meta.split()
        path = raw_path.decode("utf-8", "surrogateescape")
        reason = exclusion(path)
        if mode in {b"120000", b"160000"}:
            reason = "symlink_not_followed" if mode == b"120000" else "submodule_not_traversed"
        if reason or int(size) > max_size:
            rows.append({"repo": name, "root": str(repo), "path": path, "version": ref,
                         "status": reason or "oversize_not_classified", "categories": []})
        else:
            wanted.append((path, oid, mode.decode()))
    # Only approved blobs enter cat-file: excluded settings and key files are never opened.
    for offset in range(0, len(wanted), 8):
        group = wanted[offset:offset + 8]
        payload = b"\n".join(oid for _, oid, _ in group) + b"\n"
        batch = subprocess.run(["git", "--no-replace-objects", "-c", "core.fsmonitor=false", "-C", str(repo), "cat-file", "--batch"], input=payload,
                               env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
        pos = 0
        for path, _, mode in group:
            end = batch.index(b"\n", pos)
            header = batch[pos:end].split()
            size = int(header[-1]); start = end + 1
            record(name, repo, path, ref, batch[start:start + size], rows, max_size)
            rows[-1]["git_mode"] = mode
            pos = start + size + 1
    changes = []
    head_difference = [p.decode("utf-8", "surrogateescape") for p in
                       git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--name-only", "-z", ref, head).split(b"\0") if p]
    if overlay:
        # Compare raw files with recorded blobs; a worktree diff may execute clean filters.
        snapshot = {row["path"]: row for row in rows
                    if row["root"] == str(repo) and row["version"] == ref}
        index = {}
        for entry in git(repo, "ls-files", "--stage", "-t", "-z").split(b"\0"):
            if entry:
                meta, raw = entry.split(b"\t", 1)
                index[raw] = meta.split()
        paths = {p.encode("utf-8", "surrogateescape") for p in snapshot}
        paths |= set(index)
        paths |= set(git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"))
        ignored = git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
        ignored_paths = {p.decode("utf-8", "surrogateescape").rstrip("/") for p in ignored.split(b"\0") if p}
        for raw in sorted(paths):
            if not raw:
                continue
            path = raw.decode("utf-8", "surrogateescape"); p = repo / path
            current = []
            reason = exclusion(path)
            if any(str(parent) in ignored_paths for parent in (Path(path), *Path(path).parents)):
                reason = reason or "ignored_untracked_not_read"
            entry = index.get(raw)
            if entry and entry[1] == b"160000":
                reason = "submodule_not_traversed"
            elif entry and entry[1] == b"120000":
                reason = "symlink_not_followed"
            elif entry and entry[0] == b"S" and not p.exists():
                reason = reason or "sparse_not_materialized"
            if linked_path(p, repo):
                reason = "symlink_not_followed"
            if reason or not p.is_file():
                current.append({"repo": name, "root": str(repo), "path": path, "version": "working_overlay",
                             "status": reason or "deleted_or_missing", "categories": []})
            elif not p.resolve().is_relative_to(repo.resolve()):
                current.append({"repo": name, "root": str(repo), "path": path, "version": "working_overlay",
                             "status": "external_symlink_parent_not_followed", "categories": []})
            elif p.stat().st_size > max_size:
                current.append({"repo": name, "root": str(repo), "path": path, "version": "working_overlay",
                             "status": "oversize_not_classified", "categories": []})
            else:
                record(name, repo, path, "working_overlay", p.read_bytes(), current, max_size)
                current[0]["git_mode"] = "100755" if p.stat().st_mode & 0o111 else "100644"
            previous = snapshot.get(path)
            # Without content evidence, equality is unknown: retain the current boundary.
            if not previous or "sha256" not in current[0] or any(previous.get(key) != current[0].get(key) for key in ("sha256", "status", "git_mode")):
                rows.extend(current)
                changes.append(path)
        staged = git(repo, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--no-renames", "--name-only", "-z", head)
        for raw in staged.split(b"\0"):
            if raw:
                path = raw.decode("utf-8", "surrogateescape")
                rows.append({"repo": name, "root": str(repo), "path": path, "version": "index_overlay",
                             "status": exclusion(path) or "staged_difference_not_read", "categories": []})
        for raw in ignored.split(b"\0"):
            if raw:
                path = raw.decode("utf-8", "surrogateescape")
                rows.append({"repo": name, "root": str(repo), "path": path, "version": "working_overlay",
                             "status": exclusion(path) or "ignored_untracked_not_read", "categories": []})
    return {"name": name, "root": str(repo), "requested_ref": requested_ref, "ref": ref,
            "fell_back_to_HEAD": fallback, "checkout_HEAD": head, "overlay_paths": len(changes),
            "checkout_paths_differing_from_ref": head_difference,
            "checkout_difference_disposition": "working_overlay_included" if overlay else "outside_requested_snapshot",
            "checkout_changed_during_scan": head != git(repo, "rev-parse", "HEAD").decode().strip()}


def linked_path(path: Path, root: Path) -> bool:
    """Reject links at every level before stat/read can follow a parent link."""
    return any(p.is_symlink() for p in (path, *path.parents)
               if p == root or p.is_relative_to(root))


def ignored_paths(root: Path) -> set[str]:
    top = git(root, "rev-parse", "--show-toplevel", check=False)
    if not top:
        return set()
    top = Path(os.fsdecode(top).removesuffix("\n"))
    ignored = set()
    for raw in git(top, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z").split(b"\0"):
        if raw:
            path = top / os.fsdecode(raw).rstrip("/")
            if path.is_relative_to(root):
                ignored.add(str(path.relative_to(root)))
            elif root.is_relative_to(path):
                ignored.add(".")
    return ignored


def is_ignored(path: str, ignored: set[str]) -> bool:
    return any(str(parent) in ignored for parent in (Path(path), *Path(path).parents))


def document_paths(root: Path, ignored: set[str] | None = None) -> list[Path]:
    # os.walk records links themselves without traversing them or applying ignore rules.
    def fail(error):
        raise error
    paths = []
    for directory, folders, files in os.walk(root, followlinks=False, onerror=fail):
        parent = Path(directory)
        for folder in folders[:]:
            path = parent / folder
            relative = str(path.relative_to(root))
            if path.is_symlink() or exclusion(relative) or is_ignored(relative, ignored or set()):
                paths.append(path)
                folders.remove(folder)
        paths.extend(parent / name for name in files)
    return sorted(paths)


def loose_docs(name: str, root: Path, rows: list, max_size: int, direct_only: bool = False):
    ignored = ignored_paths(root)
    if direct_only:
        names = [str(p) for p in root.iterdir() if p.is_symlink() or p.is_file()]
    else:
        names = document_paths(root, ignored)
    for name_path in names:
        p = Path(name_path); rel = str(p.relative_to(root))
        reason = exclusion(rel)
        if is_ignored(rel, ignored):
            reason = reason or "ignored_untracked_not_read"
        if linked_path(p, root) or not p.resolve().is_relative_to(root.resolve()):
            reason = "symlink_not_followed"
        if reason or not p.is_file() or p.stat().st_size > max_size:
            rows.append({"repo": name, "root": str(root), "path": rel, "version": "working",
                         "status": reason or "oversize_not_classified", "categories": []})
        else:
            record(name, root, rel, "working", p.read_bytes(), rows, max_size)


def workspace_docs(root: Path, rows: list, max_size: int):
    # Deliberately exclude artifacts/backups, settings and session stores.
    wanted = [root / "AGENTS.md", root / "CLAUDE.md"]
    ignored = ignored_paths(root)
    for folder in ("docs", "agent-docs"):
        p = root / folder
        if linked_path(p, root):
            rows.append({"repo": "workspace", "root": str(root), "path": folder,
                         "version": "working", "status": "symlink_not_followed", "categories": []})
        elif is_ignored(folder, ignored):
            wanted.append(p)
        elif p.is_dir():
            wanted.extend(document_paths(p, ignored_paths(p)))
    for p in sorted(set(wanted)):
        rel = str(p.relative_to(root)); reason = exclusion(rel)
        if is_ignored(rel, ignored):
            reason = reason or "ignored_untracked_not_read"
        if linked_path(p, root) or not p.resolve().is_relative_to(root.resolve()):
            reason = "symlink_not_followed"
        if not reason and not p.is_file():
            continue
        if reason or p.stat().st_size > max_size:
            rows.append({"repo": "workspace", "root": str(root), "path": rel, "version": "working",
                         "status": reason or "oversize_not_classified", "categories": []})
        else:
            record("workspace", root, rel, "working", p.read_bytes(), rows, max_size)
    for directory in (".agents/skills", ".claude/skills"):
        aliases = root / directory
        if linked_path(aliases, root):
            rows.append({"repo": "workspace", "root": str(root), "path": directory,
                         "version": "working", "status": "skill_alias_not_followed", "categories": ["skill_alias"]})
        elif aliases.is_dir():
            loose_docs("workspace", aliases, rows, max_size)


def reject_links(path: Path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"Refusing symlink in path: {path}")


def md_code(value):
    """Render arbitrary path bytes as data, never report markup."""
    text = html.escape(json.dumps(str(value), ensure_ascii=True))
    for character in "`|[]*_":
        text = text.replace(character, f"&#{ord(character)};")
    return "<code>" + text + "</code>"


def csv_cell(value):
    text = str(value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New or empty directory outside scanned sources")
    parser.add_argument("--ref", help="Exact revision; unavailable explicit revisions fail without substituting HEAD")
    parser.add_argument("--repo", type=Path, action="append", help="Restrict to these checkouts; repeatable")
    parser.add_argument("--no-working-overlay", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=4_000_000)
    args = parser.parse_args()
    requested_ref = args.ref or "origin/main"
    allow_fallback = args.ref is None
    reject_links(args.workspace.absolute())
    root = args.workspace.resolve()
    if not root.is_dir():
        raise ValueError(f"Workspace must be an existing directory: {root}")
    reject_links(args.output.absolute())
    output = args.output.resolve()
    rows = []; sources = []; nonrepos = []; loose_roots = []; unavailable = []
    paths = args.repo or []
    for repo in paths:
        reject_links(repo.absolute())
    if not args.repo:
        surface_map = Path(__file__).resolve().parents[1] / "references/surface-map.md"
        expected = sorted(set(re.findall(r"\b(?:repos|services)/[a-z0-9-]+", surface_map.read_text())))
        for relative in expected:
            path = root / relative
            if linked_path(path, root) or not path.is_dir():
                unavailable.append(relative)
                rows.append({"repo": "workspace", "root": str(root), "path": relative,
                             "version": "working", "status": "known_source_root_unavailable", "categories": []})
        for container in (root / "repos", root / "services"):
            if container.is_symlink():
                rows.append({"repo": "workspace", "root": str(root), "path": str(container.relative_to(root)),
                             "version": "working", "status": "symlink_not_followed", "categories": []})
            elif container.is_dir():
                loose_docs("workspace", container, rows, args.max_bytes, direct_only=True)
                for path in sorted(container.iterdir()):
                    if path.is_symlink() or not path.is_dir():
                        continue  # Direct files and links were recorded above.
                    reason = exclusion(path.name)
                    if reason:
                        rows.append({"repo": "workspace", "root": str(root), "path": str(path.relative_to(root)),
                                     "version": "working", "status": reason, "categories": []})
                    elif path.is_dir():
                        paths.append(path)
    scanned_roots = [p.resolve() for p in paths]
    if not args.repo:
        scanned_roots.extend(root / p for p in ("repos", "services", "docs", "agent-docs", ".agents/skills", ".claude/skills"))
    if any(output.is_relative_to(p) for p in scanned_roots):
        raise ValueError("--output must be outside scanned source directories")
    for repo in paths:
        repo = repo.resolve()
        top = os.fsdecode(git(repo, "rev-parse", "--show-toplevel", check=False)).removesuffix("\n")
        if not top or Path(top).resolve() != repo:
            if args.repo:
                raise ValueError(f"Explicit --repo must name a Git repository root: {repo}")
            # One extra directory level accommodates grouped repositories such as video-creation.
            if not args.repo:
                loose_docs(repo.name, repo, rows, args.max_bytes, direct_only=True)
                for child in sorted(repo.iterdir()):
                    if not child.is_dir() or child.is_symlink():
                        continue
                    reason = exclusion(child.name)
                    if reason:
                        rows.append({"repo": repo.name, "root": str(repo), "path": child.name,
                                     "version": "working", "status": reason, "categories": []})
                        continue
                    child_top = os.fsdecode(git(child, "rev-parse", "--show-toplevel", check=False)).removesuffix("\n")
                    if child_top and Path(child_top).resolve() == child:
                        sources.append(scan_repo(child.name, child, requested_ref, not args.no_working_overlay, rows, args.max_bytes, allow_fallback))
                    else:
                        loose_docs(child.name, child, rows, args.max_bytes)
                        loose_roots.append(str(child))
                nonrepos.append(str(repo))
            continue
        sources.append(scan_repo(repo.name, repo, requested_ref, not args.no_working_overlay, rows, args.max_bytes, allow_fallback))
    if not args.repo:
        workspace_docs(root, rows, args.max_bytes)
    names = sorted({r["repo"] for r in rows})
    outputs = [output / f for f in ("locations.jsonl", "locations.csv", "coverage.json", "INDEX.md")]
    outputs += [output / "repositories" / (name + ".md") for name in names]
    for path in outputs:
        reject_links(path)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("--output must be new or empty; use a fresh directory for each inventory")
    with (output / "locations.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=True) + "\n")
    with (output / "locations.csv").open("x", newline="", encoding="utf-8", errors="backslashreplace") as stream:
        writer = csv.writer(stream)
        writer.writerow(["repository", "root", "path", "revision", "status", "categories", "signal_lines"])
        for row in rows:
            writer.writerow([csv_cell(cell) for cell in [row["repo"], row["root"], row["path"], row["version"], row["status"],
                             "; ".join(row["categories"]), json.dumps(row.get("signal_lines", {}))]])
    counts = collections.Counter(row["status"] for row in rows)
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": sources,
               "unavailable_source_roots_from_surface_map": unavailable,
               "grouping_directories_children_scanned": nonrepos, "loose_roots_scanned": loose_roots,
               "counts": dict(counts),
               "limits": ["Line signals are heuristic; all other text stays in the inventory for review.",
                          "CSV formula-leading cells are prefixed with an apostrophe; JSONL retains exact path values.",
                          "Remote refs are local snapshots, not fetched or live release claims.",
                          "Old worktrees, dependency copies, artifacts/backups and database-authored content are outside this source inventory.",
                          "Working overlays are not part of the recorded commit; they may be based on an older HEAD.",
                          "Overlay paths include current unverified boundaries, even when their content could not be compared; they are not an exact changed-file count.",
                          "Staged differences from HEAD are listed as index_overlay boundaries; index content is not read.",
                          "Git-ignored untracked paths are recorded without content reads. Non-Git loose roots bypass text-search ignore files; excluded directory trees may have one boundary row.",
                          "Known private filenames and key extensions are excluded before content reads; this is not secret detection for arbitrarily named files.",
                          "External symlink targets are not read; ordinary source configuration remains in scope."]}
    (output / "coverage.json").write_text(json.dumps(summary, indent=2) + "\n")
    index = ["# Guidance surface inventory", "", "Every enumerated path is in locations.csv and locations.jsonl.",
             "Coverage and fixed revisions are in coverage.json. Counts include committed sources and working overlays separately.",
             "", "| Repository | Inventoried text files | Other paths recorded |", "|---|---:|---:|"]
    pages = output / "repositories"
    pages.mkdir(exist_ok=True)
    for name in names:
        matching = [r for r in rows if r["repo"] == name]
        inventoried = sum(r["status"] == "inventoried" for r in matching)
        page = pages / (name + ".md")
        index.append(f"| {md_code(name)} [report]({quote(str(page.relative_to(output)))}) | {inventoried} | {len(matching) - inventoried} |")
        detail = [f"# {md_code(name)}: every enumerated guidance location", "",
                  "These are file-level candidates and coverage records, not proof that all copy was semantically checked.",
                  "Revision/working-overlay is explicit; the current file on disk may differ from the named commit.", ""]
        for row in sorted(matching, key=lambda r: (r["path"], r["version"])):
            categories = ", ".join(row["categories"]) or row["status"]
            detail.append(f"- {md_code(row['root'] + '/' + row['path'])} — {md_code(row['version'])}; {categories}")
        page.write_text("\n".join(detail) + "\n", encoding="utf-8", errors="backslashreplace")
    index += ["", "## Categories", "", "| Category | Files |", "|---|---:|"]
    for tag, count in sorted(collections.Counter(t for r in rows for t in r["categories"]).items()):
        index.append(f"| {tag} | {count} |")
    index += ["", "## Limits", ""] + ["- " + s for s in summary["limits"]]
    if nonrepos:
        index += ["", "Grouping directories: nested repositories and loose child folders inventoried:"] + ["- " + md_code(p) for p in nonrepos]
    (output / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8", errors="backslashreplace")
    print(json.dumps({"output": str(output), "repositories": len(sources), "counts": dict(counts)}))


if __name__ == "__main__":
    main()
