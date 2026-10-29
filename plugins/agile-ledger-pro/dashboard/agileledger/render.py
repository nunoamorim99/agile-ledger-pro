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
# Patching an entry that already exists
# --------------------------------------------------------------------------
#
# A full render writes an entry from the model, and the model is a summary:
# a criterion wrapped over three lines, the reason written after a
# Dependencies link, a field the dashboard has no name for — none of it is a
# value the model holds, so a full render of an existing entry drops it. That
# is fine for an entry being created and never for one being edited. An
# existing entry is therefore *patched*: its own lines are the starting
# point, and only the field or block whose value the action changed is
# rewritten. Everything else comes back byte for byte.

class Lines(list):
    """Rendered lines that also carry the original text they replaced.

    `LedgerFile.replace` records ``replaced`` as text the action meant to
    change, which is what the save-time no-loss guard checks against.
    """
    replaced = ""


def _norm(value):
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, bool):
        return value
    text = "" if value is None else str(value).strip()
    return "" if text in ("", EMPTY) else text


def _changed(new: dict, key: str) -> bool:
    return _norm(new.get(key)) != _norm((new.get("_orig") or {}).get(key))


def _content_at(out: list[str]) -> int:
    """Index of the first line after an entry's ``**Title**`` line."""
    from .parse import _title_line
    tidx = _title_line(out[1:])[3]
    return 1 + tidx + 1 if tidx >= 0 else 1


def _blocks(out: list[str]):
    from .parse import _split_blocks
    at = _content_at(out)
    return at, _split_blocks(out[at:])


def _find_block(out: list[str], *labels: str):
    at, blocks = _blocks(out)
    wanted = {l.lower() for l in labels}
    for b in blocks:
        if b["label"].lower() in wanted:
            return at + b["span"][0], at + b["span"][1], b
    return None


def _set_block(out: list[str], labels, new_lines: list[str], removed: list[str],
               before=("notes",)) -> None:
    """Replace one ``**Label**`` block, or insert it ahead of ``before``."""
    labels = (labels,) if isinstance(labels, str) else labels
    hit = _find_block(out, *labels)
    if hit:
        start, end, _ = hit
        while end > start and not out[end - 1].strip():
            end -= 1          # the blank after a block belongs to the layout
        removed += out[start:end]
        if new_lines:
            out[start:end] = new_lines
        else:
            if end < len(out) and not out[end].strip():
                end += 1
            out[start:end] = []
        return
    if not new_lines:
        return
    anchor = _find_block(out, *before) if before else None
    if anchor:
        out[anchor[0]:anchor[0]] = list(new_lines) + [""]
    else:
        while out and not out[-1].strip():
            out.pop()
        out += [""] + list(new_lines)


_FIELD_LINE = re.compile(r"^(\s*[-*]\s+\*\*([^*]+?):?\*\*:?\s*)(.*)$")


def _field_region(out: list[str]) -> tuple[int, int]:
    """The ``- **Field:** value`` lines live between the title and the first block."""
    at, blocks = _blocks(out)
    end = at + blocks[0]["span"][0] if blocks else len(out)
    return at, end


def _has_field(out: list[str], label: str) -> bool:
    start, end = _field_region(out)
    return any((m := _FIELD_LINE.match(out[i])) and m.group(2).strip().lower() == label.lower()
               for i in range(start, end))


def _set_field(out: list[str], label: str, value, removed: list[str]) -> None:
    """Set one bullet field in place; ``None`` removes it. Unknown fields are never touched."""
    start, end = _field_region(out)
    last = None
    for i in range(start, end):
        m = _FIELD_LINE.match(out[i])
        if not m:
            continue
        last = i
        if m.group(2).strip().lower() != label.lower():
            continue
        removed.append(out[i])
        if value is None:
            out[i:i + 1] = []
        else:
            out[i] = m.group(1) + str(value)
        return
    if value is None:
        return
    line = f"- **{label}:** {value}"
    if last is not None:
        out.insert(last + 1, line)
        return
    at = start
    while at < end and not out[at].strip():
        at += 1
    out[at:at] = [line, ""] if at < len(out) and out[at].strip() else [line]
    if at > 0 and out[at - 1].strip():
        out.insert(at, "")


def _set_head(out: list[str], head_for, removed: list[str]) -> None:
    from .parse import _title_line
    _, _, meta, tidx = _title_line(out[1:])
    if tidx < 0:
        return
    removed.append(out[1 + tidx])
    out[1 + tidx] = head_for(meta)


