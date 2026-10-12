"""The ledger's vocabulary: states, emoji and the order things are written in.

These constants mirror `references/entry-templates.md` and the "two state
machines" section of `SKILL.md`. They are the single place to change if the
skill's vocabulary ever moves, and `tests/run_tests.py` asserts that the
templates shipped alongside still agree with them.
"""

from __future__ import annotations

EMPTY = "—"

# --------------------------------------------------------------------------
# Stories
# --------------------------------------------------------------------------

# Section order in User-Stories.md is also the row order of its index table.
STORY_STATES = ["Ready", "In Sprint", "Delivered", "Paused", "Discarded"]

STORY_STATE_LABEL = {
    "Draft": "\U0001f4dd Draft",            # 📝 — lives only as an epic index line
    "Ready": "✅ Ready",                # ✅
    "In Sprint": "\U0001f3c3 In Sprint",    # 🏃
    "Delivered": "✅ Delivered",        # ✅
    "Paused": "❄️ Paused",        # ❄️
    "Discarded": "\U0001f5d1️ Discarded",  # 🗑️
}

# The emoji that sits after the title on a story's own entry.
STORY_STATE_EMOJI = {
    "Draft": "\U0001f4a1",                  # 💡
    "Ready": "\U0001f4a1",                  # 💡
    "In Sprint": "\U0001f3c3",              # 🏃
    "Delivered": "✅",                  # ✅
    "Paused": "❄️",               # ❄️
    "Discarded": "\U0001f5d1️",        # 🗑️
}

# --------------------------------------------------------------------------
# Epics
# --------------------------------------------------------------------------

EPIC_STATES = ["Proposed", "In Progress", "Done", "Paused", "Discarded"]

EPIC_STATE_LABEL = {
    "Proposed": "\U0001f4a1 Proposed",      # 💡
    "In Progress": "\U0001f528 In Progress",  # 🔨
    "Done": "✅ Done",                  # ✅
    "Paused": "❄️ Paused",        # ❄️
    "Discarded": "\U0001f5d1️ Discarded",  # 🗑️
}

EPIC_STATE_EMOJI = {k: v.split(" ", 1)[0] for k, v in EPIC_STATE_LABEL.items()}

# --------------------------------------------------------------------------
# Bugs
# --------------------------------------------------------------------------

BUG_STATES = ["Inbox", "Triaged", "Confirmed", "In Sprint", "Fixed",
              "Deferred", "Won't fix"]

BUG_STATE_LABEL = {
    "Inbox": "\U0001f41b Inbox",            # 🐛
    "Triaged": "\U0001f50d Triaged",        # 🔍
    "Confirmed": "\U0001f52c Confirmed",    # 🔬
    "In Sprint": "\U0001f6e0️ In Sprint",  # 🛠️
    "Fixed": "✅ Fixed",                # ✅
    "Deferred": "❄️ Deferred",    # ❄️
    "Won't fix": "\U0001f6ab Won't fix",    # 🚫
}

BUG_STATE_EMOJI = {k: v.split(" ", 1)[0] for k, v in BUG_STATE_LABEL.items()}

SEVERITIES = ["critical", "major", "minor", "trivial"]

# --------------------------------------------------------------------------
# Shared
# --------------------------------------------------------------------------

PRIORITIES = ["\U0001f534", "\U0001f7e1", "\U0001f7e2"]   # 🔴 high · 🟡 medium · 🟢 low
PRIORITY_NAME = {"\U0001f534": "High", "\U0001f7e1": "Medium", "\U0001f7e2": "Low"}
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}

BOARD_COLUMNS = ["To Do", "In Progress", "In Review", "In PR", "Done"]

LAYERS = ["frontend", "backend", "fullstack", "infra", "design", "docs"]

FIBONACCI = [1, 2, 3, 5, 8, 13, 21]

LEDGER_FILES = [
    "Ideas.md",
    "Epic-Backlog.md",
    "User-Stories.md",
    "Bugs.md",
    "Sprint.md",
    "Sprints-History.md",
    "Releases.md",
    "Definitions.md",
]


def priority_rank(priority: str | None) -> int:
    """Sort key: high priority first, unknown last."""
    return PRIORITY_RANK.get((priority or "").strip(), len(PRIORITIES))


def id_rank(item_id: str) -> int:
    """Numeric part of ``US-014`` so IDs sort 2 < 10 rather than lexically."""
    digits = "".join(ch for ch in (item_id or "") if ch.isdigit())
    return int(digits) if digits else 0


def anchor(item_id: str) -> str:
    """``US-014`` -> ``#us-014``: the stable, rename-proof anchor."""
    return "#" + item_id.strip().lower()


def home_file(item_id: str) -> str:
    """Which ledger file holds the full entry for an ID."""
    prefix = item_id.split("-")[0].upper()
    return {
        "EPIC": "Epic-Backlog.md",
        "US": "User-Stories.md",
        "BUG": "Bugs.md",
        "TASK": "User-Stories.md",
    }.get(prefix, "User-Stories.md")


def link(item_id: str, *, same_file: bool = False) -> str:
    """Render the live link the ledger uses everywhere for an ID."""
    target = anchor(item_id) if same_file else home_file(item_id) + anchor(item_id)
    return f"[{item_id}]({target})"


def slugify(text: str, limit: int = 5) -> str:
    """``Google SSO login`` -> ``google-sso-login`` for branch names."""
    words = []
    for raw in (text or "").lower().split():
        word = "".join(ch for ch in raw if ch.isalnum())
        if word:
            words.append(word)
        if len(words) >= limit:
            break
    return "-".join(words) or "work"
