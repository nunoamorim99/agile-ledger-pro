"""The command sheet: every slash command, where it writes, and where to run it.

The descriptions are read from the shipped `commands/*.md` frontmatter rather
than copied here, so the sheet cannot drift from the plugin. This module only
adds what the frontmatter does not carry: the phase grouping, the file each
command writes, and whether the dashboard can do it or it belongs in a Claude
Code session.

A command found on disk but missing from the table below still appears, under
"Other" — a new command shows up in the sheet without anyone editing this file.
"""

from __future__ import annotations

import re
from pathlib import Path

#: group -> ordered commands. ``action`` names the dashboard action that does the
#: same job, or None when the command only makes sense in a Claude Code session.
SHEET: list[dict] = [
    {
        "group": "Capture",
        "blurb": "Instant, append-only, safe mid-work — in any language.",
        "commands": [
            {"name": "idea", "args": "<text>", "writes": "Ideas.md", "action": "add_idea"},
            {"name": "bug", "args": "<text>", "writes": "Bugs.md", "action": "add_bug"},
        ],
    },
    {
        "group": "Triage",
        "blurb": "Inbox → registered, with a typed ID.",
        "commands": [
            {"name": "triage", "args": "", "writes": "Epic-Backlog.md",
             "action": "triage_idea_to_story"},
            {"name": "triage-bug", "args": "", "writes": "Bugs.md", "action": "triage_bug"},
        ],
    },
    {
        "group": "Shape the backlog",
        "blurb": "Draft → Ready. The Definition of Ready is the gate.",
        "commands": [
            {"name": "detail-us", "args": "<US-ID>", "writes": "User-Stories.md",
             "action": "detail_story"},
            {"name": "detail-epic", "args": "<EPIC-ID>", "writes": "User-Stories.md",
             "action": "detail_story",
             "note": "On the page, detail each story from the epic's own list."},
            {"name": "create-task", "args": "<US-ID>", "writes": "User-Stories.md",
             "action": None, "note": "Optional, for a genuine FE/BE split."},
            {"name": "find-bug", "args": "<BUG-ID>", "writes": "Bugs.md", "action": None,
             "note": "Reads your code to reproduce and locate the cause."},
            {"name": "refine", "args": "", "writes": "—", "action": None,
             "note": "INVEST / DoR judgement — a reading, not a mechanical check."},
        ],
    },
    {
        "group": "Plan & run the sprint",
        "blurb": "The board tracks the fine column; the story keeps the coarse state.",
        "commands": [
            {"name": "plan-sprint", "args": "", "writes": "Sprint.md", "action": "plan_sprint"},
            {"name": "start-us", "args": "<US-ID>", "writes": "Sprint.md",
             "action": "move_board_item"},
            {"name": "start-bug", "args": "<BUG-ID>", "writes": "Sprint.md",
             "action": "move_board_item"},
            {"name": "review", "args": "<ID>", "writes": "Sprint.md", "action": "move_board_item"},
            {"name": "pr", "args": "<ID>", "writes": "Sprint.md", "action": "move_board_item",
             "note": "The page moves the card; the PR body comes from the session."},
            {"name": "done-us", "args": "<US-ID>", "writes": "Sprint.md · Releases.md",
             "action": "complete_item"},
            {"name": "done-bug", "args": "<BUG-ID>", "writes": "Sprint.md · Releases.md",
             "action": "complete_item"},
            {"name": "close-sprint", "args": "", "writes": "Sprints-History.md",
             "action": "close_sprint"},
        ],
    },
    {
        "group": "Inspect",
        "blurb": "Read-only. These are the views this dashboard already is.",
        "commands": [
            {"name": "dashboard", "args": "[--port N]", "writes": "—", "action": None,
             "note": "You are looking at it."},
            {"name": "board", "args": "", "writes": "—", "action": None, "view": "board"},
            {"name": "standup", "args": "", "writes": "—", "action": None, "view": "board",
             "note": "Alias of /board."},
            {"name": "my-work", "args": "[name]", "writes": "—", "action": None,
             "view": "overview", "note": "Use the Person filter in the top bar."},
            {"name": "status", "args": "", "writes": "—", "action": None, "view": "overview"},
            {"name": "insights", "args": "[--repo <slug>]", "writes": "—", "action": None,
             "view": "insights", "note": "The Insights tab is this, computed from the files."},
            {"name": "roadmap", "args": "", "writes": "—", "action": None, "view": "epics"},
            {"name": "guide", "args": "", "writes": "—", "action": None, "view": "commands"},
            {"name": "ledger-check", "args": "", "writes": "—", "action": "check"},
            {"name": "sync-main", "args": "", "writes": "Sprint.md", "action": None,
             "note": "Reads git in the code repo."},
        ],
    },
    {
        "group": "Release",
        "blurb": "Major.Minor, cut from the Increment.",
        "commands": [
            {"name": "release", "args": "[version]", "writes": "Releases.md",
             "action": "cut_release"},
            {"name": "changelog", "args": "", "writes": "—", "action": None,
             "view": "releases", "note": "Derived notes — ask in the session."},
        ],
    },
    {
        "group": "Ledger & repos",
        "blurb": "The ledger repo itself and the projects it covers.",
        "commands": [
            {"name": "init-ledger", "args": "[path]", "writes": "Registry.md · Config.md",
             "action": None},
            {"name": "whoami", "args": "[name|@handle]", "writes": "Me.local.md",
             "action": "update_me",
             "note": "The session can match your gh login; the page offers the roster."},
            {"name": "register-repo", "args": "<path|remote>", "writes": "Registry.md",
             "action": None},
            {"name": "switch-methodology", "args": "<scrum|kanban>", "writes": "Definitions.md",
             "action": None,
             "note": "Settings shows the same derived numbers; the session does the reconstruction."},
            {"name": "migrate-ledger", "args": "[path]", "writes": "—", "action": None},
            {"name": "ledger-commit", "args": "", "writes": "git", "action": "commit"},
            {"name": "discover-repos", "args": "", "writes": "Registry.md", "action": None},
            {"name": "workspace-sync", "args": "", "writes": "many", "action": None},
            {"name": "workspace-status", "args": "", "writes": "—", "action": None},
        ],
    },
]

