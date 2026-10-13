"""Finding the ledger root, and reading the two files that sit at it.

The resolution rules match `SKILL.md`: a ledger root is a directory holding a
`Registry.md` whose first heading is `# Agile-Ledger Registry` — **never** a
directory matched by name. That marker is what keeps an existing Agile-Ledger
ledger readable by Pro.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import mdutil
from .mdutil import clean

REGISTRY_MARKER = "Agile-Ledger Registry"
REGISTRY_FILE = "Registry.md"
CONFIG_FILE = "Config.md"


def is_ledger_root(path: Path) -> bool:
    """True when ``path`` holds a Registry.md carrying the marker heading."""
    registry = path / REGISTRY_FILE
    if not registry.is_file():
        return False
    try:
        text = registry.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in mdutil.split_lines(text):
        if not line.strip():
            continue
        if mdutil.heading_level(line) == 1:
            return REGISTRY_MARKER in mdutil.heading_text(line)
        # Only the *first* heading counts; anything else means this is not it.
        if mdutil.heading_level(line):
            return False
    return False


def find_ledger_root(start: Path | None = None) -> Path | None:
    """Locate the ledger root from ``start``, mirroring the skill's search.

    1. ``start`` itself, then every parent directory.
    2. Each of those directories' immediate children (the common layout, where
       the ledger repo sits beside the code repos under one workspace root).
    """
    start = (start or Path.cwd()).resolve()
    candidates = [start, *start.parents]

    for directory in candidates:
        if is_ledger_root(directory):
            return directory

    for directory in candidates:
        try:
            children = sorted(p for p in directory.iterdir() if p.is_dir())
        except OSError:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            if is_ledger_root(child):
                return child
    return None


def read_config(root: Path) -> dict[str, str]:
    """Parse the fenced ``key: value`` block in the ledger root's Config.md."""
    config: dict[str, str] = {}
    path = root / CONFIG_FILE
    if not path.is_file():
        return config
    lines = mdutil.split_lines(path.read_text(encoding="utf-8"))
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        body = line.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", body)
        if m:
            config[m.group(1)] = m.group(2).strip()
    return config


def read_registry(root: Path) -> list[dict[str, str]]:
    """Rows of the Registry table, as dicts keyed by a normalised column name.

    Only rows whose folder actually exists are marked ``present``; a missing
    folder is reported rather than dropped, because the Registry is
    never-delete and a stale row is information, not noise.
    """
    path = root / REGISTRY_FILE
    if not path.is_file():
        return []
    lines = mdutil.split_lines(path.read_text(encoding="utf-8"))
    headers, rows = mdutil.parse_table(lines, 0, len(lines))
    if not headers:
        return []

    def key(header: str) -> str:
        header = header.lower()
        if "repo" in header or "folder" in header:
            return "slug"
        if "code path" in header or "path" in header:
            return "code_path"
        if "remote" in header:
            return "remote"
        if "status" in header:
            return "status"
        if "sync" in header:
            return "last_sync"
        if "swept" in header:
            return "last_swept"
        if "note" in header:
            return "notes"
        return re.sub(r"[^a-z0-9]+", "_", header).strip("_")

    keys = [key(h) for h in headers]
    out = []
    for row in rows:
        entry = {k: clean(v) for k, v in zip(keys, row)}
        slug = mdutil.strip_links(entry.get("slug", "")).strip()
        if not slug or slug == mdutil.EMPTY:
            continue
        entry["slug"] = slug
        entry["present"] = (root / slug).is_dir()
        out.append(entry)
    return out


def detect_layout(folder: Path) -> dict:
    """Which era's file layout a repo folder uses.

    The ledger's file layout changed during v1 — `Ideas.md` arrived in v1.4,
    `Bugs.md` in v1.3, and the `Backlog.md` split in v1.2 — so a folder
    relocated from an older ledger can be missing files the skill expects. A
    dashboard that just rendered an empty backlog would be lying about why.
    """
    has = {name: (folder / name).is_file() for name in
           ("Backlog.md", "Epic-Backlog.md", "User-Stories.md", "Ideas.md", "Bugs.md")}

    if has["Backlog.md"] and not has["Epic-Backlog.md"]:
        if not has["User-Stories.md"]:
            era, detail = "v1.0 – v1.1", ("story detail is still nested inside Backlog.md, and "
                                          "Ideas.md and Bugs.md do not exist yet")
        elif not has["Bugs.md"]:
            era, detail = "v1.2", "User-Stories.md was split out, but Bugs.md and Ideas.md do not exist yet"
        elif not has["Ideas.md"]:
            era, detail = "v1.3", "Bugs.md exists, but the idea inbox is still a section inside Backlog.md"
        else:
            era, detail = "pre-v1.4", "Backlog.md has not been renamed to Epic-Backlog.md yet"
        return {
            "era": era,
            "legacy": True,
            "detail": detail,
            "message": (f"This folder uses the {era} file layout, so parts of it cannot be read here. "
                        f"Run /migrate-ledger in Claude Code to convert it."),
        }

    from .model import LEDGER_FILES
    missing = [n for n in LEDGER_FILES if not (folder / n).is_file()]
    if missing:
        return {
            "era": "current",
            "legacy": False,
            "detail": "files missing from an otherwise current folder",
            "message": ("Missing from this folder: " + ", ".join(missing)
                        + ". /register-repo scaffolds the eight files."),
        }
    return {"era": "current", "legacy": False, "detail": "", "message": ""}


def list_repos(root: Path) -> list[dict[str, str]]:
    """Every repo folder worth showing: Registry rows plus unregistered folders.

    A folder holding ledger files but missing from the Registry is surfaced
    with ``registered: False`` rather than hidden — the dashboard should show
    what is on disk, and the fix is a `/register-repo` run.
    """
    rows = read_registry(root)
    known = {r["slug"] for r in rows}
    repos = [dict(r, registered=True) for r in rows]

    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if child.name.startswith(".") or child.name in known:
            continue
        if any((child / n).is_file() for n in
               ("Epic-Backlog.md", "Ideas.md", "Backlog.md")):
            repos.append({
                "slug": child.name,
                "code_path": mdutil.EMPTY,
                "remote": mdutil.EMPTY,
                "status": "unregistered",
                "last_sync": mdutil.EMPTY,
                "last_swept": mdutil.EMPTY,
                "notes": mdutil.EMPTY,
                "present": True,
                "registered": False,
            })
    return repos
