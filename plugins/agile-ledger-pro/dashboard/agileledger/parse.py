"""Readers for the eight ledger files.

Every parser returns plain dicts and records a ``span`` — the half-open line
range the entry occupies in its file — so `actions.py` can replace exactly that
region and leave everything else on disk byte-for-byte intact. Fields this
module does not model are preserved for the same reason: they live in
``extra_blocks`` and are written back untouched.

The detail entries are treated as the source of truth; the overview tables are
not parsed for data at all, because `SKILL.md` declares them derived.
"""

from __future__ import annotations

import re

from . import mdutil
from .mdutil import EMPTY, bullets, clean, comment_mask, split_lines, strip_links

ID_RE = re.compile(r"^(EPIC|US|BUG|TASK)-\d+$", re.IGNORECASE)
_NEXT_ID = re.compile(r"([A-Z]+):\s*([A-Z]+-\d+)")
# The label's colon may sit inside the bold markers (`**Goal:**`) or outside
# them (`**Story**:`), and some labels carry none at all (`**Story** — ...`).
# Group 2 records whether a colon was seen, because a colon-less label uses an
# em dash as its separator and a colon-bearing one does not.
_BLOCK_START = re.compile(r"^\*\*([^*]+?)(:)?\*\*(:)?\s*(.*)$")
_FIELD = re.compile(r"^\s*[-*]\s+\*\*([^*]+?):?\*\*:?\s*(.*)$")


# --------------------------------------------------------------------------
# Shared entry machinery
# --------------------------------------------------------------------------

def _title_line(body: list[str]) -> tuple[str, str, list[str], int]:
    """Pull ``**Title** EMOJI  ·  meta · meta`` off the top of an entry body.

    Returns ``(title, emoji, meta_parts, index)``; ``index`` is the line the
    header was found on so the caller can keep what follows.
    """
    for i, line in enumerate(body):
        if not line.strip():
            continue
        if not line.lstrip().startswith("**"):
            break
        parts = [p.strip() for p in line.split(mdutil.MIDDOT)]
        head = parts[0]
        m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", head.strip())
        if not m:
            break
        return m.group(1).strip(), m.group(2).strip(), parts[1:], i
    return "", "", [], -1


def _split_blocks(body: list[str]) -> list[dict]:
    """Break an entry body into its ``**Label**`` prose blocks, in order.

    A block starts at a non-bullet line opening with ``**Label**`` or
    ``**Label:**`` and runs to the next such line. Bullet fields
    (``- **Priority:** ...``) are not block starts.
    """
    mask = comment_mask(body)
    starts = []
    for i, line in enumerate(body):
        if mask[i] or _FIELD.match(line):
            continue
        if line.startswith((" ", "\t")):
            continue  # an indented bold line belongs to the block above it
        if _BLOCK_START.match(line.strip()):
            starts.append(i)
    blocks = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(body)
        m = _BLOCK_START.match(body[start].strip())
        label = m.group(1).strip()
        had_colon = bool(m.group(2) or m.group(3))
        inline = m.group(4).strip()
        # "**Story** — As a ..." separates with an em dash, so drop it. A
        # colon-bearing label does not, and there "—" is the value itself
        # (the ledger's "unknown", as in "**Notes:** —").
        if not had_colon and inline.startswith(mdutil.DASH):
            inline = inline[len(mdutil.DASH):].strip()
        blocks.append({
            "label": label,
            "inline": inline,
            "body": body[start + 1:end],
            "span": (start, end),
        })
    return blocks


_MARKER = re.compile(r"^_\(([^)]*)\)_\s*(.*)$")


