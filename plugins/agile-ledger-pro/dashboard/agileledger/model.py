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


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------

# The roles the `## Team` roster in the ledger root's Config.md recognises.
#
# A role here is a *label*, never a permission. The ledger is Markdown in a git
# repo: everyone who can read it can edit it, and the dashboard is a server each
# person runs on their own machine against their own clone, with no accounts and
# no authentication. Nothing in this codebase can stop a developer from opening
# Config.md.
#
# What the roster does buy is real, which is why it exists: names the dashboard
# can offer instead of free-text assignees, a `Me` that resolves whether it is
# written as a handle or a display name, and the owner list `/init-ledger` writes
# into CODEOWNERS — where the git host *can* enforce that a change to the team's
# rules needs the PO's approval before it reaches main.
ROLES = ["PO", "PM", "SM", "Dev", "QA", "Design"]

ROLE_NAME = {
    "PO": "Product Owner",
    "PM": "Product Manager",
    "SM": "Scrum Master",
    "Dev": "Developer",
    "QA": "QA",
    "Design": "Design",
}

# The roles that own the rules — the Definition of Ready and Done, the estimation
# scale, the ledger's own config. These become the CODEOWNERS of Config.md and
# every Definitions.md.
CONFIG_OWNERS = ["PO", "PM"]

# Who runs which action, once a team has written a roster.
#
# The same guardrail the Settings screen uses, and the same caveat: this is a
# label being read, not a permission being enforced. Each person runs the
# dashboard themselves against their own clone, and the file it asks who they
# are is in their working tree. It stops the wrong button being pressed by
# accident, which is most wrong buttons, and stops nothing else.
#
# Roles that shape *what gets built* — the backlog is the Product Owner's, and
# a developer should not be the one deciding an idea becomes an epic.
BACKLOG_ROLES = ["PO", "PM"]

# Roles that run the *ceremony*. Separate from the above because a Scrum
# Master plans and closes sprints without owning the backlog.
SPRINT_ROLES = ["PO", "PM", "SM"]

# An action absent from this map is open to the whole team, which is the
# deliberate default: a new action belongs to everybody until somebody decides
# it does not. Delete a line here to open that action up again — one line is
# the whole change, in both the dashboard and the command sheet.
ACTION_ROLES = {
    # Shaping the backlog: what is worth building, and in what order.
    "add_idea": BACKLOG_ROLES,
    "discard_idea": BACKLOG_ROLES,
    "triage_idea_to_epic": BACKLOG_ROLES,
    "triage_idea_to_story": BACKLOG_ROLES,
    "triage_bug": BACKLOG_ROLES,
    "move_story_to_epic": BACKLOG_ROLES,
    # Writing a Draft up into a Ready story: the story sentence and the
    # acceptance criteria are the Product Owner's, and the Definition of Ready
    # is their gate. Editing the story afterwards is `update_story`, which
    # stays open — the estimate lives there and the estimate is the
    # developer's own (see SKILL.md on who owns size and who owns value).
    "detail_story": BACKLOG_ROLES,
    "cut_release": BACKLOG_ROLES,
    # The sprint ceremony.
    "plan_sprint": SPRINT_ROLES,
    "pull_into_sprint": SPRINT_ROLES,
    "close_sprint": SPRINT_ROLES,
    # The team's shared rules — the same set the Settings screen locks.
    "update_project_config": CONFIG_OWNERS,
    "update_ledger_config": CONFIG_OWNERS,
    "update_team": CONFIG_OWNERS,
    "update_checklist": CONFIG_OWNERS,
}

# Everything not listed above is open, and these are the ones it matters for,
# so they are named here to be tested rather than left to a reader's trust:
#
#   add_bug          anyone finds a bug; a report nobody can file is a bug lost
#   update_story     editing a story that exists, where the estimate and the
#                    assignee live — the estimate is the developer's by the
#                    skill's own rule, so this one must stay open
#   set_story_state  · set_bug_state · move_board_item · complete_item
#                    the board is the developers' instrument
#   set_blocked      saying you are stuck must never need permission
#   update_bug       fixing is development
#   commit · check   reading the ledger and committing your own edits to it
#   update_me        your own name is yours
OPEN_ACTIONS = [
    "add_bug", "update_story", "set_story_state", "update_bug",
    "set_bug_state", "move_board_item", "set_blocked", "complete_item",
    "commit", "check", "update_me",
]


def action_roles(action: str) -> list[str]:
    """Roles that may run ``action``, or ``[]`` when it is open to everyone."""
    return ACTION_ROLES.get(action, [])

# What people actually type. The roster is written by hand as often as by the
# dashboard, so "Product Owner", "po" and "PO" all have to land in one bucket.
ROLE_ALIASES = {
    "po": "PO", "product owner": "PO", "productowner": "PO", "owner": "PO",
    "pm": "PM", "product manager": "PM", "productmanager": "PM",
    "project manager": "PM", "manager": "PM",
    "sm": "SM", "scrum master": "SM", "scrummaster": "SM",
    "dev": "Dev", "developer": "Dev", "engineer": "Dev", "eng": "Dev",
    "devs": "Dev", "development": "Dev",
    "qa": "QA", "test": "QA", "tester": "QA", "quality": "QA",
    "design": "Design", "designer": "Design", "ux": "Design", "ui": "Design",
}


def normalise_role(role: str | None) -> str:
    """Canonical role for whatever was written, or the text itself.

    An unrecognised role is returned unchanged rather than dropped or coerced:
    the roster belongs to the team, and a dashboard that silently renamed
    someone's role would be lying about what the file says.
    """
    raw = (role or "").strip()
    if not raw or raw == EMPTY:
        return ""
    return ROLE_ALIASES.get(raw.lower(), raw)


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
