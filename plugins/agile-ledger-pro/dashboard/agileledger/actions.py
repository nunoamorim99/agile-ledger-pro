"""The write operations the dashboard exposes, one per slash command.

Each action mutates the repo folder and returns a summary dict. They follow the
same rules as the matching command in `SKILL.md`: nothing is ever deleted
(items move between sections and keep their row forever), IDs are never reused,
derived tables are rebuilt rather than hand-edited, and a state change updates
both the item's own entry and its mirror (the epic index line, the board).

Gates the skill applies with judgement — Definition of Ready, Definition of
Done, the dependency gate — are surfaced as *warnings* on the response rather
than hard refusals, so the dashboard reports them and the human decides.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import tempfile

from . import mdutil, render, resolve
from .mdutil import EMPTY
from .model import (BOARD_COLUMNS, BUG_STATE_EMOJI, BUG_STATES, STORY_STATE_EMOJI,
                    STORY_STATE_LABEL, STORY_STATES, id_rank, link, slugify)
from .store import Repo


class ActionError(Exception):
    """A request that cannot be carried out, reported back to the browser."""


def today() -> str:
    return datetime.date.today().isoformat()


# --------------------------------------------------------------------------
# Low-level section editing
# --------------------------------------------------------------------------

def _remove_lines(handle, start: int, end: int) -> None:
    """Drop ``[start, end)`` plus one trailing blank so spacing stays even."""
    if end < len(handle.lines) and not handle.lines[end].strip():
        end += 1
    handle.replace((start, end), [])


def _find_state_section(handle, state: str, states: list[str]):
    """The ``## <state>`` section for a state, tolerating combined headings."""
    for idx, title in mdutil.iter_headings(handle.lines, 2):
        low = title.lower()
        if state.lower() in low:
            # A combined "Paused / Discarded" heading serves both.
            return mdutil.section_span(handle.lines, idx)
    return None


def _set_section_bullets(handle, span: tuple[int, int], bullets: list[str]) -> None:
    """Replace a section's top-level bullets, keeping its prose and headings."""
    start, end = span
    mask = mdutil.comment_mask(handle.lines)
    keep = []
    for i in range(start + 1, end):
        if mask[i]:
            keep.append(handle.lines[i])
            continue
        if re.match(r"^\s{0,3}(?:[-*]|\d+\.)\s+\S", handle.lines[i]):
            continue
        keep.append(handle.lines[i])
    while keep and not keep[-1].strip():
        keep.pop()
    body = keep + ([""] if keep and bullets else []) + bullets + [""]
    handle.replace((start + 1, end), body)


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------

def add_idea(repo: Repo, text: str, **_) -> dict:
    text = (text or "").strip()
    if not text:
        raise ActionError("an idea needs some text")
    line = f"- {today()} {mdutil.DASH} {text}"
    if not repo.append_to_section("Ideas.md", 2, lambda t: "inbox" in t.lower(),
                                  [line], top=True):
        raise ActionError("Ideas.md has no '## 💡 Inbox' section")
    return {"message": "Idea captured in Ideas.md", "command": f"/idea {text}"}


def add_bug(repo: Repo, text: str, **_) -> dict:
    text = (text or "").strip()
    if not text:
        raise ActionError("a bug report needs some text")
    line = f"- {today()} {mdutil.DASH} {text}"
    if not repo.append_to_section("Bugs.md", 2, lambda t: "inbox" in t.lower(),
                                  [line], top=True):
        raise ActionError("Bugs.md has no '## 🐛 Inbox' section")
    return {"message": "Bug report captured in Bugs.md", "command": f"/bug {text}"}


# --------------------------------------------------------------------------
# Triage
# --------------------------------------------------------------------------

def _drop_inbox_line(repo: Repo, file_name: str, line_no: int | None) -> None:
    if line_no is None:
        return
    handle = repo.file(file_name)
    if 0 <= line_no < len(handle.lines):
        handle.replace((line_no, line_no + 1), [])


TRIAGED_HEADING = "## \u2705 Triaged"


def _retire_idea(repo: Repo, line_no: int | None, became: str = "", note: str = "") -> None:
    """Move an idea from the inbox to ``## ✅ Triaged`` with where it went.

    Ideas used to be deleted here, the one place the ledger threw anything
    away — and with them went every "ideas per month" and "how many ideas
    become stories" a PM could ever ask for. Now the line is kept, with
    ``→ US-012 (date)`` or ``→ discarded (date): why``, newest first.

    A file from before the section existed gets it appended, once.
    """
    if line_no is None:
        return
    handle = repo.file("Ideas.md")
    if not (0 <= line_no < len(handle.lines)):
        return
    raw = handle.lines[line_no]
    m = re.match(r"^\s{0,3}[-*]\s+(.*)$", raw)
    if not m:
        return
    tail = f"{became} ({today()})" if became else f"discarded ({today()})"
    if note:
        tail += f": {note}"
    line = f"- {m.group(1).strip()} \u2192 {tail}"
    handle.replace((line_no, line_no + 1), [])

    if not mdutil.find_section(handle.lines, 2, lambda t: "triaged" in t.lower()):
        lines = handle.lines
        at = len(lines)
        while at > 0 and not lines[at - 1].strip():
            at -= 1
        handle.insert(at, ["", TRIAGED_HEADING, "",
                           "_Every idea that left the inbox, and where it went. Never deleted._", ""])
    repo.append_to_section("Ideas.md", 2, lambda t: "triaged" in t.lower(), [line], top=True)


def triage_idea_to_epic(repo: Repo, title: str, goal: str = "", area: str = "",
                        target: str = "", idea_line: int | None = None, **_) -> dict:
    title = (title or "").strip()
    if not title:
        raise ActionError("an epic needs a title")
    epic_id = repo.allocate_id("EPIC")
    epic = {
        "id": epic_id, "title": title, "emoji": "\U0001f4a1",
        "target": target or EMPTY, "goal": goal or "", "area": area or "",
        "created": today(), "history": [], "stories": [],
        "rollup": {"stories_done": 0, "stories_total": 0,
                   "points_done": 0, "points_total": 0},
    }
    if not repo.append_to_section("Epic-Backlog.md", 2,
                                  lambda t: t.strip().lower() == "epics",
                                  render.render_epic(epic)):
        raise ActionError("Epic-Backlog.md has no '## Epics' section")
    repo.bump_next_id("EPIC", epic_id)
    _retire_idea(repo, idea_line, became=epic_id)
    return {"message": f"{epic_id} created", "id": epic_id,
            "command": f"/triage  (idea → {epic_id})"}