def _strip_marker(inline: str) -> tuple[str, str]:
    """Split ``_(confirmed)_ — text`` into ``("confirmed", "text")``.

    Several blocks carry a parenthesised italic confidence marker before their
    real content (``**Assessment** _(pending /find-bug)_``). Without this the
    marker would be read as the content and written back as if a human had
    typed it.
    """
    m = _MARKER.match(inline.strip())
    if not m:
        return "", inline.strip()
    rest = m.group(2).strip()
    if rest.startswith(mdutil.DASH):
        rest = rest[len(mdutil.DASH):].strip()
    return m.group(1).strip(), rest


def _fields(body: list[str]) -> dict[str, str]:
    """``- **Priority:** 🔴`` bullet fields, keyed by lowercased label."""
    out = {}
    mask = comment_mask(body)
    for i, line in enumerate(body):
        if mask[i]:
            continue
        m = _FIELD.match(line)
        if m:
            out[m.group(1).strip().lower()] = m.group(2).strip()
    return out


def _block(blocks: list[dict], *labels: str) -> dict | None:
    wanted = {l.lower() for l in labels}
    for b in blocks:
        if b["label"].lower() in wanted:
            return b
    return None


def _block_text(blocks: list[dict], *labels: str) -> str:
    b = _block(blocks, *labels)
    if not b:
        return ""
    parts = [b["inline"]] if b["inline"] else []
    parts += [l.strip() for l in b["body"] if l.strip()]
    return " ".join(parts).strip()


def _entries(lines: list[str], start: int, end: int, level: int) -> list[dict]:
    """Every ``#''*level`` heading inside ``[start, end)`` whose text is an ID."""
    mask = comment_mask(lines)
    found = []
    for i in range(start, min(end, len(lines))):
        if mask[i] or mdutil.heading_level(lines[i]) != level:
            continue
        text = mdutil.heading_text(lines[i]).strip()
        if ID_RE.match(text):
            found.append((i, text.upper()))

    out = []
    for n, (idx, item_id) in enumerate(found):
        stop = found[n + 1][0] if n + 1 < len(found) else end
        # An entry also stops at any heading shallower than its own.
        for j in range(idx + 1, stop):
            lv = mdutil.heading_level(lines[j])
            if not mask[j] and lv and lv < level:
                stop = j
                break
        span = mdutil.trim_span(lines, idx, stop)
        out.append({"id": item_id, "span": span, "body": lines[idx + 1:span[1]]})
    return out


# --------------------------------------------------------------------------
# Ideas.md
# --------------------------------------------------------------------------

def parse_triaged_ideas(lines: list[str]) -> list[dict]:
    """The ``## ✅ Triaged`` section: every idea that left the inbox, and where to.

    ``- 2026-03-01 — weekly digest email → US-012 (2026-03-04)`` or
    ``… → discarded (2026-03-04): already covered by US-009``. Ideas used to
    be deleted at triage, which made "ideas per month" and the idea → story
    funnel impossible to ever compute, and was the one place the ledger threw
    something away.
    """
    span = mdutil.find_section(lines, 2, lambda t: "triaged" in t.lower())
    if not span:
        return []
    start, end = span
    mask = comment_mask(lines)
    out = []
    for i in range(start + 1, end):
        if mask[i]:
            continue
        m = re.match(r"^\s{0,3}[-*]\s+(.*)$", lines[i])
        if not m or not m.group(1).strip():
            continue
        text = m.group(1).strip()
        date = ""
        dm = re.match(r"^(\d{4}-\d{2}-\d{2})\s*" + mdutil.DASH + r"\s*(.*)$", text)
        if dm:
            date, text = dm.group(1), dm.group(2).strip()
        outcome, became, when, note = "", "", "", ""
        om = re.match(r"^(.*?)\s*→\s*(.*)$", text)
        if om:
            text, tail = om.group(1).strip(), om.group(2).strip()
            tm = re.match(r"^((?:US|EPIC)-\d+|discarded)\s*(?:\((\d{4}-\d{2}-\d{2})\))?\s*:?\s*(.*)$",
                          tail, re.IGNORECASE)
            if tm:
                target = tm.group(1)
                outcome = "discarded" if target.lower() == "discarded" else "promoted"
                became = "" if outcome == "discarded" else target.upper()
                when, note = tm.group(2) or "", tm.group(3).strip()
        out.append({"date": date, "text": text, "outcome": outcome, "became": became,
                    "triaged": when, "note": note, "line": i})
    return out


