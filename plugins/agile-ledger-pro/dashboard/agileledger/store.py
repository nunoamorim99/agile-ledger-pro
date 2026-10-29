"""Loading a repo folder, splicing edits into it, and writing it back safely.

Three properties matter here:

* **Surgical.** An edit replaces only the line span the parser reported, so
  anything this code does not model survives untouched.
* **Derived data stays derived.** After any mutation the overview tables, the
  roll-up lines and the epic rollups are rebuilt from the entries.
* **Atomic.** A file is written to a sibling temp file and moved into place, so
  an interrupted write cannot leave a half-written ledger behind.
"""

from __future__ import annotations

import os
import re
from collections import Counter
import tempfile
from pathlib import Path

from . import mdutil, parse, render, resolve
from .mdutil import split_lines
from .model import LEDGER_FILES, EMPTY, id_rank


class LossError(Exception):
    """A save that would delete text nobody asked to change. Nothing is written."""


def _public(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if not k.startswith("_")}


class LedgerFile:
    """One ledger .md file, held as lines with a dirty flag."""

    def __init__(self, path: Path):
        self.path = path
        self.exists = path.is_file()
        self.lines = split_lines(path.read_text(encoding="utf-8")) if self.exists else []
        self._original = list(self.lines)
        #: Words an action said it meant to replace — the old value of a field
        #: it edited, a derived table it rebuilt. The no-loss guard allows
        #: these to disappear and nothing else.
        self.allowed: Counter = Counter()

    @property
    def dirty(self) -> bool:
        return self.lines != self._original

    def allow(self, text: str) -> None:
        self.allowed.update(mdutil.words(text))

    def replace(self, span: tuple[int, int], new_lines: list[str], *, allow: bool = False) -> None:
        """Splice ``new_lines`` over ``span``.

        ``allow=True`` says the old lines are derived or explicitly replaced, so
        their words may go. A patched entry carries the exact text it replaced
        (`render.Lines.replaced`), and only that is allowed.
        """
        start, end = span
        if allow:
            self.allow("\n".join(self.lines[start:end]))
        replaced = getattr(new_lines, "replaced", None)
        if replaced:
            self.allow(replaced)
        self.lines[start:end] = list(new_lines)

    def insert(self, at: int, new_lines: list[str]) -> None:
        self.lines[at:at] = list(new_lines)

    def save(self) -> bool:
        """Write atomically. Returns True when something was actually written."""
        if not self.dirty:
            return False
        self.allowed = Counter()
        text = "\n".join(self.lines)
        if not text.endswith("\n"):
            text += "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent),
                                   prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        self._original = list(self.lines)
        self.exists = True
        return True