def triage_idea_to_story(repo: Repo, epic_id: str, title: str, priority: str = "",
                         idea_line: int | None = None, **_) -> dict:
    """Promote an idea to a 📝 Draft story: an epic index line, no detail yet."""
    title = (title or "").strip()
    epic_id = (epic_id or "").strip().upper()
    if not title:
        raise ActionError("a story needs a title")
    epic = next((e for e in repo.epics() if e["id"] == epic_id), None)
    if not epic:
        raise ActionError(f"no such epic: {epic_id}")

    story_id = repo.allocate_id("US")
    index = [dict(i) for i in epic.get("stories") or []]
    index.append({"id": story_id, "title": title,
                  "state": STORY_STATE_LABEL["Draft"],
                  "priority": priority or "", "points": "", "assignee": ""})
    index.sort(key=lambda i: id_rank(i["id"]))
    epic["stories"] = index
    repo.file("Epic-Backlog.md").replace(epic["span"], render.render_epic(epic))
    repo.bump_next_id("US", story_id)
    _retire_idea(repo, idea_line, became=story_id)
    return {"message": f"{story_id} added to {epic_id} as a Draft",
            "id": story_id, "command": f"/triage  (idea → {story_id})"}


def discard_idea(repo: Repo, idea_line: int | None = None, reason: str = "", **_) -> dict:
    _retire_idea(repo, idea_line, note=(reason or "").strip())
    return {"message": "Idea discarded"}


def triage_bug(repo: Repo, title: str, severity: str = "minor", priority: str = "",
               area: str = "", relates_to: str = "", reported_by: str = "",
               symptom: str = "", inbox_line: int | None = None, **_) -> dict:
    title = (title or "").strip()
    if not title:
        raise ActionError("a bug needs a title")
    bug_id = repo.allocate_id("BUG")
    bug = {
        "id": bug_id, "title": title, "state": "Triaged",
        "emoji": BUG_STATE_EMOJI["Triaged"],
        "severity": severity or "minor", "priority": priority or EMPTY,
        "estimate": EMPTY,
        "reported_by": f"{reported_by} ({today()})" if reported_by else today(),
        "triaged": today(),
        "area": area or EMPTY, "assignee": EMPTY,
        "relates_to": (relates_to or "").strip().upper(),
        "symptom": symptom or title, "steps": [],
        "expected": "", "actual": "", "assessment": "", "notes": "",
    }
    placed = repo.append_to_section(
        "Bugs.md", 2,
        lambda t: "triaged" in t.lower() or "confirmed" in t.lower(),
        render.render_bug(bug))
    if not placed:
        raise ActionError("Bugs.md has no Triaged / Confirmed section")
    _bump_bug_counter(repo, bug_id)
    _drop_inbox_line(repo, "Bugs.md", inbox_line)
    return {"message": f"{bug_id} registered", "id": bug_id,
            "command": f"/triage-bug  (inbox → {bug_id})"}


def _bump_bug_counter(repo: Repo, allocated: str) -> None:
    handle = repo.file("Bugs.md")
    following = f"BUG-{id_rank(allocated) + 1:03d}"
    mask = mdutil.comment_mask(handle.lines)
    for i, line in enumerate(handle.lines):
        if mask[i] or "next free id" not in line.lower():
            continue
        handle.lines[i] = re.sub(r"\bBUG:\s*BUG-\d+", f"BUG: {following}", line)
        return


# --------------------------------------------------------------------------
# Shaping a story
# --------------------------------------------------------------------------

def _story_by_id(repo: Repo, story_id: str) -> dict:
    story = next((s for s in repo.stories() if s["id"] == story_id.upper()), None)
    if not story:
        raise ActionError(f"no detailed story {story_id} in User-Stories.md")
    return story


def _epic_index_entry(repo: Repo, story_id: str):
    for epic in repo.epics():
        for item in epic.get("stories") or []:
            if item["id"] == story_id.upper():
                return epic, item
    return None, None


def detail_story(repo: Repo, story_id: str, title: str = "", story: str = "",
                 criteria=None, priority: str = "", estimate: str = "",
                 area: str = "", layer: str = "", assignee: str = "",
                 dependencies=None, notes: str = "", **_) -> dict:
    """Draft → ✅ Ready: write the full entry and flip the epic index line."""
    story_id = (story_id or "").strip().upper()
    epic, index_item = _epic_index_entry(repo, story_id)
    if not epic:
        raise ActionError(f"{story_id} has no index line under any epic")
    if any(s["id"] == story_id for s in repo.stories()):
        raise ActionError(f"{story_id} is already detailed; edit it instead")

    entry = {
        "id": story_id,
        "title": (title or index_item.get("title") or "").strip(),
        "state": "Ready",
        "emoji": STORY_STATE_EMOJI["Ready"],
        "parent": epic["id"],
        "priority": priority or index_item.get("priority") or EMPTY,
        "estimate": estimate or EMPTY,
        "area": area or epic.get("area") or EMPTY,
        "layer": layer or EMPTY,
        "assignee": _at(assignee),
        "story": story or "",
        "criteria": [c for c in (criteria or []) if str(c).strip()],
        "dependencies": [d.strip().upper() for d in (dependencies or []) if d.strip()],
        "notes": notes or "",
        # The day it became Ready: one end of cycle time. The other is Delivered.
        "ready": today(),
        "extra_blocks": [],
    }
    section = _find_state_section(repo.file("User-Stories.md"), "Ready", STORY_STATES)
    if not section:
        raise ActionError("User-Stories.md has no '## ✅ Ready' section")
    repo.append_to_section("User-Stories.md", 2,
                           lambda t: "ready" in t.lower(),
                           render.render_story(entry))
    repo.sync_epic_index(entry)
    return {"message": f"{story_id} detailed and moved to Ready",
            "id": story_id, "warnings": _dor_warnings(entry),
            "command": f"/detail-us {story_id}"}


def _dor_warnings(story: dict) -> list[str]:
    """Definition-of-Ready checks, reported rather than enforced."""
    out = []
    if not story.get("story"):
        out.append("No story sentence (As a… I want… so that…).")
    elif not re.search(r"\bas a\b.*\bi want\b", story["story"], re.IGNORECASE):
        out.append("Story sentence does not follow As a / I want / so that.")
    if not story.get("criteria"):
        out.append("No acceptance criteria.")
    else:
        loose = [c for c in story["criteria"]
                 if not re.search(r"\bgiven\b.*\bwhen\b.*\bthen\b", c, re.IGNORECASE)]
        if loose:
            out.append(f"{len(loose)} acceptance criterion/criteria are not Given/When/Then.")
    if mdutil.is_empty(story.get("estimate")):
        out.append("No estimate.")
    if mdutil.is_empty(story.get("priority")):
        out.append("No priority.")
    return out


def update_story(repo: Repo, story_id: str, **fields) -> dict:
    story = _story_by_id(repo, story_id)
    changed = []
    for key in ("title", "story", "priority", "estimate", "area", "layer",
                "notes", "reason"):
        if key in fields and fields[key] is not None:
            value = str(fields[key]).strip()
            if value != str(story.get(key) or ""):
                story[key] = value
                changed.append(key)
    if "assignee" in fields and fields["assignee"] is not None:
        story["assignee"] = _at(fields["assignee"])
        changed.append("assignee")
    if "criteria" in fields and fields["criteria"] is not None:
        story["criteria"] = [c for c in fields["criteria"] if str(c).strip()]
        changed.append("criteria")
    if "dependencies" in fields and fields["dependencies"] is not None:
        story["dependencies"] = [d.strip().upper()
                                 for d in fields["dependencies"] if d.strip()]
        changed.append("dependencies")
    if not changed:
        return {"message": "Nothing to change"}
    repo.file("User-Stories.md").replace(story["span"], render.render_story(story))
    repo.sync_epic_index(story)
    return {"message": f"{story['id']} updated ({', '.join(changed)})",
            "id": story["id"]}


