#!/usr/bin/env python3
"""Build the downloadable install bundles from the plugin source of truth.

    source: plugins/agile-ledger-pro/{commands,skills}
    output: dist/agile-ledger-pro-<version>.zip        full drop-in for .claude/
            dist/agile-ledger-pro-skill-<version>.zip  skill only, for Claude.ai web upload

The version is read from plugins/agile-ledger-pro/.claude-plugin/plugin.json, so a bundle
can never disagree with the plugin manifest.

Usage:
    python3 scripts/build_bundles.py            build into dist/
    python3 scripts/build_bundles.py --check    build, then assert the contents are right

Uses only the standard library so it runs identically on Windows and on CI.
"""

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "plugins" / "agile-ledger-pro"
DIST = ROOT / "dist"


def add_tree(zf: zipfile.ZipFile, source: Path, prefix: str) -> None:
    """Write every file under `source` into the archive at `prefix`, sorted for reproducibility."""
    for path in sorted(source.rglob("*")):
        if path.is_file():
            zf.write(path, f"{prefix}/{path.relative_to(source).as_posix()}")


def build() -> tuple[Path, Path, str]:
    for required in (SRC / "commands", SRC / "skills"):
        if not required.is_dir():
            sys.exit(f"build-bundles: missing {required.relative_to(ROOT)}")

    manifest = json.loads((SRC / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = manifest["version"]

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    full = DIST / f"agile-ledger-pro-{version}.zip"
    skill = DIST / f"agile-ledger-pro-skill-{version}.zip"

    # Full bundle — unzips straight into .claude/. Commands sit one level deeper than in
    # the plugin because a manual install namespaces them by directory
    # (commands/agile-ledger-pro/idea.md -> /agile-ledger-pro:idea).
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED) as zf:
        add_tree(zf, SRC / "skills", "skills")
        add_tree(zf, SRC / "commands", "commands/agile-ledger-pro")
        zf.write(ROOT / "INSTALL.txt", "INSTALL.txt")
        zf.write(ROOT / "LICENSE", "LICENSE")

    # Skill-only bundle — Claude.ai web/desktop's Customize -> Skills expects the skill
    # folder itself, with no commands alongside it.
    with zipfile.ZipFile(skill, "w", zipfile.ZIP_DEFLATED) as zf:
        add_tree(zf, SRC / "skills" / "agile-ledger-pro", "agile-ledger-pro")
        zf.write(ROOT / "LICENSE", "agile-ledger-pro/LICENSE")

    print(f"build-bundles: built from plugins/agile-ledger-pro at version {version}")
    for archive in (full, skill):
        with zipfile.ZipFile(archive) as zf:
            print(f"  {archive.relative_to(ROOT).as_posix()}  ({len(zf.namelist())} files)")
    return full, skill, version


def check(full: Path, skill: Path) -> int:
    errors = []

    with zipfile.ZipFile(full) as zf:
        names = zf.namelist()
    for required in ("skills/agile-ledger-pro/SKILL.md",
                     "skills/agile-ledger-pro-workspace/SKILL.md",
                     "commands/agile-ledger-pro/idea.md",
                     "INSTALL.txt"):
        if required not in names:
            errors.append(f"full bundle missing {required}")

    with zipfile.ZipFile(skill) as zf:
        skill_names = zf.namelist()
    if "agile-ledger-pro/SKILL.md" not in skill_names:
        errors.append("skill bundle missing agile-ledger-pro/SKILL.md")
    if any(n.startswith("commands/") for n in skill_names):
        errors.append("skill bundle should not contain commands/")
    # The skill bundle is the web-upload path; it must carry its reference templates.
    if not any(n.startswith("agile-ledger-pro/references/") for n in skill_names):
        errors.append("skill bundle missing agile-ledger-pro/references/")

    if errors:
        print("\nbuild-bundles: FAILED", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("build-bundles: bundle contents OK")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="assert bundle contents after building")
    args = parser.parse_args()

    full_zip, skill_zip, _ = build()
    sys.exit(check(full_zip, skill_zip) if args.check else 0)
