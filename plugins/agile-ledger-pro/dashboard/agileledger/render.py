"""Writers for ledger entries and the derived overview tables.

Shapes follow `references/entry-templates.md` exactly, including its
readability rule: every metadata field is its own bulleted line and logical
sections are separated by a blank line, because a single line break collapses
in Markdown preview.

The overview tables and epic rollups are rebuilt from the entries rather than
edited in place — `SKILL.md` calls them "derived, never hand-typed", and
recomputing them is the one part of this job a program does better than a
human editing by hand.
"""

from __future__ import annotations

import re

from . import mdutil
from .model import (BOARD_COLUMNS, BUG_STATE_EMOJI, BUG_STATE_LABEL, BUG_STATES,
                    EMPTY, EPIC_STATE_EMOJI, EPIC_STATE_LABEL, PRIORITIES,
                    STORY_STATE_EMOJI, STORY_STATE_LABEL, STORY_STATES,
                    anchor, id_rank, link, priority_rank)

SEP = "  " + mdutil.MIDDOT + "  "     # the wide separator on a title line
DOT = " " + mdutil.MIDDOT + " "       # the inline separator inside a field
DASH = mdutil.DASH


def _v(value) -> str:
    """Render a value for display, never leaving a cell blank."""
    text = ("" if value is None else str(value)).strip()
    return text if text else EMPTY