def parse_ideas(lines: list[str]) -> list[dict]:
    span = mdutil.find_section(lines, 2, lambda t: "inbox" in t.lower())
    if not span:
        return []
    start, end = span
    mask = comment_mask(lines)
    out = []
    for i in range(start + 1, end):
        if mask[i]:
            continue
        m = re.match(r"^\s{0,3}[-*]\s+(.*)$", lines[i])
        if not m or not m.group(1).strip():
            continue
        text = m.group(1).strip()
        date = ""
        dm = re.match(r"^(\d{4}-\d{2}-\d{2})\s*" + mdutil.DASH + r"\s*(.*)$", text)
        if dm:
            date, text = dm.group(1), dm.group(2).strip()
        out.append({"date": date, "text": text, "line": i})
    return out


# --------------------------------------------------------------------------
# Epic-Backlog.md
# --------------------------------------------------------------------------

def parse_next_ids(lines: list[str]) -> dict[str, str]:
    mask = comment_mask(lines)
    out = {}
    for i, line in enumerate(lines):
        if mask[i] or "next free id" not in line.lower():
            continue
        for kind, value in _NEXT_ID.findall(line):
            out[kind.upper()] = value.upper()
    return out


def parse_epics(lines: list[str]) -> list[dict]:
    span = mdutil.find_section(lines, 2, lambda t: t.strip().lower() == "epics")
    start, end = span if span else (0, len(lines))
    out = []
    for entry in _entries(lines, start, end, 3):
        body = entry["body"]
        title, emoji, meta, tidx = _title_line(body)
        content = body[tidx + 1:] if tidx >= 0 else body
        blocks = _split_blocks(content)

        target, done_stories, total_stories, done_pts, total_pts = "", 0, 0, 0, 0
        for part in meta:
            if part.lower().startswith("target"):
                target = part.split(None, 1)[1].strip() if " " in part else ""
            elif "stories" in part.lower():
                m = re.search(r"(\d+)\s*/\s*(\d+)", part)
                if m:
                    done_stories, total_stories = int(m.group(1)), int(m.group(2))
            elif "pts" in part.lower():
                m = re.search(r"(\d+)\s*/\s*(\d+)", part)
                if m:
                    done_pts, total_pts = int(m.group(1)), int(m.group(2))

        stories_block = _block(blocks, "Stories")
        index = []
        if stories_block:
            for raw in bullets(stories_block["body"], 0, len(stories_block["body"])):
                parts = [p.strip() for p in raw.split(mdutil.MIDDOT)]
                sid = strip_links(parts[0]).strip() if parts else ""
                if not ID_RE.match(sid):
                    continue
                item = {"id": sid.upper(), "title": "", "state": "", "priority": "",
                        "points": "", "assignee": ""}
                for part in parts[1:]:
                    if not part:
                        continue
                    if part.startswith("@"):
                        item["assignee"] = part
                    elif re.fullmatch(r"\d+\s*pts?", part):
                        item["points"] = re.sub(r"\s*pts?$", "", part)
                    elif part in ("\U0001f534", "\U0001f7e1", "\U0001f7e2"):
                        item["priority"] = part
                    elif any(k in part for k in ("Draft", "Ready", "Sprint", "Delivered",
                                                 "Paused", "Discarded")):
                        item["state"] = part
                    elif not item["title"]:
                        item["title"] = part
                index.append(item)

        history_block = _block(blocks, "History")
        history = bullets(history_block["body"], 0, len(history_block["body"])) if history_block else []

        known = {"stories", "history", "goal", "area", "created"}
        extra = [b for b in blocks if b["label"].lower() not in known]

        out.append({
            "id": entry["id"],
            "title": title,
            "emoji": emoji,
            "target": clean(target),
            "goal": _block_text(blocks, "Goal"),
            "created": _block_text(blocks, "Created"),
            "area": _block_text(blocks, "Area"),
            "history": history,
            "stories": index,
            "rollup": {"stories_done": done_stories, "stories_total": total_stories,
                       "points_done": done_pts, "points_total": total_pts},
            "extra_blocks": [b["label"] for b in extra],
            "span": entry["span"],
        })
    return out