def _list_lines(items: list[str], hit, marker=lambda n: "-") -> list[str]:
    """A rewritten list: unchanged items on their own lines, new ones rendered.

    Adding one criterion is no reason to unwrap the others or flatten the
    bullet nested under one of them.
    """
    from .mdutil import list_item_lines
    written = list_item_lines(hit[2]["body"]) if hit else {}
    out = []
    for n, item in enumerate(items, 1):
        lines = written.pop(item, None)
        if lines:
            first = re.sub(r"^(\s*)(?:[-*+]|\d+[.)])", lambda m: m.group(1) + marker(n),
                           lines[0], count=1)
            out += [first] + lines[1:]
        else:
            out.append(f"{marker(n)} {item}")
    return out


def _deps_block(new_ids: list[str], hit) -> list[str]:
    """``**Dependencies:**`` for a changed ID list, keeping what was said about them.

    "US-003 — needs the auth API first" is a reason, not decoration; when the
    IDs change the prose stays, and only a body line naming a dependency that
    was removed goes with it.
    """
    ids = lambda text: {i.upper() for i in re.findall(r"\b((?:US|EPIC|BUG)-\d+)\b",
                                                       mdutil.strip_links(text), re.IGNORECASE)}
    inline, body = "", []
    if hit:
        inline, body = hit[2]["inline"], list(hit[2]["body"])
    while body and not body[-1].strip():
        body.pop()
    keep = set(new_ids)
    body = [l for l in body if not (ids(l) and not ids(l) <= keep)]
    in_body = set().union(*[ids(l) for l in body]) if body else set()
    prose = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", inline)
    prose = re.sub(r"\b(?:US|EPIC|BUG)-\d+\b", " ", prose, flags=re.IGNORECASE)
    prose = prose.strip(" \t·,;:" + DASH + "–-")
    prose = "" if prose == EMPTY else re.sub(r"\s{2,}", " ", prose)
    listed = [d for d in new_ids if d not in in_body]
    value = DOT.join(link(d) for d in listed) if listed else ("" if in_body else EMPTY)
    head = "**Dependencies:**" + (f" {value}" if value else "")
    if prose:
        head += f" {DASH} {prose}"
    return [head] + body


def _patch_story(story: dict) -> Lines:
    out = list(story["_raw"])
    orig = story.get("_orig") or {}
    removed: list[str] = []
    state = story.get("state", "Ready")

    if any(_changed(story, k) for k in ("title", "emoji", "parent")):
        def head(meta):
            head = f"**{_v(story.get('title'))}** {story.get('emoji') or STORY_STATE_EMOJI.get(state, '')}"
            parts, had_parent = [], False
            for part in meta:
                if part.lower().startswith("parent"):
                    had_parent = True
                    if story.get("parent"):
                        parts.append("Parent: " + link(story["parent"]))
                elif part:
                    parts.append(part)
            if story.get("parent") and not had_parent:
                parts.insert(0, "Parent: " + link(story["parent"]))
            return head + (SEP + DOT.join(parts) if parts else "")
        _set_head(out, head, removed)

    for key, label in (("priority", "Priority"), ("estimate", "Estimate"), ("area", "Area"),
                       ("layer", "Layer"), ("assignee", "Assignee")):
        if _changed(story, key):
            _set_field(out, label, _v(story.get(key)), removed)

    if _changed(story, "state"):
        if state in ("Paused", "Discarded"):
            when = story.get("status_date") or ""
            _set_field(out, "Status", f"{state}{f' ({when})' if when else ''}", removed)
        elif orig.get("state") in ("Paused", "Discarded") and _has_field(out, "Status"):
            _set_field(out, "Status", None, removed)
    if _changed(story, "reason") or (_changed(story, "state") and state in ("Paused", "Discarded")
                                     and not _has_field(out, "Reason")
                                     and not _find_block(out, "Reason")):
        if _find_block(out, "Reason"):
            _set_block(out, "Reason", [f"**Reason:** {_v(story.get('reason'))}"], removed)
        else:
            _set_field(out, "Reason", _v(story.get("reason")), removed)

    if _changed(story, "story"):
        _set_block(out, "Story", [f"**Story** {DASH} {story['story']}"] if story.get("story") else [],
                   removed)

    if _changed(story, "criteria") or _changed(story, "criteria_met"):
        from .mdutil import list_items
        hit = _find_block(out, "Acceptance criteria")
        loose = list_items(hit[2]["body"])[1] if hit else []
        criteria = [c for c in story.get("criteria") or [] if str(c).strip()]
        if state == "Delivered" and story.get("criteria_met"):
            header = "**Acceptance criteria:** all met ✓"
        elif hit and not re.match(r"^all met\b", re.sub(r"^_\([^)]*\)_\s*", "", hit[2]["inline"]),
                                  re.IGNORECASE):
            header = out[hit[0]]
        else:
            header = "**Acceptance criteria** _(Given / When / Then)_"
        block = []
        if criteria or story.get("criteria_met"):
            block = [header] + ([""] + _list_lines(criteria, hit) if criteria else []) \
                    + ([""] + loose if loose else [])
        _set_block(out, "Acceptance criteria", block, removed)

    if _changed(story, "dependencies"):
        hit = _find_block(out, "Dependencies")
        _set_block(out, "Dependencies", _deps_block(story.get("dependencies") or [], hit), removed)

    for label, key in (("Ready", "ready"), ("Started", "started"), ("Delivered", "delivered")):
        if _changed(story, key):
            _set_block(out, label, [f"**{label}:** {story[key]}"] if story.get(key) else [], removed)

    if _changed(story, "notes"):
        _set_block(out, "Notes", [f"**Notes:** {_v(story.get('notes'))}"], removed, before=())

    result = Lines(out)
    result.replaced = "\n".join(removed)
    return result