def set_story_state(repo: Repo, story_id: str, state: str, reason: str = "", **_) -> dict:
    """Move a story's entry between the ``##`` state sections of User-Stories.md."""
    if state not in STORY_STATES:
        raise ActionError(f"unknown story state: {state}")
    story = _story_by_id(repo, story_id)
    if story["state"] == state:
        return {"message": f"{story['id']} is already {state}"}

    handle = repo.file("User-Stories.md")
    _remove_lines(handle, *story["span"])

    story["state"] = state
    story["emoji"] = STORY_STATE_EMOJI[state]
    if state in ("Paused", "Discarded"):
        story["reason"] = reason or story.get("reason") or EMPTY
        story["status_date"] = today()

    if not repo.append_to_section("User-Stories.md", 2,
                                  lambda t, s=state: s.lower() in t.lower(),
                                  render.render_story(story)):
        raise ActionError(f"User-Stories.md has no section for {state}")
    repo.sync_epic_index(story)
    return {"message": f"{story['id']} → {state}", "id": story["id"]}


def update_bug(repo: Repo, bug_id: str, **fields) -> dict:
    bug = next((b for b in repo.bugs() if b["id"] == bug_id.upper()), None)
    if not bug:
        raise ActionError(f"no such bug: {bug_id}")
    changed = []
    for key in ("title", "severity", "priority", "estimate", "area", "symptom",
                "expected", "actual", "assessment", "notes", "relates_to"):
        if key in fields and fields[key] is not None:
            bug[key] = str(fields[key]).strip()
            changed.append(key)
    if "assignee" in fields and fields["assignee"] is not None:
        bug["assignee"] = _at(fields["assignee"])
        changed.append("assignee")
    if "steps" in fields and fields["steps"] is not None:
        bug["steps"] = [s for s in fields["steps"] if str(s).strip()]
        bug["steps_confidence"] = "confirmed" if bug["steps"] else None
        changed.append("steps")
    if fields.get("assessment"):
        bug["assessment_confidence"] = "confirmed"

    new_state = fields.get("state")
    if new_state and new_state in BUG_STATES and new_state != bug["state"]:
        return _move_bug(repo, bug, new_state, extra_changed=changed)
    if not changed:
        return {"message": "Nothing to change"}
    repo.file("Bugs.md").replace(bug["span"], render.render_bug(bug))
    return {"message": f"{bug['id']} updated ({', '.join(changed)})", "id": bug["id"]}


def _move_bug(repo: Repo, bug: dict, state: str, extra_changed=None) -> dict:
    handle = repo.file("Bugs.md")
    _remove_lines(handle, *bug["span"])
    bug["state"] = state
    bug["emoji"] = BUG_STATE_EMOJI[state]

    def wanted(title: str) -> bool:
        low = title.lower()
        if state in ("Triaged", "Confirmed"):
            return "triaged" in low or "confirmed" in low
        if state == "In Sprint":
            return "in sprint" in low
        if state == "Fixed":
            return "fixed" in low and "won't" not in low
        return "deferred" in low or "won't" in low

    if not repo.append_to_section("Bugs.md", 2, wanted, render.render_bug(bug)):
        raise ActionError(f"Bugs.md has no section for {state}")
    return {"message": f"{bug['id']} → {state}", "id": bug["id"]}


def set_bug_state(repo: Repo, bug_id: str, state: str, **_) -> dict:
    bug = next((b for b in repo.bugs() if b["id"] == bug_id.upper()), None)
    if not bug:
        raise ActionError(f"no such bug: {bug_id}")
    if state not in BUG_STATES:
        raise ActionError(f"unknown bug state: {state}")
    if bug["state"] == state:
        return {"message": f"{bug['id']} is already {state}"}
    return _move_bug(repo, bug, state)


def _at(name) -> str:
    name = str(name or "").strip()
    if not name or name == EMPTY:
        return EMPTY
    return name if name.startswith("@") else "@" + name


# --------------------------------------------------------------------------
# Sprint
# --------------------------------------------------------------------------

def _write_board(repo: Repo, board: dict[str, list[dict]]) -> None:
    handle = repo.file("Sprint.md")
    board_span = mdutil.find_section(handle.lines, 2,
                                     lambda t: t.strip().lower() == "board")
    if not board_span:
        raise ActionError("Sprint.md has no '## Board' section")
    # Bottom-up so an earlier column's span is still valid after a later edit.
    columns = []
    for idx, title in mdutil.iter_headings(handle.lines, 3):
        if board_span[0] < idx < board_span[1]:
            name = next((c for c in BOARD_COLUMNS
                         if c.lower() == title.strip().lower()), None)
            if name:
                columns.append((idx, name))
    for idx, name in sorted(columns, reverse=True):
        span = mdutil.section_span(handle.lines, idx)
        _set_section_bullets(handle, span,
                             [render.board_line(i) for i in board.get(name, [])])


def _set_sprint_field(repo: Repo, label: str, value: str) -> None:
    handle = repo.file("Sprint.md")
    pattern = re.compile(r"^\*\*" + re.escape(label) + r":\*\*.*$")
    for i, line in enumerate(handle.lines):
        if pattern.match(line):
            handle.lines[i] = f"**{label}:** {value}"
            return


def plan_sprint(repo: Repo, name: str = "", goal: str = "", dates: str = "",
                capacity: str = "", items=None, **_) -> dict:
    """Pull Ready stories and triaged bugs onto a fresh board."""
    items = [str(i).strip().upper() for i in (items or []) if str(i).strip()]
    if not name:
        raise ActionError("the sprint needs a name, e.g. 2026-S04")

    stories = {s["id"]: s for s in repo.stories()}
    bugs = {b["id"]: b for b in repo.bugs()}
    todo, warnings = [], []

    for item_id in items:
        if item_id in stories:
            story = stories[item_id]
            if story["state"] not in ("Ready", "In Sprint"):
                warnings.append(f"{item_id} is {story['state']}, not Ready.")
            unmet = [d for d in story.get("dependencies") or []
                     if d in stories and stories[d]["state"] != "Delivered"]
            if unmet:
                warnings.append(f"{item_id} depends on {', '.join(unmet)} (not Delivered).")
            todo.append({"id": item_id, "title": story["title"],
                         "points": story.get("estimate", ""),
                         "assignee": story.get("assignee", "")})
        elif item_id in bugs:
            bug = bugs[item_id]
            if bug["state"] not in ("Triaged", "Confirmed", "In Sprint"):
                warnings.append(f"{item_id} is {bug['state']}, not pullable.")
            todo.append({"id": item_id, "title": bug["title"],
                         "points": bug.get("estimate", ""),
                         "assignee": bug.get("assignee", "")})
        else:
            raise ActionError(f"{item_id} is not a detailed story or a registered bug")

    _set_sprint_field(repo, "Sprint", name)
    _set_sprint_field(repo, "Sprint Goal", goal or EMPTY)
    _set_sprint_field(repo, "Dates", dates or EMPTY)
    _set_sprint_field(repo, "Capacity (target points)", capacity or EMPTY)
    board = {col: [] for col in BOARD_COLUMNS}
    board["To Do"] = todo
    _write_board(repo, board)

    for item_id in items:
        if item_id in stories and stories[item_id]["state"] != "In Sprint":
            set_story_state(repo, item_id, "In Sprint")
        elif item_id in bugs and bugs[item_id]["state"] != "In Sprint":
            set_bug_state(repo, item_id, "In Sprint")

    points = sum(int(i["points"]) for i in todo if str(i["points"]).strip().isdigit())
    return {"message": f"Sprint {name} planned with {len(todo)} items ({points} pts)",
            "warnings": warnings, "command": "/plan-sprint"}