# --------------------------------------------------------------------------
# User-Stories.md
# --------------------------------------------------------------------------

def _state_of_section(title: str, states: list[str]) -> str | None:
    """Match a ``## ✅ Ready`` heading to a state name, tolerating combined headings."""
    low = title.lower()
    hits = [s for s in states if s.lower() in low]
    return hits[0] if hits else None


def parse_stories(lines: list[str]) -> list[dict]:
    from .model import STORY_STATES

    out = []
    for idx, title in mdutil.iter_headings(lines, 2):
        state = _state_of_section(title, STORY_STATES)
        if not state:
            continue
        start, end = mdutil.section_span(lines, idx)
        for entry in _entries(lines, start, end, 4):
            body = entry["body"]
            name, emoji, meta, tidx = _title_line(body)
            content = body[tidx + 1:] if tidx >= 0 else body
            blocks = _split_blocks(content)
            fields = _fields(content)

            parent = ""
            for part in meta:
                if part.lower().startswith("parent"):
                    parent = strip_links(part.split(":", 1)[-1]).strip().upper()

            ac_block = _block(blocks, "Acceptance criteria")
            criteria, criteria_met = [], False
            if ac_block:
                _, inline = _strip_marker(ac_block["inline"])
                # The Delivered shape collapses the list to "all met ✓".
                if inline and re.match(r"^all met\b", inline, re.IGNORECASE):
                    criteria_met = True
                elif inline:
                    criteria.append(inline)
                criteria += bullets(ac_block["body"], 0, len(ac_block["body"]))

            deps_text = _block_text(blocks, "Dependencies")
            deps = [i.upper() for i in re.findall(r"\b((?:US|EPIC|BUG)-\d+)\b",
                                                  strip_links(deps_text), re.IGNORECASE)]

            known = {"story", "acceptance criteria", "dependencies", "notes",
                     "ready", "started", "delivered", "reason", "what shipped"}
            extra = [{"label": b["label"], "inline": b["inline"], "body": b["body"]}
                     for b in blocks if b["label"].lower() not in known]

            out.append({
                "id": entry["id"],
                "title": name,
                "emoji": emoji,
                "state": state,
                "parent": parent,
                "priority": clean(fields.get("priority")),
                "estimate": clean(fields.get("estimate")),
                "area": clean(fields.get("area")),
                "layer": clean(fields.get("layer")),
                "assignee": clean(fields.get("assignee")),
                "status_note": clean(fields.get("status")),
                "reason": clean(fields.get("reason")) if "reason" in fields
                          else clean(_block_text(blocks, "Reason")),
                "story": _block_text(blocks, "Story"),
                "criteria": criteria,
                "criteria_met": criteria_met,
                "dependencies": deps,
                "dependencies_text": deps_text,
                # The flow dates. Optional, and absent from every file written
                # before they existed: a story has always carried one date
                # (Delivered), which says what shipped but not how long it
                # took. Ready and Started are what cycle time is made of.
                "ready": _block_text(blocks, "Ready"),
                "started": _block_text(blocks, "Started"),
                "delivered": _block_text(blocks, "Delivered"),
                "notes": _block_text(blocks, "Notes"),
                "extra_blocks": extra,
                "span": entry["span"],
            })
    return out