#: Why a command is session-only, so the sheet can say so instead of just "no".
SESSION_ONLY_REASON = {
    "find-bug": "Reads your source to reproduce the bug and locate the cause.",
    "refine": "A judgement call on story quality, not a mechanical edit.",
    "create-task": "Rare by design — ask in the session when you truly need one.",
    "sync-main": "Runs git in the code repo and maps merges to story IDs.",
    "changelog": "Writes prose for humans from the release history.",
    "init-ledger": "Creates the ledger repo and offers git init.",
    "register-repo": "Reads a repo's git remote and scaffolds its folder.",
    "switch-methodology": "Proposes the switch with derived numbers, and reconstructs drafts from git.",
    "migrate-ledger": "Moves a pre-2.0 folder and cleans the code repo on a branch.",
    "discover-repos": "Scans your GitHub org and proposes clones.",
    "workspace-sync": "Reads git across every repo and drafts reconstructed work.",
    "workspace-status": "Spans every repo; this page shows one at a time.",
    "dashboard": "You are looking at it.",
    "board": "This page is the board.",
    "standup": "This page is the board.",
    "my-work": "Use the Person filter in the top bar.",
    "status": "The Overview tab is this.",
    "insights": "The Insights tab is this.",
    "roadmap": "The Epics tab is this.",
    "guide": "This sheet is it.",
    "detail-epic": "Detail each story from its epic on the Epics tab.",
    "pr": "The page moves the card; the PR body is written in the session.",
}

_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _commands_dir(dashboard_root: Path) -> Path | None:
    """Find the shipped commands folder next to the dashboard.

    Two layouts ship: the plugin (`<plugin>/commands`) and the manual bundle,
    which nests commands one level deeper (`.claude/commands/agile-ledger-pro`).
    """
    parent = dashboard_root.parent
    for candidate in (parent / "commands" / "agile-ledger-pro", parent / "commands"):
        if candidate.is_dir() and any(candidate.glob("*.md")):
            return candidate
    return None


def _descriptions(folder: Path | None) -> dict[str, str]:
    if not folder:
        return {}
    out = {}
    for path in sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = _FRONT.match(text)
        if not m:
            continue
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "description":
                out[path.stem] = value.strip()
                break
    return out


def sheet(dashboard_root: Path, available_actions: set[str]) -> dict:
    """The command sheet, merged with the descriptions on disk."""
    folder = _commands_dir(dashboard_root)
    described = _descriptions(folder)
    listed = {c["name"] for group in SHEET for c in group["commands"]}

    groups = []
    for group in SHEET:
        rows = []
        for command in group["commands"]:
            name = command["name"]
            action = command.get("action")
            if action and action not in available_actions:
                action = None
            rows.append({
                "name": name,
                "args": command.get("args", ""),
                "description": described.get(name, ""),
                "writes": command.get("writes", "—"),
                "action": action,
                "view": command.get("view"),
                "note": command.get("note") or SESSION_ONLY_REASON.get(name, ""),
                "here": bool(action) or bool(command.get("view")),
            })
        groups.append({"group": group["group"], "blurb": group["blurb"], "commands": rows})

    extra = sorted(set(described) - listed)
    if extra:
        groups.append({
            "group": "Other",
            "blurb": "Shipped with the plugin but not yet placed in this sheet.",
            "commands": [{"name": n, "args": "", "description": described[n],
                          "writes": "—", "action": None, "view": None,
                          "note": "", "here": False} for n in extra],
        })

    return {
        "groups": groups,
        "source": str(folder) if folder else None,
        "total": sum(len(g["commands"]) for g in groups),
    }