def pull_into_sprint(repo: Repo, items=None, **_) -> dict:
    """Add work to the sprint already running, without disturbing the board.

    `plan_sprint` builds a board from nothing, which is right at planning time
    and wrong afterwards — it would drop everything back into To Do. Pulling in
    appends to To Do and leaves every other column exactly where it was, which
    is what both the blocked row's "pull it in" and the backlog's bulk action
    mean.
    """
    wanted = [str(i).strip().upper() for i in (items or []) if str(i).strip()]
    if not wanted:
        raise ActionError("nothing selected to pull in")

    sprint = repo.sprint()
    if mdutil.is_empty(sprint.get("name")):
        raise ActionError("there is no open sprint — run /plan-sprint first")

    board = {col: list(entries) for col, entries in sprint["board"].items()}
    on_board = {i["id"] for entries in board.values() for i in entries}
    stories = {s["id"]: s for s in repo.stories()}
    bugs = {b["id"]: b for b in repo.bugs()}

    added, skipped, warnings = [], [], []
    for item_id in wanted:
        if item_id in on_board:
            skipped.append(f"{item_id} is already on the board")
            continue
        if item_id in stories:
            story = stories[item_id]
            if story["state"] not in ("Ready", "In Sprint"):
                warnings.append(f"{item_id} is {story['state']}, not Ready.")
            unmet = [d for d in story.get("dependencies") or []
                     if d in stories and stories[d]["state"] != "Delivered"]
            if unmet:
                warnings.append(f"{item_id} depends on {', '.join(unmet)} (not Delivered).")
            board["To Do"].append({"id": item_id, "title": story["title"],
                                   "points": story.get("estimate", ""),
                                   "assignee": story.get("assignee", ""),
                                   "pulled": today()})
        elif item_id in bugs:
            bug = bugs[item_id]
            if bug["state"] not in ("Triaged", "Confirmed", "In Sprint"):
                warnings.append(f"{item_id} is {bug['state']}, not pullable.")
            board["To Do"].append({"id": item_id, "title": bug["title"],
                                   "points": bug.get("estimate", ""),
                                   "assignee": bug.get("assignee", ""),
                                   "pulled": today()})
        else:
            raise ActionError(f"{item_id} is not a detailed story or a registered bug")
        added.append(item_id)

    if added:
        _write_board(repo, board)
        for item_id in added:
            if item_id in stories and stories[item_id]["state"] != "In Sprint":
                set_story_state(repo, item_id, "In Sprint")
            elif item_id in bugs and bugs[item_id]["state"] != "In Sprint":
                set_bug_state(repo, item_id, "In Sprint")

        # Over-capacity is reported, never refused: the human decides.
        capacity = 0
        try:
            capacity = int(str(sprint.get("capacity", "")).strip())
        except (TypeError, ValueError):
            pass
        if capacity:
            total = sum(int(i["points"]) for entries in board.values() for i in entries
                        if str(i.get("points", "")).strip().isdigit())
            if total > capacity:
                warnings.append(f"The sprint now holds {total} pts against a "
                                f"{capacity} pt capacity.")

    message = (f"Pulled {len(added)} item(s) into {sprint['name']}"
               if added else "Nothing to pull in")
    if skipped:
        message += " — " + "; ".join(skipped)
    return {"message": message, "warnings": warnings, "added": added,
            "command": "/plan-sprint  (pull in)"}


def move_story_to_epic(repo: Repo, story_id: str, epic_id: str, **_) -> dict:
    """Reparent a story: its own entry, and both epics' index lines.

    The index line is a mirror of the detail entry, so moving a story means
    taking the line out of the old epic and putting it under the new one. The
    story keeps its ID, its history and its place in the lifecycle.
    """
    story_id = (story_id or "").strip().upper()
    epic_id = (epic_id or "").strip().upper()
    target = next((e for e in repo.epics() if e["id"] == epic_id), None)
    if not target:
        raise ActionError(f"no such epic: {epic_id}")

    story = next((s for s in repo.stories() if s["id"] == story_id), None)
    holders = [e for e in repo.epics()
               if any(i["id"] == story_id for i in e.get("stories") or [])]
    if not story and not holders:
        raise ActionError(f"{story_id} is not in this backlog")
    if all(e["id"] == epic_id for e in holders) and (not story or story.get("parent") == epic_id):
        return {"message": f"{story_id} is already under {epic_id}"}

    # Carry the index line across verbatim when there is no detail entry yet
    # (a Draft lives only as that line).
    carried = None
    for epic in holders:
        carried = carried or next(
            (dict(i) for i in epic["stories"] if i["id"] == story_id), None)

    handle = repo.file("Epic-Backlog.md")
    for epic in sorted(holders, key=lambda e: e["span"][0], reverse=True):
        if epic["id"] == epic_id:
            continue
        epic["stories"] = [i for i in epic["stories"] if i["id"] != story_id]
        handle.replace(epic["span"], render.render_epic(epic))

    if story:
        story["parent"] = epic_id
        repo.file("User-Stories.md").replace(story["span"], render.render_story(story))
        repo.sync_epic_index(story)
    elif carried:
        fresh = next((e for e in repo.epics() if e["id"] == epic_id), None)
        index = [dict(i) for i in fresh.get("stories") or []]
        if not any(i["id"] == story_id for i in index):
            index.append(carried)
        index.sort(key=lambda i: id_rank(i["id"]))
        fresh["stories"] = index
        repo.file("Epic-Backlog.md").replace(fresh["span"], render.render_epic(fresh))

    moved_from = ", ".join(e["id"] for e in holders if e["id"] != epic_id) or "nowhere"
    return {"message": f"{story_id} moved from {moved_from} to {epic_id}",
            "id": story_id}