# --------------------------------------------------------------------------
# Bugs.md
# --------------------------------------------------------------------------

def parse_bug_inbox(lines: list[str]) -> list[dict]:
    span = mdutil.find_section(lines, 2, lambda t: "inbox" in t.lower())
    if not span:
        return []
    start, end = span
    mask = comment_mask(lines)
    out = []
    for i in range(start + 1, end):
        if mask[i]:
            continue
        m = re.match(r"^\s{0,3}[-*]\s+(.*)$", lines[i])
        if not m or not m.group(1).strip():
            continue
        text = m.group(1).strip()
        date = ""
        dm = re.match(r"^(\d{4}-\d{2}-\d{2})\s*" + mdutil.DASH + r"\s*(.*)$", text)
        if dm:
            date, text = dm.group(1), dm.group(2).strip()
        out.append({"date": date, "text": text, "line": i})
    return out


def parse_bugs(lines: list[str]) -> list[dict]:
    from .model import BUG_STATES

    out = []
    for idx, title in mdutil.iter_headings(lines, 2):
        if "inbox" in title.lower():
            continue
        start, end = mdutil.section_span(lines, idx)
        section_state = _state_of_section(title, [s for s in BUG_STATES if s != "Inbox"])
        for entry in _entries(lines, start, end, 3):
            body = entry["body"]
            name, emoji, meta, tidx = _title_line(body)
            content = body[tidx + 1:] if tidx >= 0 else body
            blocks = _split_blocks(content)
            fields = _fields(content)

            relates, has_relates = "", False
            for part in meta:
                if "relates" in part.lower():
                    has_relates = True
                    ids = re.findall(r"\b((?:US|EPIC)-\d+)\b", strip_links(part), re.IGNORECASE)
                    relates = ids[0].upper() if ids else ""

            steps_block = _block(blocks, "Steps to reproduce")
            steps = bullets(steps_block["body"], 0, len(steps_block["body"])) if steps_block else []
            steps_confidence = _strip_marker(steps_block["inline"])[0] if steps_block else ""
            assess_block = _block(blocks, "Assessment")
            assess_confidence, assessment = _strip_marker(assess_block["inline"]) if assess_block else ("", "")
            if assess_block and not assessment:
                assessment = " ".join(l.strip() for l in assess_block["body"] if l.strip())

            state = clean(fields.get("state"))
            if state == EMPTY:
                state = section_state or "Triaged"
            else:
                state = next((s for s in BUG_STATES if s.lower() in state.lower()),
                             section_state or "Triaged")

            known = {"symptom", "steps to reproduce", "expected", "actual",
                     "assessment", "notes", "triaged", "started", "fixed"}
            extra = [{"label": b["label"], "inline": b["inline"], "body": b["body"]}
                     for b in blocks if b["label"].lower() not in known]

            out.append({
                "id": entry["id"],
                "title": name,
                "emoji": emoji,
                "state": state,
                "severity": clean(fields.get("severity")),
                "priority": clean(fields.get("priority")),
                "estimate": clean(fields.get("estimate")),
                "reported_by": clean(fields.get("reported by")),
                "area": clean(fields.get("area")),
                "assignee": clean(fields.get("assignee")),
                "relates_to": relates,
                # Kept so re-rendering an unrelated edit does not silently drop
                # an explicit "relates to —" the ledger already carried.
                "has_relates_meta": has_relates,
                "symptom": _block_text(blocks, "Symptom"),
                "steps": steps,
                "steps_confidence": steps_confidence,
                "expected": _block_text(blocks, "Expected"),
                "actual": _block_text(blocks, "Actual"),
                "assessment": assessment,
                "assessment_confidence": assess_confidence,
                "triaged": _block_text(blocks, "Triaged"),
                "started": _block_text(blocks, "Started"),
                "fixed": _block_text(blocks, "Fixed"),
                "notes": _block_text(blocks, "Notes"),
                "extra_blocks": extra,
                "span": entry["span"],
            })
    return out


