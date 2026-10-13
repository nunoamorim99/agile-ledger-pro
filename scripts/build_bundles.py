#!/usr/bin/env python3
"""Build the downloadable install bundles from the plugin source of truth.

    source: plugins/agile-ledger-pro/{commands,skills,dashboard}
    output: dist/agile-ledger-pro-<version>.zip        full drop-in for .claude/
            dist/agile-ledger-pro-skill-<version>.zip  skill only, for Claude.ai web upload

The dashboard ships only in the full bundle: it is a local Python server, and the
skill-only bundle targets Claude.ai on the web, where there is nothing to run it on.

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


def _skip_from_bundle(path: Path) -> bool:
    """Caches, the test fixture, and the design handoff.

    The fixture is deliberately excluded: it contains a Registry.md carrying the
    real `# Agile-Ledger Registry` marker, and an installed copy of it sitting
    under .claude/ could be picked up as a ledger root by the resolver.

    `design-handoff/` held the mockups the dashboard was built from. It is gone
    now that every phase is in, but the rule stays: design material belongs in
    the repository, not in a quarter-megabyte shipped to everyone who installs
    the plugin. If another handoff lands there, it still cannot ship.
    """
    parts = path.parts
    return ("__pycache__" in parts or "tests" in parts or "design-handoff" in parts
            or path.suffix in {".pyc", ".pyo"})


def add_tree(zf: zipfile.ZipFile, source: Path, prefix: str, skip=None) -> None:
    """Write every file under `source` into the archive at `prefix`, sorted for reproducibility."""
    for path in sorted(source.rglob("*")):
        if path.is_file() and not (skip and skip(path)):
            zf.write(path, f"{prefix}/{path.relative_to(source).as_posix()}")


def build() -> tuple[Path, Path, str]:
    for required in (SRC / "commands", SRC / "skills", SRC / "dashboard"):
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
        add_tree(zf, SRC / "dashboard", "dashboard", skip=_skip_from_bundle)
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
                     "commands/agile-ledger-pro/dashboard.md",
                     "dashboard/serve.py",
                     "dashboard/agileledger/parse.py",
                     "dashboard/static/index.html",
                     "dashboard/static/app.js",
                     "dashboard/static/style.css",
                     "INSTALL.txt"):
        if required not in names:
            errors.append(f"full bundle missing {required}")
    if any("__pycache__" in n for n in names):
        errors.append("full bundle contains __pycache__")
    # A stray Registry.md under .claude/ could be mistaken for a ledger root.
    if any("/tests/" in n or n.endswith("Registry.md") for n in names):
        errors.append("full bundle ships the test fixture")
    if any("design-handoff" in n for n in names):
        errors.append("full bundle ships the design handoff")

    with zipfile.ZipFile(skill) as zf:
        skill_names = zf.namelist()
    if "agile-ledger-pro/SKILL.md" not in skill_names:
        errors.append("skill bundle missing agile-ledger-pro/SKILL.md")
    if any(n.startswith("commands/") for n in skill_names):
        errors.append("skill bundle should not contain commands/")
    if any("dashboard" in n for n in skill_names):
        errors.append("skill bundle should not contain the dashboard")
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
