"""Read-only proof that the dashboard's writer is safe on a real ledger.

``python serve.py --verify`` runs this over every project in the ledger and
never saves. For each entry it checks the three things a write depends on:

1. **Untouched, unchanged.** Writing an entry back with no value changed
   gives the same bytes. Anything else means the writer would reformat text
   nobody asked it to touch.
2. **An edit changes only itself.** Changing one field in memory and writing
   the entry back passes the no-loss guard — the only words that go are the
   old value's.
3. **A rebuild loses nothing.** Recomputing the derived tables, roll-ups and
   epic title lines removes no word that is not itself derived.

It is the check to run on a ledger written by hand, or by an older version,
before trusting the page with it.
"""

from __future__ import annotations

import copy
from pathlib import Path

from . import mdutil, render, resolve
from .store import Repo


def _entry_report(repo: Repo, kind: str) -> dict:
    entries = repo.stories() if kind == "story" else repo.bugs()
    write = render.render_story if kind == "story" else render.render_bug
    identical, reformatted, unsafe = 0, [], []
    for entry in entries:
        if list(write(entry)) == list(entry["_raw"]):
            identical += 1
        else:
            reformatted.append(entry["id"])
        # Change one field in memory and write the entry back: the only words
        # allowed to go are the ones the patch says it replaced — the same
        # test the save guard applies, scoped to this entry.
        probe = copy.deepcopy(entry)
        probe["estimate"] = "13" if str(probe.get("estimate")) != "13" else "21"
        out = write(probe)
        lost = (mdutil.words("\n".join(entry["_raw"])) - mdutil.words("\n".join(out))) \
            - mdutil.words(getattr(out, "replaced", ""))
        if lost:
            unsafe.append(f"{entry['id']} ({', '.join(sorted(lost)[:6])})")
    return {"count": len(entries), "identical": identical,
            "reformatted": reformatted, "unsafe": unsafe}


def verify_repo(root: Path, slug: str) -> dict:
    repo = Repo(root, slug)
    stories = _entry_report(repo, "story")
    bugs = _entry_report(repo, "bug")

    probe = Repo(root, slug)
    probe.rebuild_overviews()
    lost = probe.lost_words()
    touched = [n for n in probe.dirty_files()]
    return {
        "slug": slug,
        "stories": stories,
        "bugs": bugs,
        "epics": len(probe.epics()),
        "rebuild_lost": sorted(lost),
        "rebuild_touches": touched,
    }


def verify(root: Path) -> tuple[bool, list[str]]:
    """Every project in the ledger. Returns ``(ok, report lines)``."""
    lines, ok = [], True
    repos = [r for r in resolve.list_repos(root) if r.get("present")]
    if not repos:
        return False, ["No project folders found in this ledger."]
    for row in repos:
        try:
            r = verify_repo(root, row["slug"])
        except FileNotFoundError:
            continue
        s, b = r["stories"], r["bugs"]
        bad = s["unsafe"] or b["unsafe"] or r["rebuild_lost"]
        ok = ok and not bad
        lines.append(f"{'FAIL' if bad else 'ok  '} {r['slug']}: "
                     f"{s['count']} stories ({s['identical']} unchanged on rewrite), "
                     f"{b['count']} bugs ({b['identical']} unchanged), {r['epics']} epics")
        if s["reformatted"] or b["reformatted"]:
            lines.append("       rewritten differently (no words lost): "
                         + ", ".join(s["reformatted"] + b["reformatted"]))
        for item in s["unsafe"] + b["unsafe"]:
            lines.append(f"       an edit would lose text: {item}")
        if r["rebuild_lost"]:
            lines.append("       a rebuild would lose: " + ", ".join(r["rebuild_lost"][:12]))
        if r["rebuild_touches"]:
            lines.append("       derived lines a first save refreshes in: "
                         + ", ".join(r["rebuild_touches"]))
    lines.append("")
    lines.append("Safe: no write would delete text." if ok else
                 "Not safe: the lines marked FAIL would lose text. Nothing was written. "
                 "Please send this report.")
    return ok, lines