class Repo:
    """A single repo folder inside the ledger root."""

    def __init__(self, root: Path, slug: str):
        self.root = Path(root)
        self.slug = slug
        # A flat ledger lives inside its own project, so its files sit at the
        # root rather than in a per-repo folder.
        self.path = resolve.repo_folder(self.root, slug)
        self.flat = self.path == self.root
        if not self.path.is_dir():
            raise FileNotFoundError(f"no such repo folder in the ledger: {slug}")
        self.files = {name: LedgerFile(self.path / name) for name in LEDGER_FILES}

    # -- convenience -------------------------------------------------------

    def file(self, name: str) -> LedgerFile:
        return self.files[name]

    def lines(self, name: str) -> list[str]:
        return self.files[name].lines

    # -- reading -----------------------------------------------------------

    def ideas(self) -> list[dict]:
        return parse.parse_ideas(self.lines("Ideas.md"))

    def triaged_ideas(self) -> list[dict]:
        """Ideas that left the inbox, with where each went. The funnel's far end."""
        return parse.parse_triaged_ideas(self.lines("Ideas.md"))

    def epics(self) -> list[dict]:
        epics = parse.parse_epics(self.lines("Epic-Backlog.md"))
        for epic in epics:
            epic["state"] = render.epic_state_from_emoji(epic.get("emoji", ""))
        return epics

    def stories(self) -> list[dict]:
        return parse.parse_stories(self.lines("User-Stories.md"))

    def bug_inbox(self) -> list[dict]:
        return parse.parse_bug_inbox(self.lines("Bugs.md"))

    def bugs(self) -> list[dict]:
        return parse.parse_bugs(self.lines("Bugs.md"))

    def sprint(self) -> dict:
        return parse.parse_sprint(self.lines("Sprint.md"))

    def history(self) -> dict:
        return parse.parse_history(self.lines("Sprints-History.md"))

    def releases(self) -> dict:
        return parse.parse_releases(self.lines("Releases.md"))

    def definitions(self) -> dict:
        return parse.parse_definitions(self.lines("Definitions.md"))

    def next_ids(self) -> dict[str, str]:
        return parse.parse_next_ids(self.lines("Epic-Backlog.md"))

    def snapshot(self) -> dict:
        """Everything the dashboard needs for this repo, in one payload."""
        stories = self.stories()
        bugs = self.bugs()
        epics = self.epics()
        by_id = {s["id"]: s for s in stories}
        for epic in epics:
            epic["rollup"] = render.epic_rollup(epic, by_id)
        sprint = self.sprint()
        definitions = self.definitions()
        return {
            "slug": self.slug,
            "ideas": self.ideas(),
            "triaged_ideas": self.triaged_ideas(),
            "epics": epics,
            # The writer's bookkeeping (the entry as written, its values as
            # read) is for the server, not the page.
            "stories": [_public(s) for s in stories],
            "bug_inbox": self.bug_inbox(),
            "bugs": [_public(b) for b in bugs],
            "sprint": sprint,
            "history": self.history(),
            "releases": self.releases(),
            "definitions": definitions,
            "next_ids": self.next_ids(),
            "missing_files": [n for n, f in self.files.items() if not f.exists],
            "layout": resolve.detect_layout(self.path),
            "placement": "in-repo" if self.flat else "standalone",
            "stats": self._stats(stories, bugs, epics, sprint),
        }

    def _stats(self, stories, bugs, epics, sprint) -> dict:
        def points(items):
            total = 0
            for item in items:
                try:
                    total += int(str(item.get("estimate", "")).strip())
                except (TypeError, ValueError):
                    pass
            return total

        ready = [s for s in stories if s["state"] == "Ready"]
        in_sprint = [s for s in stories if s["state"] == "In Sprint"]
        return {
            "epics": len(epics),
            "stories": len(stories),
            "ready": len(ready),
            "ready_points": points(ready),
            "in_sprint": len(in_sprint),
            "in_sprint_points": points(in_sprint),
            "delivered": sum(1 for s in stories if s["state"] == "Delivered"),
            "open_bugs": sum(1 for b in bugs
                             if b["state"] in render.OPEN_BUG_STATES),
            "inbox_ideas": len(self.ideas()),
            "inbox_bugs": len(self.bug_inbox()),
            "sprint_name": sprint.get("name", EMPTY),
            "board_counts": {col: len(items) for col, items in sprint["board"].items()},
            "blocked": len(sprint.get("blocked") or []),
            "increment": len(self.releases()["increment"]),
        }

    # -- ID allocation -----------------------------------------------------

    def allocate_id(self, kind: str) -> str:
        """Next free ID of ``kind``, taking the max of the counter and reality.

        The counter in `Epic-Backlog.md` can go stale if a file was hand-edited;
        taking the maximum of counter and the highest ID actually present means
        a reused ID is impossible, which matters because IDs are the join key
        with git.
        """
        kind = kind.upper()
        counter = self.next_ids().get(kind, f"{kind}-001")
        used = []
        if kind == "EPIC":
            used = [e["id"] for e in self.epics()]
        elif kind == "US":
            used = [s["id"] for s in self.stories()]
            for epic in self.epics():
                used += [s["id"] for s in epic.get("stories") or []]
        elif kind == "BUG":
            used = [b["id"] for b in self.bugs()]
        highest = max([id_rank(i) for i in used] + [0])
        number = max(id_rank(counter), highest + 1)
        return f"{kind}-{number:03d}"

    def bump_next_id(self, kind: str, allocated: str) -> None:
        """Advance the ``Next free ID`` counter past ``allocated``."""
        kind = kind.upper()
        following = f"{kind}-{id_rank(allocated) + 1:03d}"
        ledger = self.file("Epic-Backlog.md")
        mask = mdutil.comment_mask(ledger.lines)
        for i, line in enumerate(ledger.lines):
            if mask[i] or "next free id" not in line.lower():
                continue
            ledger.lines[i] = re.sub(rf"\b{kind}:\s*{kind}-\d+",
                                     f"{kind}: {following}", line)
            return

    # -- section helpers ---------------------------------------------------

    def _section(self, name: str, level: int, predicate):
        return mdutil.find_section(self.lines(name), level, predicate)

    def append_to_section(self, name: str, level: int, predicate,
                          new_lines: list[str], *, top: bool = False) -> bool:
        """Insert ``new_lines`` into a section, keeping one blank line around it."""
        handle = self.file(name)
        span = mdutil.find_section(handle.lines, level, predicate)
        if not span:
            return False
        start, end = span
        if top:
            at = start + 1
            while at < end and not handle.lines[at].strip():
                at += 1
            block = list(new_lines) + [""]
            handle.insert(at, block)
            return True

        at = mdutil.trim_span(handle.lines, start, end)[1]
        block = list(new_lines)
        if at > start and handle.lines[at - 1].strip():
            block = [""] + block
        handle.insert(at, block)
        return True

    def replace_entry(self, name: str, span: tuple[int, int], new_lines: list[str]) -> None:
        self.file(name).replace(span, new_lines)

    # -- derived rebuilds --------------------------------------------------

    def rebuild_overviews(self) -> None:
        """Recompute every derived table and roll-up from the entries."""
        self._rebuild_story_overview()
        self._rebuild_bug_overview()
        self._rebuild_epic_overview()

    def _overview_span(self, name: str) -> tuple[int, int] | None:
        return self._section(name, 2, lambda t: t.strip().lower() == "overview")

    def _replace_table(self, name: str, new_lines: list[str]) -> None:
        handle = self.file(name)
        span = self._overview_span(name)
        if not span:
            return
        start, end = span
        table = mdutil.find_table(handle.lines, start, end)
        if table:
            handle.replace(table, new_lines, allow=True)
        else:
            handle.insert(mdutil.trim_span(handle.lines, start, end)[1], [""] + new_lines)

    def _replace_rollup(self, name: str, predicate, new_lines: list[str],
                        tail_predicate=None) -> None:
        """Replace the roll-up region at the top of an Overview section.

        A roll-up can span several lines with blanks between them (Bugs.md has
        a counts line, a blank, then "Open by priority"), so ``tail_predicate``
        names the last line of the region. Without it the region is the single
        matched line plus any unbroken continuation.
        """
        handle = self.file(name)
        span = self._overview_span(name)
        if not span:
            return
        start, end = span
        table = mdutil.find_table(handle.lines, start, end)
        limit = table[0] if table else end
        for i in range(start + 1, limit):
            if not predicate(handle.lines[i]):
                continue
            if tail_predicate:
                run = i + 1
                for j in range(i + 1, limit):
                    if tail_predicate(handle.lines[j]):
                        run = j + 1
                        break
            else:
                run = i + 1
                while run < limit and handle.lines[run].strip() and \
                        not handle.lines[run].lstrip().startswith("_"):
                    run += 1
            handle.replace((i, run), new_lines, allow=True)
            return
        at = start + 1
        while at < limit and not handle.lines[at].strip():
            at += 1
        handle.insert(at, list(new_lines) + [""])

    def _rebuild_story_overview(self) -> None:
        stories = self.stories()
        self._replace_rollup(
            "User-Stories.md",
            lambda l: "Ready" in l and "In Sprint" in l and not l.strip().startswith("|"),
            [render.story_rollup_line(stories)])
        self._replace_table("User-Stories.md", render.story_table(stories))

    def _rebuild_bug_overview(self) -> None:
        bugs = self.bugs()
        inbox = len(self.bug_inbox())
        rollup = render.bug_rollup_lines(bugs, inbox)
        self._replace_rollup(
            "Bugs.md",
            lambda l: "Inbox" in l and "Fixed" in l and not l.strip().startswith("|"),
            rollup,
            tail_predicate=lambda l: l.strip().lower().startswith("open by priority"))
        self._replace_table("Bugs.md", render.bug_table(bugs))

    @staticmethod
    def _epic_state(epic: dict) -> str:
        """Derived from the children — except where the children say nothing.

        An epic with no stories yet, or one a person paused or discarded whose
        stories are merely Ready, keeps the state somebody gave it: deriving
        "Proposed" there would undo a decision, not compute a fact.
        """
        current = epic.get("state") or render.epic_state_from_emoji(epic.get("emoji", ""))
        if not epic.get("stories"):
            return current
        derived = render.derive_epic_state(epic)
        if current in ("Paused", "Discarded") and derived == "Proposed":
            return current
        return derived

    def _rebuild_epic_overview(self) -> None:
        """Re-derive each epic's state and rollups — on its title line only.

        This used to re-render every epic block after every action, which
        rewrote the goal and notes of epics nobody touched in their summary
        shape, losing whatever did not fit it. Now the one derived line is
        recomputed and written back only when a value on it actually moved.
        """
        stories = {s["id"]: s for s in self.stories()}
        handle = self.file("Epic-Backlog.md")
        for epic in self.epics():
            at = epic.get("title_at")
            if at is None:
                continue
            line = handle.lines[at]
            as_read = render.epic_title_line(epic, line)
            fresh = dict(epic)
            fresh["rollup"] = render.epic_rollup(epic, stories)
            fresh["state"] = self._epic_state(epic)
            fresh["emoji"] = render.EPIC_STATE_EMOJI[fresh["state"]]
            updated = render.epic_title_line(fresh, line)
            # Not allowed to lose anything: a state glyph and two figures move,
            # and none of those are words. If a word goes, the guard says so.
            if updated != as_read:
                handle.replace((at, at + 1), [updated])

        refreshed = self.epics()
        by_id = {s["id"]: s for s in self.stories()}
        for epic in refreshed:
            epic["rollup"] = render.epic_rollup(epic, by_id)
            epic["state"] = self._epic_state(epic)
        self._replace_table("Epic-Backlog.md", render.epic_table(refreshed))

    # -- epic index lines --------------------------------------------------

    def _epic(self, epic_id: str) -> dict | None:
        return next((e for e in self.epics() if e["id"] == epic_id), None)

    def insert_index_line(self, epic_id: str, line: str, item_id: str) -> bool:
        """Put one index line under an epic's ``**Stories:**``, in ID order.

        Only that line is added; the epic's other lines are not rewritten. An
        epic with no Stories block yet gets one at its end.
        """
        epic = self._epic(epic_id)
        if not epic:
            return False
        handle = self.file("Epic-Backlog.md")
        index = epic.get("stories") or []
        if index:
            later = [i for i in index if id_rank(i["id"]) > id_rank(item_id)]
            at = later[0]["line"] if later else index[-1]["line"] + 1
            handle.insert(at, [line])
            return True
        if epic.get("stories_at"):
            start, end = epic["stories_at"]
            at = start + 1
            while at < end and not handle.lines[at].strip():
                at += 1
            if at >= end or at == start + 1:
                handle.insert(start + 1, ["", line])
            else:
                handle.insert(at, [line])
            return True
        end = epic["span"][1]
        handle.insert(end, ["", "**Stories:**", "", line])
        return True

    def remove_index_line(self, epic_id: str, item_id: str) -> str | None:
        """Take one story's index line out of an epic, returning it as written."""
        epic = self._epic(epic_id)
        item = next((i for i in (epic or {}).get("stories") or [] if i["id"] == item_id), None)
        if not item:
            return None
        handle = self.file("Epic-Backlog.md")
        raw = handle.lines[item["line"]]
        handle.replace((item["line"], item["line"] + 1), [])
        return raw

    def sync_epic_index(self, story: dict) -> None:
        """Mirror a story's coarse state onto its epic's index line — that line only.

        Values the story does not change keep the line's own words: a state
        reading "✅ Delivered in v1.2" stays so while the story stays
        Delivered, and a note after the assignee rides along.
        """
        if not story.get("parent"):
            return
        from .model import STORY_STATE_LABEL
        epic = self._epic(story["parent"])
        if not epic:
            return
        handle = self.file("Epic-Backlog.md")
        label = STORY_STATE_LABEL.get(story.get("state", "Ready"), "")
        old = next((i for i in epic.get("stories") or [] if i["id"] == story["id"]), None)
        row = dict(old or {"id": story["id"], "extra": [], "assignee_note": ""})
        row["title"] = story.get("title") or row.get("title", "")
        if not (old and label and label in (old.get("state") or "")):
            # "✅ Delivered — re-opened by US-074": the state moves, the note stays.
            _, sep, note = (old.get("state") if old else "").partition(mdutil.DASH)
            row["state"] = label + (f" {mdutil.DASH} {note.strip()}" if sep and note.strip() else "")
        row["priority"] = story.get("priority", "")
        row["points"] = story.get("estimate", "")
        row["assignee"] = story.get("assignee", "")
        line = render.story_index_line(row)
        if old is None:
            self.insert_index_line(epic["id"], line, story["id"])
            return
        same = all(render._norm(row.get(k)) == render._norm(old.get(k))
                   for k in ("title", "state", "priority", "points", "assignee"))
        if same:
            return
        prefix = re.match(r"^(\s*[-*]\s+)", old["raw"])
        line = (prefix.group(1) if prefix else "- ") + line[2:]
        # Only the old values that changed may go — not the whole line, which
        # would hide a note lost with them.
        for key in ("title", "priority", "points", "assignee"):
            if render._norm(row.get(key)) != render._norm(old.get(key)):
                handle.allow(str(old.get(key) or ""))
        if render._norm(row.get("state")) != render._norm(old.get("state")):
            handle.allow((old.get("state") or "").partition(mdutil.DASH)[0])
        handle.replace((old["line"], old["line"] + 1), [line])

    # -- saving ------------------------------------------------------------

    def lost_words(self) -> Counter:
        """Words the eight files held before this action and would not hold after.

        Taken across all eight together, so text that moves — a story changing
        section, an Increment line rolling into a version — is not a loss. What
        an action declared it was replacing (`LedgerFile.allowed`) is not either.
        Anything else is a sentence somebody wrote that the save would delete.
        """
        before, after, allowed = Counter(), Counter(), Counter()
        for handle in self.files.values():
            if not handle.dirty:
                continue
            before.update(mdutil.words("\n".join(handle._original)))
            after.update(mdutil.words("\n".join(handle.lines)))
            allowed.update(handle.allowed)
        return (before - after) - allowed

    def save(self) -> list[str]:
        """Write every changed file — or none, if that would delete text.

        The guard runs before the first byte is written, so a refused save
        leaves the ledger exactly as it was.
        """
        lost = self.lost_words()
        if lost:
            sample = ", ".join(sorted(lost)[:12]) + (" …" if len(lost) > 12 else "")
            raise LossError(
                "Nothing was saved: this change would have deleted text the dashboard "
                f"does not edit ({sample}). Make it with Claude or in the file instead, "
                "and please report it — the dashboard should never drop a word.")
        written = []
        for name, handle in self.files.items():
            if handle.save():
                written.append(name)
        return written

    def dirty_files(self) -> list[str]:
        return [n for n, f in self.files.items() if f.dirty]