# --------------------------------------------------------------------------
# Sprint.md
# --------------------------------------------------------------------------

def parse_sprint(lines: list[str]) -> dict:
    from .model import BOARD_COLUMNS

    def field(label):
        value = mdutil.bold_field(lines, label)
        return clean(value) if value is not None else EMPTY

    def sprint_name(value: str) -> str:
        """Empty when the file is carrying its placeholder rather than a sprint.

        `Sprint.template.md` ships, and `/close-sprint` restores, a friendly
        line — ``_none yet_ — run `/plan-sprint` to start one.`` — which reads
        well in Markdown but is not a sprint name. Treat the italic placeholder,
        and anything that points at the command, as no sprint at all.
        """
        text = (value or "").strip()
        if not text or text == EMPTY:
            return EMPTY
        if text.startswith("_") or "/plan-sprint" in text:
            return EMPTY
        return text

    last_sync = EMPTY
    mask = comment_mask(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = re.match(r"^\s*Last main sync:\s*(.*)$", line, re.IGNORECASE)
        if m:
            last_sync = clean(re.sub(r"[_*]", "", m.group(1)))
            break

    board = {col: [] for col in BOARD_COLUMNS}
    board_span = mdutil.find_section(lines, 2, lambda t: t.strip().lower() == "board")
    if board_span:
        b_start, b_end = board_span
        for idx, title in mdutil.iter_headings(lines, 3):
            if not (b_start < idx < b_end):
                continue
            column = next((c for c in BOARD_COLUMNS if c.lower() == title.strip().lower()), None)
            if not column:
                continue
            c_start, c_end = mdutil.section_span(lines, idx)
            for raw in bullets(lines, c_start + 1, min(c_end, b_end)):
                item = _board_item(raw)
                if item:
                    board[column].append(item)

    blocked = []
    blocked_span = mdutil.find_section(lines, 2, lambda t: "blocked" in t.lower())
    if blocked_span:
        for raw in bullets(lines, blocked_span[0] + 1, blocked_span[1]):
            text = strip_links(raw)
            m = re.match(r"^((?:US|BUG)-\d+)\b\s*(?:" + mdutil.DASH + r"\s*)?(.*)$",
                         text, re.IGNORECASE)
            if not m:
                continue
            parts = [p.strip() for p in m.group(2).split(mdutil.MIDDOT)]
            since = ""
            if len(parts) > 1:
                sm = re.fullmatch(r"since\s+(\d{4}-\d{2}-\d{2})", parts[-1])
                if sm:
                    since = sm.group(1)
                    parts = parts[:-1]
            blocked.append({
                "id": m.group(1).upper(),
                "title": parts[0] if parts else "",
                # Everything after the title says why it is blocked, which is the
                # part a reader actually needs. Keep it whole.
                "reason": (" " + mdutil.MIDDOT + " ").join(p for p in parts[1:] if p),
                "since": since,
                "text": text,
            })

    sync_log = []
    log_span = mdutil.find_section(lines, 2, lambda t: "sync log" in t.lower())
    if log_span:
        sync_log = [strip_links(r) for r in bullets(lines, log_span[0] + 1, log_span[1])]

    return {
        "name": sprint_name(field("Sprint")),
        "goal": field("Sprint Goal"),
        "dates": field("Dates"),
        "capacity": field("Capacity (target points)"),
        "last_sync": last_sync,
        "board": board,
        "blocked": blocked,
        "sync_log": sync_log,
    }


def _board_item(raw: str) -> dict | None:
    """``- US-014 — Google SSO login · 5 pts · @rita`` (links optional)."""
    text = strip_links(raw)
    m = re.match(r"^((?:US|BUG)-\d+)\b\s*(?:" + mdutil.DASH + r"\s*)?(.*)$", text, re.IGNORECASE)
    if not m:
        return None
    rest = [p.strip() for p in m.group(2).split(mdutil.MIDDOT)]
    item = {"id": m.group(1).upper(), "title": rest[0] if rest else "",
            "points": "", "assignee": "", "pulled": ""}
    for part in rest[1:]:
        if part.startswith("@"):
            item["assignee"] = part
        elif re.fullmatch(r"\d+\s*pts?", part):
            item["points"] = re.sub(r"\s*pts?$", "", part)
        else:
            pm = re.fullmatch(r"pulled\s+(\d{4}-\d{2}-\d{2})", part)
            if pm:
                item["pulled"] = pm.group(1)
    return item


# --------------------------------------------------------------------------
# Sprints-History.md
# --------------------------------------------------------------------------

_RANGE = re.compile(r"\s*(?:→|->|–|—|\bto\b)\s*")


def _split_range(dates: str) -> tuple[str, str]:
    """``2026-02-16 → 2026-02-27`` -> ``("2026-02-16", "2026-02-27")``.

    Teams write the arrow several ways, so accept the usual ones. Anything that
    does not split cleanly in two is kept whole as the start rather than guessed
    at — a half-invented end date would be worse than an empty cell.
    """
    text = (dates or "").strip()
    if not text or text == EMPTY:
        return "", ""
    parts = [p.strip() for p in _RANGE.split(text) if p.strip()]
    return (parts[0], parts[1]) if len(parts) == 2 else (text, "")


def _retro_notes(body: list[str]) -> list[dict]:
    """The bullets under ``Retro notes:`` in a closed sprint.

    A line usually opens with its own label (``- Kept: …``, ``- Try: …``), so
    keep that label separate from the note rather than flattening it — it is
    how the team already files what they learned.
    """
    mask = comment_mask(body)
    start = None
    for i, line in enumerate(body):
        if not mask[i] and re.match(r"^\s*retro notes:?\s*$", line, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return []

    out = []
    for i in range(start, len(body)):
        if mask[i]:
            continue
        line = body[i]
        if line.strip() and not re.match(r"^\s{0,3}[-*]\s+", line):
            break                       # the list ended; anything else is not a note
        m = re.match(r"^\s{0,3}[-*]\s+(.*)$", line)
        if not m or not m.group(1).strip():
            continue
        text = m.group(1).strip()
        label, _, rest = text.partition(":")
        if rest.strip() and len(label) <= 24:
            out.append({"label": label.strip(), "note": rest.strip()})
        else:
            out.append({"label": "", "note": text})
    return out


def parse_history(lines: list[str]) -> dict:
    velocity_line = mdutil.bold_field(lines, "Rolling velocity (last 3 sprints)")
    sprints = []
    mask = comment_mask(lines)
    for i, line in enumerate(lines):
        if mask[i] or mdutil.heading_level(line) != 2:
            continue
        title = mdutil.heading_text(line)
        start, end = mdutil.section_span(lines, i)
        body = lines[start + 1:end]
        joined = "\n".join(b for j, b in enumerate(body) if not comment_mask(body)[j])

        name, goal_quote, dates = title, "", ""
        tm = re.match(r"^(\S+)\s*" + mdutil.DASH + r'\s*"?([^"(]*)"?\s*(?:\(([^)]*)\))?\s*$', title)
        if tm:
            name = tm.group(1).strip()
            goal_quote = tm.group(2).strip()
            dates = (tm.group(3) or "").strip()

        def grab(label):
            m = re.search(r"^" + re.escape(label) + r":\s*(.*)$", joined, re.MULTILINE)
            return m.group(1).strip() if m else ""

        committed = completed = velocity = ""
        cm = re.search(r"Committed:\s*(\d+)\s*pts?.*?Completed:\s*(\d+)\s*pts?", joined, re.S)
        if cm:
            committed, completed = cm.group(1), cm.group(2)
        vm = re.search(r"velocity\s*\*{0,2}\s*(\d+)", joined, re.IGNORECASE)
        if vm:
            velocity = vm.group(1)

        start_date, end_date = _split_range(dates)
        sprints.append({
            "name": name,
            "title": goal_quote,
            "dates": dates,
            "start": start_date,
            "end": end_date,
            "goal": grab("Goal"),
            "committed": committed,
            "completed": completed,
            "velocity": velocity,
            "delivered": [i.upper() for i in re.findall(
                r"\b((?:US|BUG)-\d+)\b", grab("Delivered"), re.IGNORECASE)],
            "pulled": [i.upper() for i in re.findall(
                r"\b((?:US|BUG)-\d+)\b", grab("Pulled in") or "", re.IGNORECASE)],
            "pulled_points": (re.search(r"\((\d+)\s*pts?\)", grab("Pulled in") or "") or [None, "0"])[1],
            "carried": [i.upper() for i in re.findall(
                r"\b((?:US|BUG)-\d+)\b", grab("Carried over"), re.IGNORECASE)],
            "retro": _retro_notes(body),
            "span": (start, end),
        })
    return {"rolling_velocity": clean(velocity_line), "sprints": sprints}


# --------------------------------------------------------------------------
# Releases.md
# --------------------------------------------------------------------------

def parse_releases(lines: list[str]) -> dict:
    increment = []
    inc_span = mdutil.find_section(lines, 2, lambda t: "increment" in t.lower())
    if inc_span:
        for raw in bullets(lines, inc_span[0] + 1, inc_span[1]):
            text = strip_links(raw)
            ids = re.findall(r"\b((?:US|BUG)-\d+)\b", text, re.IGNORECASE)
            increment.append({"id": ids[0].upper() if ids else "", "text": text})

    versions = []
    hist_span = mdutil.find_section(lines, 2, lambda t: "version history" in t.lower())
    if hist_span:
        h_start, h_end = hist_span
        for idx, title in mdutil.iter_headings(lines, 3):
            if not (h_start < idx < h_end):
                continue
            start, end = mdutil.section_span(lines, idx)
            body = lines[start + 1:end]
            b_mask = comment_mask(body)
            joined = "\n".join(b for j, b in enumerate(body) if not b_mask[j])

            version, name, date = title, "", ""
            tm = re.match(r"^(\S+)\s*" + mdutil.DASH + r"\s*(.*?)\s*(?:\(([^)]*)\))?\s*$", title)
            if tm:
                version, name, date = tm.group(1).strip(), tm.group(2).strip(), (tm.group(3) or "").strip()

            def grab(label):
                m = re.search(r"^" + re.escape(label) + r":\s*(.*)$", joined, re.MULTILINE)
                return m.group(1).strip() if m else ""

            versions.append({
                "version": version,
                "title": name,
                "date": date,
                "theme": grab("Theme"),
                "stories": [i.upper() for i in re.findall(
                    r"\b((?:US|BUG)-\d+)\b", grab("Stories"), re.IGNORECASE)],
                "epics": [i.upper() for i in re.findall(
                    r"\bEPIC-\d+\b", grab("Epics touched"), re.IGNORECASE)],
                "span": (start, end),
            })
    return {"increment": increment, "versions": versions}


# --------------------------------------------------------------------------
# Definitions.md
# --------------------------------------------------------------------------

def parse_definitions(lines: list[str]) -> dict:
    config = {}
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

    def checklist(keyword):
        span = mdutil.find_section(lines, 2, lambda t: keyword in t.lower())
        if not span:
            return []
        out = []
        for raw in bullets(lines, span[0] + 1, span[1]):
            m = re.match(r"^\[([ xX])\]\s*(.*)$", raw)
            out.append(m.group(2).strip() if m else raw)
        return out

    return {
        "config": config,
        "definition_of_ready": checklist("definition of ready"),
        "definition_of_done": checklist("definition of done"),
    }