def move_board_item(repo: Repo, item_id: str, column: str, **_) -> dict:
    """Move one item between board columns (``/start-us`` … ``/done-us``)."""
    item_id = (item_id or "").strip().upper()
    if column not in BOARD_COLUMNS:
        raise ActionError(f"unknown board column: {column}")

    sprint = repo.sprint()
    board = {col: list(items) for col, items in sprint["board"].items()}
    found = None
    for col, items in board.items():
        for item in items:
            if item["id"] == item_id:
                found = item
                board[col] = [i for i in items if i["id"] != item_id]
                break
        if found:
            break
    if not found:
        raise ActionError(f"{item_id} is not on the board")

    warnings = []
    if column == "In Progress":
        stories = {s["id"]: s for s in repo.stories()}
        unmet = [d for d in (stories.get(item_id, {}).get("dependencies") or [])
                 if d in stories and stories[d]["state"] != "Delivered"]
        if unmet:
            warnings.append(f"Dependency gate: {', '.join(unmet)} not Delivered.")

    board[column].append(found)
    _write_board(repo, board)

    # Started goes on the item's own entry, not the board line: the board is
    # rebuilt at every sprint and the entry is where the date has to outlive
    # it. First time only — a card bounced back to To Do and started again
    # keeps the day the work really began.
    if column == "In Progress":
        _stamp_started(repo, item_id)

    result = {"message": f"{item_id} → {column}", "warnings": warnings,
              "branch": _branch_name(repo, item_id)}
    if column == "In Progress":
        result["command"] = f"/start-us {item_id}" if item_id.startswith("US") \
            else f"/start-bug {item_id}"
    return result


def _stamp_started(repo: Repo, item_id: str) -> None:
    """Write ``Started: <today>`` on a story or bug that has none yet."""
    for story in repo.stories():
        if story["id"] == item_id:
            if not story.get("started"):
                story["started"] = today()
                repo.file("User-Stories.md").replace(story["span"], render.render_story(story))
            return
    for bug in repo.bugs():
        if bug["id"] == item_id:
            if not bug.get("started"):
                bug["started"] = today()
                repo.file("Bugs.md").replace(bug["span"], render.render_bug(bug))
            return


def _branch_name(repo: Repo, item_id: str) -> str:
    title = ""
    for story in repo.stories():
        if story["id"] == item_id:
            title = story["title"]
    for bug in repo.bugs():
        if bug["id"] == item_id:
            title = bug["title"]
    return f"{item_id.lower()}-{slugify(title)}"


def set_blocked(repo: Repo, item_id: str, reason: str = "", blocked: bool = True, **_) -> dict:
    item_id = (item_id or "").strip().upper()
    sprint = repo.sprint()
    previous = next((b for b in sprint["blocked"] if b["id"] == item_id), None)
    entries = [b for b in sprint["blocked"] if b["id"] != item_id]
    title = ""
    for items in sprint["board"].values():
        for item in items:
            if item["id"] == item_id:
                title = item["title"]
    if blocked:
        # Editing the reason must not reset the clock: blocked time is
        # measured from the day the flag first went up.
        since = (previous or {}).get("since") or today()
        entries.append({"id": item_id, "title": title,
                        "reason": reason or "blocked", "since": since})

    handle = repo.file("Sprint.md")
    span = mdutil.find_section(handle.lines, 2, lambda t: "blocked" in t.lower())
    if not span:
        raise ActionError("Sprint.md has no '## 🚧 Blocked' section")
    _set_section_bullets(handle, span, [render.blocked_line(e) for e in entries])
    return {"message": f"{item_id} {'flagged blocked' if blocked else 'unblocked'}"}


def complete_item(repo: Repo, item_id: str, pr: str = "", commit: str = "", **_) -> dict:
    """In PR → Done: board, the item's own entry, and the Increment line."""
    item_id = (item_id or "").strip().upper()
    sprint = repo.sprint()
    name = sprint.get("name", EMPTY)
    trace = " · ".join(p for p in [f"PR {pr}" if pr else "", commit] if p)
    stamp = f"{today()} · sprint {name}" + (f" · _({trace})_" if trace else "")

    move_board_item(repo, item_id, "Done")

    if item_id.startswith("BUG"):
        bug = next((b for b in repo.bugs() if b["id"] == item_id), None)
        if not bug:
            raise ActionError(f"no such bug: {item_id}")
        bug["fixed"] = stamp
        repo.file("Bugs.md").replace(bug["span"], render.render_bug(bug))
        _move_bug(repo, next(b for b in repo.bugs() if b["id"] == item_id), "Fixed")
        title = bug["title"]
        tag = " — **Fixed**"
    else:
        title = _story_by_id(repo, item_id)["title"]
        # Move to the Delivered section first; only then stamp the delivery
        # line and collapse the criteria, because the "all met ✓" shape only
        # applies to a Delivered entry and a later re-render would drop it.
        set_story_state(repo, item_id, "Delivered")
        story = _story_by_id(repo, item_id)
        story["delivered"] = stamp
        story["criteria_met"] = True
        repo.file("User-Stories.md").replace(story["span"], render.render_story(story))
        tag = ""

    epic_id = ""
    for epic in repo.epics():
        if any(i["id"] == item_id for i in epic.get("stories") or []):
            epic_id = epic["id"]
    suffix = f" ({epic_id})" if epic_id else ""
    inc = f"- {link(item_id)} {mdutil.DASH} {title}{suffix} {mdutil.DASH} {today()}"
    if pr:
        inc += f" {mdutil.DASH} PR {pr}"
    inc += tag
    repo.append_to_section("Releases.md", 2, lambda t: "increment" in t.lower(), [inc])

    return {"message": f"{item_id} is Done and recorded in the Increment",
            "command": f"/done-us {item_id}" if item_id.startswith("US")
                       else f"/done-bug {item_id}"}


def close_sprint(repo: Repo, retro_kept: str = "", retro_try: str = "", **_) -> dict:
    """Record velocity and the sprint in history; send unfinished work back."""
    sprint = repo.sprint()
    name = sprint.get("name", EMPTY)
    if mdutil.is_empty(name):
        raise ActionError("there is no open sprint to close")

    board = sprint["board"]
    done = board.get("Done", [])
    unfinished = [i for col in BOARD_COLUMNS if col != "Done" for i in board[col]]

    def pts(items):
        return sum(int(i["points"]) for i in items if str(i["points"]).strip().isdigit())

    velocity = pts(done)
    committed = velocity + pts(unfinished)
    pulled = [i for col in BOARD_COLUMNS for i in board.get(col, []) if i.get("pulled")]

    entry = [
        f'## {name} {mdutil.DASH} "{sprint.get("goal", "") or ""}" '
        f'({sprint.get("dates", EMPTY)})',
        f"Goal: {sprint.get('goal', EMPTY)}",
        f"Committed: {committed} pts · Completed: {velocity} pts → **velocity {velocity}**",
        f"Delivered: {', '.join(i['id'] for i in done) if done else EMPTY}",
        f"Carried over: {', '.join(i['id'] for i in unfinished) if unfinished else EMPTY}",
        # Scope change is only knowable later if it is written down now: the
        # board is rebuilt next sprint and the `pulled` stamps go with it.
        f"Pulled in: {', '.join(i['id'] for i in pulled) if pulled else EMPTY}"
        + (f" ({pts(pulled)} pts)" if pulled else ""),
        "Retro notes:",
        f"- Kept: {retro_kept}",
        f"- Try: {retro_try}",
        "",
    ]
    handle = repo.file("Sprints-History.md")
    at = len(handle.lines)
    for i, line in enumerate(handle.lines):
        if mdutil.is_rule(line):
            at = i + 1
            break
    while at < len(handle.lines) and not handle.lines[at].strip():
        at += 1
    handle.insert(at, entry)

    for item in unfinished:
        if item["id"].startswith("US"):
            set_story_state(repo, item["id"], "Ready")
        else:
            set_bug_state(repo, item["id"], "Confirmed")

    _write_board(repo, {col: [] for col in BOARD_COLUMNS})
    _set_sprint_field(repo, "Sprint", "_none yet_ — run `/plan-sprint` to start one.")
    _set_sprint_field(repo, "Sprint Goal", EMPTY)
    _set_sprint_field(repo, "Dates", EMPTY)
    _set_sprint_field(repo, "Capacity (target points)", EMPTY)

    span = mdutil.find_section(repo.file("Sprint.md").lines, 2,
                               lambda t: "blocked" in t.lower())
    if span:
        _set_section_bullets(repo.file("Sprint.md"), span, [])

    _update_rolling_velocity(repo)
    return {"message": f"Sprint {name} closed — velocity {velocity}, "
                       f"{len(unfinished)} item(s) returned to the backlog",
            "command": "/close-sprint"}


