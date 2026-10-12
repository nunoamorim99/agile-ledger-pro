"""Markdown primitives shared by the ledger parsers and renderers.

Everything here works on a list of lines (no trailing newlines) and reports
*spans* as half-open ``[start, end)`` line ranges, so a caller can splice an
edit back into the exact region it came from. That is what keeps a write
surgical: anything this module did not model stays untouched on disk.
"""

from __future__ import annotations

import re

DASH = "—"          # em dash, the separator the ledger uses
MIDDOT = "·"        # interpunct, the inline field separator
EMPTY = "—"         # the "unknown / not set" cell, never blank

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_RULE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")


def split_lines(text: str) -> list[str]:
    """Split into lines, dropping a single trailing newline's phantom entry."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def join_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def comment_mask(lines: list[str]) -> list[bool]:
    """True for every line sitting inside an HTML comment.

    The templates ship their examples commented out, so every parser has to
    skip those regions rather than register them as real entries. A comment
    that opens and closes on one line only masks that line.
    """
    mask = [False] * len(lines)
    inside = False
    for i, line in enumerate(lines):
        if inside:
            mask[i] = True
            if "-->" in line:
                inside = False
            continue
        if "<!--" in line:
            # Walk the line so an open/close pair does not leave us "inside".
            rest = line
            opened = False
            while True:
                o = rest.find("<!--")
                if o == -1:
                    break
                c = rest.find("-->", o + 4)
                if c == -1:
                    opened = True
                    break
                rest = rest[c + 3:]
            mask[i] = True
            inside = opened
    return mask


def heading_level(line: str) -> int:
    """Return the ATX heading level of ``line``, or 0 when it is not one."""
    m = _HEADING.match(line)
    return len(m.group(1)) if m else 0


def heading_text(line: str) -> str:
    m = _HEADING.match(line)
    return m.group(2) if m else ""


def is_rule(line: str) -> bool:
    return bool(_RULE.match(line))


def iter_headings(lines: list[str], level: int, *, skip_comments: bool = True):
    """Yield ``(index, text)`` for every heading at exactly ``level``."""
    mask = comment_mask(lines) if skip_comments else [False] * len(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if heading_level(line) == level:
            yield i, heading_text(line)


def section_span(lines: list[str], start: int) -> tuple[int, int]:
    """Span of the section whose heading sits at ``start``.

    Ends just before the next heading of the same or a shallower level, which
    is how these files nest (``## Epics`` holding many ``### EPIC-nnn``).
    """
    level = heading_level(lines[start])
    if level == 0:
        raise ValueError(f"line {start} is not a heading: {lines[start]!r}")
    mask = comment_mask(lines)
    for i in range(start + 1, len(lines)):
        if mask[i]:
            continue
        lv = heading_level(lines[i])
        if lv and lv <= level:
            return start, i
    return start, len(lines)


def find_section(lines: list[str], level: int, predicate) -> tuple[int, int] | None:
    """Span of the first ``level`` heading whose text satisfies ``predicate``."""
    for i, text in iter_headings(lines, level):
        if predicate(text):
            return section_span(lines, i)
    return None


def trim_span(lines: list[str], start: int, end: int) -> tuple[int, int]:
    """Shrink ``[start, end)`` past trailing blank lines and horizontal rules.

    An entry's block runs up to the next heading, but the blank line and
    ``---`` before that heading belong to the *parent* section's layout, not to
    the entry. Replacing an entry must leave them in place.
    """
    while end > start and (not lines[end - 1].strip() or is_rule(lines[end - 1])):
        end -= 1
    return start, end


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _is_delimiter_row(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c) for c in cells if c != "")


def find_table(lines: list[str], start: int, end: int) -> tuple[int, int] | None:
    """Span of the first pipe table inside ``[start, end)``.

    The span covers the header row, the delimiter row and every body row,
    including commented-out example rows so a rebuild replaces them too.
    """
    for i in range(start, end):
        if not lines[i].strip().startswith("|"):
            continue
        if i + 1 < end and _is_delimiter_row(lines[i + 1]):
            j = i + 2
            while j < end:
                stripped = lines[j].strip()
                if stripped.startswith("|"):
                    j += 1
                elif stripped.startswith("<!--") and "|" in stripped:
                    j += 1  # a commented example row still belongs to the table
                else:
                    break
            return i, j
    return None


def parse_table(lines: list[str], start: int, end: int) -> tuple[list[str], list[list[str]]]:
    """Return ``(headers, rows)`` for the first table in ``[start, end)``."""
    span = find_table(lines, start, end)
    if not span:
        return [], []
    t_start, t_end = span
    headers = _split_row(lines[t_start])
    rows = []
    mask = comment_mask(lines)
    for i in range(t_start + 2, t_end):
        if mask[i] or not lines[i].strip().startswith("|"):
            continue
        rows.append(_split_row(lines[i]))
    return headers, rows


def render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        padded = list(row) + [EMPTY] * (len(headers) - len(row))
        out.append("| " + " | ".join(str(c) if str(c).strip() else EMPTY
                                     for c in padded[:len(headers)]) + " |")
    return out


# --------------------------------------------------------------------------
# Inline field helpers
# --------------------------------------------------------------------------

_LINK = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")


def strip_links(text: str) -> str:
    """``[US-014](User-Stories.md#us-014)`` -> ``US-014``."""
    return _LINK.sub(r"\1", text)


def link_targets(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _LINK.finditer(text)]


def bold_field(lines: list[str], label: str) -> str | None:
    """Value of a ``**Label:** value`` line, with or without a list bullet."""
    pattern = re.compile(r"^\s*(?:[-*]\s+)?\*\*" + re.escape(label) + r":?\*\*:?\s*(.*)$")
    mask = comment_mask(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = pattern.match(line)
        if m:
            return m.group(1).strip()
    return None


def bullets(lines: list[str], start: int, end: int) -> list[str]:
    """Top-level ``- `` / ``1. `` bullet texts inside ``[start, end)``."""
    mask = comment_mask(lines)
    out = []
    for i in range(start, min(end, len(lines))):
        if mask[i]:
            continue
        m = re.match(r"^\s{0,3}(?:[-*]|\d+\.)\s+(.*)$", lines[i])
        if m and m.group(1).strip():
            out.append(m.group(1).strip())
    return out


def clean(value: str | None) -> str:
    """Normalise a cell: ``None``/blank/placeholder all become the EMPTY dash."""
    if value is None:
        return EMPTY
    value = value.strip()
    if not value or value in {"-", "--", EMPTY, "_none_", "—"}:
        return EMPTY
    return value


def is_empty(value: str | None) -> bool:
    return clean(value) == EMPTY