def _points(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------
# Story entry
# --------------------------------------------------------------------------

def render_story(story: dict) -> list[str]:
    state = story.get("state", "Ready")
    emoji = story.get("emoji") or STORY_STATE_EMOJI.get(state, STORY_STATE_EMOJI["Ready"])
    head = f"**{_v(story.get('title'))}** {emoji}"
    if story.get("parent"):
        head += SEP + "Parent: " + link(story["parent"])

    out = [f"#### {story['id']}", "", head, ""]

    if state in ("Paused", "Discarded"):
        label = "Paused" if state == "Paused" else "Discarded"
        when = story.get("status_date") or ""
        out.append(f"- **Status:** {label}{f' ({when})' if when else ''}")
        out.append(f"- **Reason:** {_v(story.get('reason'))}")
    else:
        out += [
            f"- **Priority:** {_v(story.get('priority'))}",
            f"- **Estimate:** {_v(story.get('estimate'))}",
            f"- **Area:** {_v(story.get('area'))}",
            f"- **Layer:** {_v(story.get('layer'))}",
            f"- **Assignee:** {_v(story.get('assignee'))}",
        ]
    out.append("")

    if story.get("story"):
        out += [f"**Story** {DASH} {story['story']}", ""]

    criteria = [c for c in story.get("criteria") or [] if c.strip()]
    if state == "Delivered" and story.get("criteria_met"):
        out += ["**Acceptance criteria:** all met ✓", ""]
    elif criteria:
        out += ["**Acceptance criteria** _(Given / When / Then)_", ""]
        out += [f"- {c}" for c in criteria]
        out.append("")

    deps = story.get("dependencies") or []
    out += [f"**Dependencies:** {DOT.join(link(d) for d in deps) if deps else EMPTY}", ""]

    if story.get("delivered"):
        out += [f"**Delivered:** {story['delivered']}", ""]

    for block in story.get("extra_blocks") or []:
        out += _render_extra(block)

    out.append(f"**Notes:** {_v(story.get('notes'))}")
    return out


def _render_extra(block: dict) -> list[str]:
    """Write back a prose block this module does not model, unchanged."""
    head = f"**{block['label']}**"
    if block.get("inline"):
        head += f" {DASH} {block['inline']}"
    out = [head]
    body = [l for l in (block.get("body") or [])]
    while body and not body[-1].strip():
        body.pop()
    if body:
        out += body
    out.append("")
    return out


# --------------------------------------------------------------------------
# Epic entry
# --------------------------------------------------------------------------

def render_epic(epic: dict) -> list[str]:
    roll = epic.get("rollup") or {}
    emoji = epic.get("emoji") or EPIC_STATE_EMOJI["Proposed"]
    meta = []
    if epic.get("target") and epic["target"] != EMPTY:
        meta.append(f"target {epic['target']}")
    meta.append(f"{roll.get('stories_done', 0)}/{roll.get('stories_total', 0)} stories")
    meta.append(f"{roll.get('points_done', 0)}/{roll.get('points_total', 0)} pts")

    out = [
        f"### {epic['id']}",
        "",
        f"**{_v(epic.get('title'))}** {emoji}" + SEP + DOT.join(meta),
        "",
        f"**Goal:** {_v(epic.get('goal'))}",
        "",
        f"**Area:** {_v(epic.get('area'))}",
        "",
        "**History:**",
        "",
    ]
    out += [f"- {h}" for h in epic.get("history") or []]
    if epic.get("history"):
        out.append("")
    out += ["**Stories:**", ""]
    out += [story_index_line(s) for s in epic.get("stories") or []]
    return out


def story_index_line(item: dict) -> str:
    """``- [US-012](User-Stories.md#us-012) · Email signup · ✅ Delivered · 🔴 · 5 pts · @rita``"""
    parts = [link(item["id"]), _v(item.get("title"))]
    state = item.get("state") or ""
    parts.append(state if state else STORY_STATE_LABEL["Draft"])
    if item.get("priority") and item["priority"] != EMPTY:
        parts.append(item["priority"])
    if item.get("points") and str(item["points"]).strip() not in ("", EMPTY):
        parts.append(f"{item['points']} pts")
    if item.get("assignee") and item["assignee"] != EMPTY:
        assignee = item["assignee"]
        parts.append(assignee if assignee.startswith("@") else "@" + assignee)
    return "- " + DOT.join(parts)


# --------------------------------------------------------------------------
# Bug entry
# --------------------------------------------------------------------------

def render_bug(bug: dict) -> list[str]:
    state = bug.get("state", "Triaged")
    emoji = bug.get("emoji") or BUG_STATE_EMOJI.get(state, BUG_STATE_EMOJI["Triaged"])
    head = f"**{_v(bug.get('title'))}** {emoji}"
    if bug.get("relates_to"):
        head += SEP + "relates to " + link(bug["relates_to"])
    elif bug.get("has_relates_meta"):
        head += SEP + "relates to " + EMPTY

    out = [
        f"### {bug['id']}",
        "",
        head,
        "",
        f"- **Severity:** {_v(bug.get('severity'))}",
        f"- **Priority:** {_v(bug.get('priority'))}",
        f"- **State:** {state}",
        f"- **Estimate:** {_v(bug.get('estimate'))}",
        f"- **Reported by:** {_v(bug.get('reported_by'))}",
        f"- **Area:** {_v(bug.get('area'))}",
        f"- **Assignee:** {_v(bug.get('assignee'))}",
        "",
        f"**Symptom** {DASH} {_v(bug.get('symptom'))}",
        "",
    ]

    steps = [s for s in bug.get("steps") or [] if s.strip()]
    confidence = bug.get("steps_confidence") or ("confirmed" if steps else "unconfirmed — needs input")
    out.append(f"**Steps to reproduce** _({confidence})_")
    out.append("")
    if steps:
        out += [f"{n}. {s}" for n, s in enumerate(steps, 1)]
        out.append("")

    out += [f"**Expected:** {_v(bug.get('expected'))}", ""]
    out += [f"**Actual:** {_v(bug.get('actual'))}", ""]

    assessment = bug.get("assessment")
    label = bug.get("assessment_confidence") or ("confirmed" if assessment else "pending /find-bug")
    if assessment:
        out += [f"**Assessment** _({label})_ {DASH} {assessment}", ""]
    else:
        out += [f"**Assessment** _({label})_", ""]

    if bug.get("fixed"):
        out += [f"**Fixed:** {bug['fixed']}", ""]

    for block in bug.get("extra_blocks") or []:
        out += _render_extra(block)

    out.append(f"**Notes:** {_v(bug.get('notes'))}")
    return out


# --------------------------------------------------------------------------
# Derived: Epic-Backlog.md overview
# --------------------------------------------------------------------------

EPIC_HEADERS = ["Epic", "Title", "Status", "Stories (done/total)", "Points (done/total)", "Target"]
_EPIC_ORDER = {"Proposed": 0, "In Progress": 0, "Done": 1, "Paused": 2, "Discarded": 2}


def epic_state_from_emoji(emoji: str) -> str:
    for name, glyph in EPIC_STATE_EMOJI.items():
        if emoji and glyph and emoji.startswith(glyph[0]):
            return name
    return "Proposed"


def derive_epic_state(epic: dict) -> str:
    """Epic status comes from its children, as the templates require."""
    states = [(s.get("state") or "") for s in epic.get("stories") or []]
    if not states:
        return "Proposed"
    if all("Discarded" in s for s in states):
        return "Discarded"
    live = [s for s in states if "Discarded" not in s]
    if live and all("Delivered" in s for s in live):
        return "Done"
    if any(("In Sprint" in s) or ("Delivered" in s) for s in states):
        return "In Progress"
    if live and all("Paused" in s for s in live):
        return "Paused"
    return "Proposed"


def epic_rollup(epic: dict, stories_by_id: dict) -> dict:
    """Recompute ``done/total`` for stories and points from the real entries."""
    total = done = pts_total = pts_done = 0
    for item in epic.get("stories") or []:
        state = item.get("state") or ""
        if "Discarded" in state:
            continue
        total += 1
        story = stories_by_id.get(item["id"])
        points = _points(story.get("estimate") if story else item.get("points"))
        pts_total += points
        if "Delivered" in state:
            done += 1
            pts_done += points
    return {"stories_done": done, "stories_total": total,
            "points_done": pts_done, "points_total": pts_total}


def epic_table(epics: list[dict]) -> list[str]:
    rows = []
    ordered = sorted(epics, key=lambda e: (_EPIC_ORDER.get(e.get("state", "Proposed"), 0),
                                           id_rank(e["id"])))
    for epic in ordered:
        roll = epic.get("rollup") or {}
        rows.append([
            f"[{epic['id']}]({anchor(epic['id'])})",
            _v(epic.get("title")),
            EPIC_STATE_LABEL.get(epic.get("state", "Proposed"), EPIC_STATE_LABEL["Proposed"]),
            f"{roll.get('stories_done', 0)}/{roll.get('stories_total', 0)}",
            f"{roll.get('points_done', 0)}/{roll.get('points_total', 0)}",
            _v(epic.get("target")),
        ])
    return mdutil.render_table(EPIC_HEADERS, rows)


# --------------------------------------------------------------------------
# Derived: User-Stories.md overview
# --------------------------------------------------------------------------

STORY_HEADERS = ["ID", "Title", "State", "Pri", "Pts", "Epic", "Assignee"]


def story_rollup_line(stories: list[dict]) -> str:
    parts = []
    for state in STORY_STATES:
        group = [s for s in stories if s.get("state") == state]
        points = sum(_points(s.get("estimate")) for s in group)
        shown = f"{points} pts" if points else EMPTY
        parts.append(f"{STORY_STATE_LABEL[state]} {len(group)} ({shown})")
    return DOT.join(parts)


def _story_sort(story: dict) -> tuple:
    return (STORY_STATES.index(story["state"]) if story.get("state") in STORY_STATES else 99,
            priority_rank(story.get("priority")),
            id_rank(story["id"]))


def story_table(stories: list[dict]) -> list[str]:
    rows = []
    for story in sorted(stories, key=_story_sort):
        rows.append([
            f"[{story['id']}]({anchor(story['id'])})",
            _v(story.get("title")),
            STORY_STATE_LABEL.get(story.get("state", "Ready"), story.get("state", EMPTY)),
            _v(story.get("priority")),
            _v(story.get("estimate")),
            link(story["parent"]) if story.get("parent") else EMPTY,
            _v(story.get("assignee")),
        ])
    return mdutil.render_table(STORY_HEADERS, rows)


# --------------------------------------------------------------------------
# Derived: Bugs.md overview
# --------------------------------------------------------------------------

BUG_HEADERS = ["ID", "Title", "State", "Sev", "Pri", "Relates to", "Assignee"]
OPEN_BUG_STATES = {"Inbox", "Triaged", "Confirmed", "In Sprint"}


def bug_rollup_lines(bugs: list[dict], inbox_count: int) -> list[str]:
    counts = []
    for state in BUG_STATES:
        if state == "Inbox":
            counts.append(f"{BUG_STATE_LABEL[state]} {inbox_count}")
        elif state == "Deferred":
            # Deferred and Won't fix share one roll-up cell, as the template shows.
            n = sum(1 for b in bugs if b.get("state") in ("Deferred", "Won't fix"))
            deferred = BUG_STATE_LABEL["Deferred"]
            wont_fix = BUG_STATE_LABEL["Won't fix"]
            counts.append(f"{deferred} / {wont_fix} {n}")
        elif state == "Won't fix":
            continue
        else:
            counts.append(f"{BUG_STATE_LABEL[state]} "
                          f"{sum(1 for b in bugs if b.get('state') == state)}")
    open_bugs = [b for b in bugs if b.get("state") in OPEN_BUG_STATES]
    by_priority = DOT.join(
        f"{p} {sum(1 for b in open_bugs if b.get('priority') == p)}" for p in PRIORITIES)
    return [DOT.join(counts), "", f"Open by priority: {by_priority}"]


def _bug_sort(bug: dict) -> tuple:
    return (BUG_STATES.index(bug["state"]) if bug.get("state") in BUG_STATES else 99,
            priority_rank(bug.get("priority")),
            id_rank(bug["id"]))


def bug_table(bugs: list[dict]) -> list[str]:
    rows = []
    for bug in sorted(bugs, key=_bug_sort):
        rows.append([
            f"[{bug['id']}]({anchor(bug['id'])})",
            _v(bug.get("title")),
            BUG_STATE_LABEL.get(bug.get("state", "Triaged"), bug.get("state", EMPTY)),
            _v(bug.get("severity")),
            _v(bug.get("priority")),
            link(bug["relates_to"]) if bug.get("relates_to") else EMPTY,
            _v(bug.get("assignee")),
        ])
    return mdutil.render_table(BUG_HEADERS, rows)


# --------------------------------------------------------------------------
# Sprint board
# --------------------------------------------------------------------------

def board_line(item: dict) -> str:
    parts = [f"{link(item['id'])} {DASH} {_v(item.get('title'))}"]
    if item.get("points") and str(item["points"]).strip() not in ("", EMPTY):
        parts.append(f"{item['points']} pts")
    if item.get("assignee") and item["assignee"] != EMPTY:
        assignee = item["assignee"]
        parts.append(assignee if assignee.startswith("@") else "@" + assignee)
    return "- " + DOT.join(parts)


def blocked_line(item: dict) -> str:
    reason = item.get("reason") or "blocked"
    return f"- {link(item['id'])} {DASH} {_v(item.get('title'))}{DOT}{reason}"


__all__ = [
    "render_story", "render_epic", "render_bug", "story_index_line",
    "epic_table", "story_table", "bug_table", "story_rollup_line",
    "bug_rollup_lines", "epic_rollup", "derive_epic_state", "epic_state_from_emoji",
    "board_line", "blocked_line", "BOARD_COLUMNS",
]