# --------------------------------------------------------------------------
# Story entry
# --------------------------------------------------------------------------

def render_story(story: dict) -> list[str]:
    if story.get("_raw"):
        return _patch_story(story)
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
        # The criteria stay listed under the verdict: "all met" is a fact about
        # them, not a replacement for them.
        out += ["**Acceptance criteria:** all met ✓", ""]
        if criteria:
            out += [f"- {c}" for c in criteria] + [""]
    elif criteria:
        out += ["**Acceptance criteria** _(Given / When / Then)_", ""]
        out += [f"- {c}" for c in criteria]
        out.append("")

    deps = story.get("dependencies") or []
    out += [f"**Dependencies:** {DOT.join(link(d) for d in deps) if deps else EMPTY}", ""]

    # The flow dates, in the order they happen. Each is written only when set,
    # so an entry from before they existed comes back byte for byte.
    for label, key in (("Ready", "ready"), ("Started", "started"), ("Delivered", "delivered")):
        if story.get(key):
            out += [f"**{label}:** {story[key]}", ""]

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
    ]
    if epic.get("created"):
        out += [f"**Created:** {epic['created']}", ""]
    out += ["**History:**", ""]
    out += [f"- {h}" for h in epic.get("history") or []]
    if epic.get("history"):
        out.append("")
    out += ["**Stories:**", ""]
    out += [story_index_line(s) for s in epic.get("stories") or []]
    return out


def epic_title_line(epic: dict, line: str) -> str:
    """The epic's ``**Title** 🔨  ·  target v2 · 1/4 stories · 5/13 pts`` line, re-derived.

    Only the derived parts move — the state emoji and the two rollups. Every
    other part the line carries stays where it was, in its own words.
    """
    roll = epic.get("rollup") or {}
    stories = f"{roll.get('stories_done', 0)}/{roll.get('stories_total', 0)} stories"
    points = f"{roll.get('points_done', 0)}/{roll.get('points_total', 0)} pts"
    parts = [p.strip() for p in line.split(mdutil.MIDDOT)]
    m = re.match(r"^(\s*\*\*.+?\*\*)\s*(.*)$", parts[0])
    if not m:
        return line
    bold, tail = m.group(1), m.group(2).strip()
    glyph = epic.get("emoji") or ""
    known = [g for g in EPIC_STATE_EMOJI.values() if g]
    hit = next((g for g in known if tail.startswith(g) or (g[0] and tail.startswith(g[0]))), None)
    if hit:
        rest = tail[len(hit):] if tail.startswith(hit) else tail[1:]
        rest = rest.lstrip("️").strip()
        tail = glyph + (" " + rest if rest else "")
    elif glyph:
        tail = (glyph + " " + tail).strip()
    # A line written without rollups keeps that shape: an unrelated action is
    # no reason to reformat an epic nobody touched.
    meta = []
    for part in parts[1:]:
        if re.search(r"\d+\s*/\s*\d+\s*stor", part):
            meta.append(stories)
        elif re.search(r"\d+\s*/\s*\d+\s*pts?\b", part):
            meta.append(points)
        elif part:
            meta.append(part)
    head = f"{bold} {tail}".rstrip()
    return head + (SEP + DOT.join(meta) if meta else "")


def story_index_line(item: dict) -> str:
    """``- [US-012](User-Stories.md#us-012) · Email signup · ✅ Delivered · 🔴 · 5 pts · @rita``

    Parts the old line carried that are not fields — ``extra``, and a note
    after the assignee — are written back after the fields they followed.
    """
    parts = [item.get("id_part") or link(item["id"]), _v(item.get("title"))]
    state = item.get("state") or ""
    parts.append(state if state else STORY_STATE_LABEL["Draft"])
    if item.get("priority") and item["priority"] != EMPTY:
        parts.append(item["priority"])
    if item.get("points") and str(item["points"]).strip() not in ("", EMPTY):
        parts.append(f"{item['points']} pts")
    if item.get("assignee") and item["assignee"] != EMPTY:
        assignee = item["assignee"]
        assignee = assignee if assignee.startswith("@") else "@" + assignee
        if item.get("assignee_note"):
            assignee += f" {DASH} {item['assignee_note']}"
        parts.append(assignee)
    elif item.get("assignee_note"):
        parts.append(item["assignee_note"])
    parts += [p for p in item.get("extra") or [] if p]
    return "- " + DOT.join(parts)