def _update_rolling_velocity(repo: Repo) -> None:
    sprints = repo.history()["sprints"][:3]
    values = [int(s["velocity"]) for s in sprints if str(s["velocity"]).isdigit()]
    average = str(round(sum(values) / len(values))) if values else EMPTY
    handle = repo.file("Sprints-History.md")
    for i, line in enumerate(handle.lines):
        if line.startswith("**Rolling velocity"):
            handle.lines[i] = f"**Rolling velocity (last 3 sprints):** {average}"
            return


# --------------------------------------------------------------------------
# Release
# --------------------------------------------------------------------------

def cut_release(repo: Repo, version: str = "", title: str = "", theme: str = "", **_) -> dict:
    releases = repo.releases()
    increment = releases["increment"]
    if not increment:
        raise ActionError("the Increment is empty — nothing to release")

    if not version:
        latest = releases["versions"][0]["version"] if releases["versions"] else "v0.0"
        m = re.match(r"v?(\d+)\.(\d+)", latest)
        major, minor = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        version = f"v{major}.{minor + 1}"
    if not version.startswith("v"):
        version = "v" + version

    ids = [i["id"] for i in increment if i["id"]]
    epics = sorted({e["id"] for e in repo.epics()
                    for s in e.get("stories") or [] if s["id"] in ids})

    entry = [
        f"### {version} {mdutil.DASH} {title or 'Release'} ({today()})",
        f"Theme: {theme or EMPTY}",
        f"Stories: {', '.join(ids) if ids else EMPTY}",
        f"Epics touched: {', '.join(epics) if epics else EMPTY}",
        "",
    ]
    handle = repo.file("Releases.md")
    span = mdutil.find_section(handle.lines, 2, lambda t: "version history" in t.lower())
    if not span:
        raise ActionError("Releases.md has no '## Version history' section")
    at = span[0] + 1
    while at < span[1] and (not handle.lines[at].strip()
                            or handle.lines[at].lstrip().startswith("_")):
        at += 1
    handle.insert(at, entry)

    inc_span = mdutil.find_section(handle.lines, 2, lambda t: "increment" in t.lower())
    if inc_span:
        _set_section_bullets(handle, inc_span, [])

    return {"message": f"{version} cut with {len(ids)} item(s)",
            "version": version, "command": f"/release {version}"}


# --------------------------------------------------------------------------
# Ledger git
# --------------------------------------------------------------------------

def _set_fenced_keys(lines: list[str], updates: dict) -> bool:
    """Set ``key: value`` inside the first fenced block, keeping its shape.

    The config blocks are written for a human to read — aligned values, a
    trailing comment on most lines. Rewriting the block would throw that away,
    so only the value is replaced, in place, with the comment carried over and
    the column kept where it was.
    """
    changed = False
    in_fence = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if in_fence:
                break
            in_fence = True
            continue
        if not in_fence:
            continue
        body, hash_, comment = line.partition("#")
        m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:\s*)(.*?)(\s*)$", body)
        if not m:
            continue
        key = m.group(2)
        if key not in updates:
            continue
        new_value = str(updates[key]).strip()
        if new_value == m.group(4).strip():
            continue
        rebuilt = f"{m.group(1)}{key}{m.group(3)}{new_value}"
        if hash_:
            # Keep the comment where it sat, when the new value still fits.
            pad = max(1, len(body) - len(rebuilt))
            rebuilt = rebuilt + " " * pad + hash_ + comment
        lines[i] = rebuilt.rstrip() if not hash_ else rebuilt
        changed = True
    # A key the block has never carried is appended inside the fence rather
    # than dropped: a ledger written before a key existed would otherwise be
    # unable to ever set it from here, and the drop was silent.
    present = set()
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_fence:
                break
            in_fence = True
            continue
        if in_fence:
            m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
            if m:
                present.add(m.group(1))
    missing = [k for k in updates if k not in present and str(updates[k]).strip()]
    if missing:
        close = next(i for i, l in enumerate(lines) if l.strip().startswith("```") and i > 0
                     and any(x.strip().startswith("```") for x in lines[:i]))
        lines[close:close] = [f"{k}: {str(updates[k]).strip()}" for k in missing]
        changed = True
    return changed


def update_project_config(repo: Repo, values=None, **_) -> dict:
    """The per-project settings in this repo folder's `Definitions.md`."""
    values = {k: v for k, v in (values or {}).items() if v is not None}
    if not values:
        return {"message": "Nothing to change"}
    handle = repo.file("Definitions.md")
    if not handle.exists:
        raise ActionError("this repo folder has no Definitions.md")
    if not _set_fenced_keys(handle.lines, values):
        return {"message": "Nothing to change"}
    return {"message": f"Updated {', '.join(sorted(values))} in Definitions.md",
            "command": "(edit Definitions.md)"}


def _root_config(repo: Repo) -> tuple:
    """``(path, lines)`` for the ledger root's Config.md, which sits outside Repo.

    The eight files go through `Repo`'s handles and its atomic save; Config.md
    belongs to the ledger rather than to any one project, so it is read and
    written here.
    """
    path = repo.root / "Config.md"
    if not path.is_file():
        raise ActionError("this ledger has no Config.md")
    return path, mdutil.split_lines(path.read_text(encoding="utf-8"))


def _write_text(path, text: str) -> None:
    """Write one file the way `Repo.save` writes the eight: temp file + replace.

    An interrupted write cannot leave half a file behind, which matters as much
    for the files at the ledger root as for the eight inside a repo folder.
    """
    if not text.endswith("\n"):
        text += "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _save_root_config(path, lines: list[str]) -> None:
    """Write Config.md back after an in-place edit of its lines."""
    _write_text(path, "\n".join(lines))


def update_ledger_config(repo: Repo, values=None, **_) -> dict:
    """The ledger-wide settings in the root's `Config.md`."""
    values = {k: v for k, v in (values or {}).items() if v is not None}
    if not values:
        return {"message": "Nothing to change"}
    path, lines = _root_config(repo)
    if not _set_fenced_keys(lines, values):
        return {"message": "Nothing to change"}
    _save_root_config(path, lines)
    return {"message": f"Updated {', '.join(sorted(values))} in Config.md",
            "command": "(edit Config.md)"}


TEAM_BLURB = ("Who is on this team, and in which role. A roster, not a permission "
              "list: anyone who can read this repo can edit it. What it governs is "
              "who CODEOWNERS asks to approve a change to the rules.")


def update_team(repo: Repo, people=None, **_) -> dict:
    """Rewrite the `## Team` roster in the ledger root's `Config.md`.

    Writes the section if the ledger predates it, placing it above `## Notes`
    so the prose stays last. An empty roster is allowed and leaves the table
    with its headings only — a team that has not written one down is the
    default state, not an error.
    """
    from .model import normalise_role

    rows = []
    for entry in (people or []):
        name = str((entry or {}).get("name", "")).strip()
        if not name or name == EMPTY:
            continue
        role = normalise_role((entry or {}).get("role", ""))
        handle = str((entry or {}).get("handle", "")).strip().lstrip("@")
        rows.append([name, role or EMPTY, _at(handle)])

    path, lines = _root_config(repo)
    table = mdutil.render_table(["Name", "Role", "GitHub"], rows)
    span = mdutil.find_section(lines, 2, lambda t: t.strip().lower() == resolve.TEAM_HEADING)

    if span:
        start, end = span
        inner = mdutil.find_table(lines, start, end)
        if inner:
            # Keep whatever prose the team wrote around their own roster.
            lines[inner[0]:inner[1]] = table
        else:
            body = mdutil.trim_span(lines, start + 1, end)
            lines[body[1]:body[1]] = ([""] if body[1] > body[0] else []) + table
    else:
        notes = mdutil.find_section(lines, 2, lambda t: t.strip().lower() == "notes")
        block = ["## Team", "", TEAM_BLURB, "", *table]
        at = notes[0] if notes else len(lines)
        while at > 0 and not lines[at - 1].strip():
            at -= 1                      # sit one blank line below what precedes it
        # A blank line after it only when something follows; at EOF it would
        # just be trailing whitespace.
        lines[at:at] = ["", *block] + ([""] if notes else [])

    _save_root_config(path, lines)
    return {"message": (f"Team roster saved ({len(rows)} "
                        f"{'person' if len(rows) == 1 else 'people'})"),
            "command": "(edit Config.md)"}


#: `Me.local.md`, written whole each time — it holds one person, so there is
#: no hand-written content around it to preserve.
ME_TEMPLATE = """# Me (local)

> Who you are **on this machine**. `.gitignore` keeps this file out of git, so your name never
> lands in a commit and never overwrites a teammate's — every clone has its own.
>
> Matched against the `## Team` roster in `Config.md`, where a handle and a display name are the
> same person. Clear it from the dashboard, or delete the file, to be asked again.

```
name:   {name}
handle: {handle}
```
"""

IGNORE_NOTE = "# Who you are is yours, not the team's — never commit it."


def _ensure_ignored(root, name: str) -> bool:
    """Add ``name`` to the ledger root's `.gitignore` unless it is covered.

    True when the file was changed. The entry goes at the **ledger root** in
    both placements: git honours a `.gitignore` in a subdirectory, so a flat
    ledger living inside its project never needs the project's own file
    touched. Without this the identity file is the next thing someone commits,
    and the problem it solves comes straight back.
    """
    path = root / ".gitignore"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    for line in lines:
        entry = line.strip()
        if entry.startswith("#"):
            continue
        if entry.lstrip("/") == name:
            return False
    block = ([""] if lines and lines[-1].strip() else []) + [IGNORE_NOTE, name]
    _write_text(path, "\n".join(lines + block))
    return True


def update_me(repo: Repo, name=None, handle=None, **_) -> dict:
    """Record who the person at this clone is, in the git-ignored `Me.local.md`.

    This is the one setting that must *not* be shared. `Me:` in a project's
    `Definitions.md` is committed with everything else, so a team all writing
    their own name there take turns overwriting each other — and in a ledger
    whose `Definitions.md` is under CODEOWNERS, a developer cannot land the
    correction at all. Here each clone answers for itself.

    Clearing both fields removes the file. That is not the never-delete rule
    bending: the rule protects what a human recorded about the *product*, and
    this holds one machine's note about itself, which the dashboard offers to
    forget so the next session asks again.
    """
    name = str(name or "").strip()
    handle = str(handle or "").strip().lstrip("@")
    if name == EMPTY:
        name = ""
    path = repo.root / resolve.ME_FILE

    if not name and not handle:
        if not path.is_file():
            return {"message": "Nothing to change"}
        path.unlink()
        return {"message": "Forgot who you are on this machine",
                "command": f"(delete {resolve.ME_FILE})"}

    # A handle alone is enough to ask the roster for the display name, which is
    # what every view shows; the reverse holds too.
    person = resolve.identify(repo.root, handle or name)
    if person:
        name = name or person["name"]
        handle = handle or person["handle"]

    _write_text(path, ME_TEMPLATE.format(name=name or EMPTY, handle=_at(handle)))
    ignored = _ensure_ignored(repo.root, resolve.ME_FILE)
    who = name or f"@{handle}"
    return {"message": f"You are {who} on this machine"
                       + (" · added to .gitignore" if ignored else ""),
            "command": f"(edit {resolve.ME_FILE})"}


def update_checklist(repo: Repo, which: str = "", items=None, **_) -> dict:
    """Rewrite the Definition of Ready or Done in `Definitions.md`.

    These are the team's own words and the gate every command quotes, so they
    are editable here rather than only in the file — but the shape stays the
    ledger's: one `- [ ]` bullet per line, under the heading it already has.
    """
    which = (which or "").strip().lower()
    heading = {"ready": "definition of ready", "done": "definition of done"}.get(which)
    if not heading:
        raise ActionError("which must be 'ready' or 'done'")
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        raise ActionError("a checklist needs at least one line")

    handle = repo.file("Definitions.md")
    span = mdutil.find_section(handle.lines, 2, lambda t: heading in t.lower())
    if not span:
        raise ActionError(f"Definitions.md has no {heading} section")

    start, end = span
    # Keep the prose that introduces the list; replace only the bullets.
    keep, seen_bullet = [], False
    mask = mdutil.comment_mask(handle.lines)
    for i in range(start + 1, end):
        line = handle.lines[i]
        if not mask[i] and re.match(r"^\s{0,3}[-*]\s+", line):
            seen_bullet = True
            continue
        if seen_bullet and not line.strip():
            continue
        keep.append(line)
    while keep and not keep[-1].strip():
        keep.pop()

    body = keep + [""] + [f"- [ ] {item}" for item in items] + [""]
    handle.replace((start + 1, end), body)
    return {"message": f"Definition of {which.title()} updated ({len(items)} items)",
            "command": "(edit Definitions.md)"}