# --------------------------------------------------------------------------
# Bug entry
# --------------------------------------------------------------------------

def _patch_bug(bug: dict) -> Lines:
    out = list(bug["_raw"])
    removed: list[str] = []
    state = bug.get("state", "Triaged")

    if any(_changed(bug, k) for k in ("title", "emoji", "relates_to")):
        def head(meta):
            head = f"**{_v(bug.get('title'))}** {bug.get('emoji') or BUG_STATE_EMOJI.get(state, '')}"
            parts, had = [], False
            for part in meta:
                if "relates" in part.lower():
                    had = True
                    parts.append("relates to " + (link(bug["relates_to"]) if bug.get("relates_to")
                                                  else EMPTY))
                elif part:
                    parts.append(part)
            if bug.get("relates_to") and not had:
                parts.insert(0, "relates to " + link(bug["relates_to"]))
            return head + (SEP + DOT.join(parts) if parts else "")
        _set_head(out, head, removed)

    for key, label in (("severity", "Severity"), ("priority", "Priority"), ("state", "State"),
                       ("estimate", "Estimate"), ("reported_by", "Reported by"),
                       ("area", "Area"), ("assignee", "Assignee")):
        if _changed(bug, key):
            _set_field(out, label, state if key == "state" else _v(bug.get(key)), removed)

    if _changed(bug, "symptom"):
        _set_block(out, "Symptom", [f"**Symptom** {DASH} {_v(bug.get('symptom'))}"], removed)

    if _changed(bug, "steps") or _changed(bug, "steps_confidence"):
        from .mdutil import list_items
        hit = _find_block(out, "Steps to reproduce")
        loose = list_items(hit[2]["body"])[1] if hit else []
        steps = [s for s in bug.get("steps") or [] if str(s).strip()]
        confidence = bug.get("steps_confidence") or ("confirmed" if steps else "unconfirmed — needs input")
        block = [f"**Steps to reproduce** _({confidence})_"]
        if steps:
            block += [""] + _list_lines(steps, hit, marker=lambda n: f"{n}.")
        if loose:
            block += [""] + loose
        _set_block(out, "Steps to reproduce", block, removed)

    for label, key in (("Expected", "expected"), ("Actual", "actual")):
        if _changed(bug, key):
            _set_block(out, label, [f"**{label}:** {_v(bug.get(key))}"], removed)

    if _changed(bug, "assessment") or _changed(bug, "assessment_confidence"):
        assessment = bug.get("assessment")
        label = bug.get("assessment_confidence") or ("confirmed" if assessment else "pending /find-bug")
        line = f"**Assessment** _({label})_" + (f" {DASH} {assessment}" if assessment else "")
        _set_block(out, "Assessment", [line], removed)

    for label, key in (("Triaged", "triaged"), ("Started", "started"), ("Fixed", "fixed")):
        if _changed(bug, key):
            _set_block(out, label, [f"**{label}:** {bug[key]}"] if bug.get(key) else [], removed)

    if _changed(bug, "notes"):
        _set_block(out, "Notes", [f"**Notes:** {_v(bug.get('notes'))}"], removed, before=())

    result = Lines(out)
    result.replaced = "\n".join(removed)
    return result


def render_bug(bug: dict) -> list[str]:
    if bug.get("_raw"):
        return _patch_bug(bug)
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

    for label, key in (("Triaged", "triaged"), ("Started", "started"), ("Fixed", "fixed")):
        if bug.get(key):
            out += [f"**{label}:** {bug[key]}", ""]

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
    # Work added after planning carries the day it arrived, which is what
    # "scope changed mid-sprint" is measured from. Planned items carry nothing.
    parts += [p for p in item.get("extra") or [] if p]
    if item.get("pulled"):
        parts.append(f"pulled {item['pulled']}")
    return "- " + DOT.join(parts)


def blocked_line(item: dict) -> str:
    reason = item.get("reason") or "blocked"
    line = f"- {link(item['id'])} {DASH} {_v(item.get('title'))}{DOT}{reason}"
    # "since" is the date the flag went up: blocked time is reason + duration,
    # and a flag with no date can only ever say the first half.
    if item.get("since"):
        line += f"{DOT}since {item['since']}"
    return line


__all__ = [
    "render_story", "render_epic", "render_bug", "story_index_line",
    "epic_table", "story_table", "bug_table", "story_rollup_line",
    "bug_rollup_lines", "epic_rollup", "derive_epic_state", "epic_state_from_emoji",
    "board_line", "blocked_line", "BOARD_COLUMNS",
]