def _git(root, *args, timeout=30) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, timeout=timeout)


def ledger_status(root) -> dict:
    """Porcelain status of the ledger repo, for the commit panel."""
    try:
        inside = _git(root, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0:
            return {"git": False, "reason": "the ledger root is not a git repository"}
        status = _git(root, "status", "--porcelain")
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
        changes = [l for l in status.stdout.splitlines() if l.strip()]
        return {"git": True, "branch": branch.stdout.strip(),
                "changes": changes, "dirty": bool(changes)}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"git": False, "reason": str(exc)}


def commit_ledger(repo: Repo, message: str = "", **_) -> dict:
    """Commit this repo folder only, the way `/ledger-commit` scopes it.

    Never pushes: `Config.md` keeps `ledger_push` off by default and the skill
    treats a push as a separate, explicitly confirmed act.
    """
    root = repo.root
    state = ledger_status(root)
    if not state.get("git"):
        raise ActionError(state.get("reason", "not a git repository"))
    if not state.get("dirty"):
        return {"message": "Nothing to commit — the ledger is clean"}

    message = (message or f"ledger({repo.slug}): dashboard update").strip()
    add = _git(root, "add", "--", repo.slug)
    if add.returncode != 0:
        raise ActionError(f"git add failed: {add.stderr.strip()}")
    staged = _git(root, "diff", "--cached", "--name-only")
    if not staged.stdout.strip():
        return {"message": f"Nothing staged under {repo.slug}/"}
    done = _git(root, "commit", "-m", message)
    if done.returncode != 0:
        raise ActionError(f"git commit failed: {done.stderr.strip() or done.stdout.strip()}")
    return {"message": f"Committed {len(staged.stdout.split())} file(s)",
            "detail": done.stdout.strip(), "command": "/ledger-commit"}


# --------------------------------------------------------------------------
# Audit (read-only)
# --------------------------------------------------------------------------

def check_ledger(repo: Repo, **_) -> dict:
    """The mechanical half of `/ledger-check`: drift, orphans, broken links."""
    issues = []
    stories = {s["id"]: s for s in repo.stories()}
    bugs = {b["id"]: b for b in repo.bugs()}
    epics = repo.epics()

    indexed = {}
    for epic in epics:
        for item in epic.get("stories") or []:
            if item["id"] in indexed:
                issues.append(f"{item['id']} is indexed under two epics "
                              f"({indexed[item['id']]} and {epic['id']}).")
            indexed[item["id"]] = epic["id"]

    for story_id, story in stories.items():
        if story_id not in indexed:
            issues.append(f"{story_id} has a detail entry but no epic index line.")
        elif story.get("parent") and story["parent"] != indexed[story_id]:
            issues.append(f"{story_id} says Parent {story['parent']} but is indexed "
                          f"under {indexed[story_id]}.")
        for dep in story.get("dependencies") or []:
            if dep not in stories:
                issues.append(f"{story_id} depends on {dep}, which has no detail entry.")

    for item_id, epic_id in indexed.items():
        item = next(i for e in epics for i in e.get("stories") or []
                    if i["id"] == item_id)
        state = item.get("state") or ""
        if "Draft" in state:
            if item_id in stories:
                issues.append(f"{item_id} is indexed Draft but has a detail entry.")
        elif item_id not in stories:
            issues.append(f"{item_id} is indexed {state.strip()} but has no detail entry.")
        else:
            coarse = STORY_STATE_LABEL.get(stories[item_id]["state"], "")
            if coarse and coarse not in state:
                issues.append(f"{item_id}: epic index says {state.strip()}, "
                              f"detail says {stories[item_id]['state']}.")

    sprint = repo.sprint()
    for column, items in sprint["board"].items():
        for item in items:
            if item["id"].startswith("US"):
                if item["id"] not in stories:
                    issues.append(f"{item['id']} is on the board but has no story entry.")
                elif stories[item["id"]]["state"] not in ("In Sprint", "Delivered"):
                    issues.append(f"{item['id']} is on the board ({column}) but its state "
                                  f"is {stories[item['id']]['state']}.")
            elif item["id"] not in bugs:
                issues.append(f"{item['id']} is on the board but has no bug entry.")

    for entry in repo.releases()["increment"]:
        if entry["id"] and entry["id"] not in stories and entry["id"] not in bugs:
            issues.append(f"Increment line references unknown {entry['id']}.")

    for kind, known in (("EPIC", [e["id"] for e in epics]),
                        ("US", list(stories) + list(indexed)),
                        ("BUG", list(bugs))):
        counter = repo.next_ids().get(kind) if kind != "BUG" else None
        if counter and known and id_rank(counter) <= max(id_rank(i) for i in known):
            issues.append(f"Next free ID for {kind} is {counter}, "
                          f"but {kind}-{max(id_rank(i) for i in known):03d} already exists.")

    return {"message": f"{len(issues)} issue(s) found" if issues else "No drift found",
            "issues": issues, "command": "/ledger-check"}


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

#: Actions that write nothing inside a repo folder, so the eight files are
#: neither rebuilt nor saved afterwards. `check` only reads; the other three
#: write at the ledger root. Rebuilding for them would mean a developer who
#: did nothing but say who they are finds three ledger files rewritten,
#: because a rebuild corrects every stale derived table it meets — true, and
#: nothing to do with what they asked for. `/ledger-check` is where that
#: correction belongs.
OUTSIDE_THE_EIGHT = {"check", "update_me", "update_team", "update_ledger_config"}

ACTIONS = {
    "add_idea": add_idea,
    "add_bug": add_bug,
    "discard_idea": discard_idea,
    "triage_idea_to_epic": triage_idea_to_epic,
    "triage_idea_to_story": triage_idea_to_story,
    "triage_bug": triage_bug,
    "detail_story": detail_story,
    "update_story": update_story,
    "set_story_state": set_story_state,
    "update_bug": update_bug,
    "set_bug_state": set_bug_state,
    "plan_sprint": plan_sprint,
    "pull_into_sprint": pull_into_sprint,
    "move_story_to_epic": move_story_to_epic,
    "move_board_item": move_board_item,
    "set_blocked": set_blocked,
    "complete_item": complete_item,
    "close_sprint": close_sprint,
    "cut_release": cut_release,
    "commit": commit_ledger,
    "check": check_ledger,
    "update_project_config": update_project_config,
    "update_ledger_config": update_ledger_config,
    "update_team": update_team,
    "update_me": update_me,
    "update_checklist": update_checklist,
}


def run(repo: Repo, action: str, params: dict) -> dict:
    """Run one action, rebuild derived data, and write the files atomically."""
    if action not in ACTIONS:
        raise ActionError(f"unknown action: {action}")
    result = ACTIONS[action](repo, **(params or {}))
    if action in OUTSIDE_THE_EIGHT:
        return result
    repo.rebuild_overviews()
    result["files_written"] = repo.save()
    return result
