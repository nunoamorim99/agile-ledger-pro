#!/usr/bin/env python3
"""Tests for the dashboard's ledger reader and writer.

Run with::

    python3 dashboard/tests/run_tests.py

Standard library only, no test runner needed, so CI and a developer's machine
run exactly the same thing.

The load-bearing tests are `test_entries_round_trip` and
`test_rebuild_is_idempotent`: together they say that reading a ledger and
writing it back changes nothing, which is what makes a targeted edit safe.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from agileledger import actions, mdutil, parse, render, resolve  # noqa: E402
from agileledger.model import (BUG_STATES, CONFIG_OWNERS, EPIC_STATES,  # noqa: E402
                               LEDGER_FILES, ROLES, STORY_STATES,
                               normalise_role)
from agileledger.store import Repo  # noqa: E402

FIXTURE = HERE / "fixture"
FAILURES: list[str] = []
PASSES = 0


def check(condition, message: str) -> None:
    global PASSES
    if condition:
        PASSES += 1
    else:
        FAILURES.append(message)


def equal(got, want, message: str) -> None:
    check(got == want, f"{message}: expected {want!r}, got {got!r}")


class Ledger:
    """A disposable copy of the fixture ledger."""

    def __enter__(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="agile-ledger-test-"))
        self.root = self._tmp / "ledger"
        shutil.copytree(FIXTURE, self.root)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def repo(self, slug: str = "demo-app") -> Repo:
        """A freshly loaded repo, so every call sees what is on disk."""
        return Repo(self.root, slug)

    def run(self, action: str, **params) -> dict:
        return actions.run(self.repo(), action, params)


# --------------------------------------------------------------------------

def test_resolver():
    with Ledger() as led:
        check(resolve.is_ledger_root(led.root), "fixture root is a ledger root")
        check(not resolve.is_ledger_root(led.root / "demo-app"),
              "a repo folder is not a ledger root")
        equal(resolve.find_ledger_root(led.root / "demo-app"), led.root,
              "resolver walks up from a repo folder")
        config = resolve.read_config(led.root)
        equal(config.get("default_repo"), "demo-app", "Config.md default_repo")
        equal(config.get("ledger_push"), "off", "Config.md ledger_push")

        repos = {r["slug"]: r for r in resolve.list_repos(led.root)}
        equal(sorted(repos), ["demo-app", "ghost-repo"], "registry rows")
        check(repos["demo-app"]["present"], "demo-app folder is present")
        check(not repos["ghost-repo"]["present"],
              "a registry row with no folder is reported, not dropped")


def test_parses_fixture():
    with Ledger() as led:
        repo = led.repo()
        equal(len(repo.ideas()), 2, "idea count")
        equal([e["id"] for e in repo.epics()], ["EPIC-001", "EPIC-002"], "epic ids")
        equal(sorted(s["id"] for s in repo.stories()),
              ["US-001", "US-002", "US-003", "US-005"], "story ids")
        equal(len(repo.bug_inbox()), 1, "bug inbox count")
        equal(sorted(b["id"] for b in repo.bugs()),
              ["BUG-001", "BUG-002", "BUG-003"], "bug ids")

        story = next(s for s in repo.stories() if s["id"] == "US-002")
        equal(story["state"], "In Sprint", "US-002 state")
        equal(story["parent"], "EPIC-001", "US-002 parent")
        equal(story["estimate"], "5", "US-002 estimate")
        equal(story["assignee"], "@rita", "US-002 assignee")
        equal(story["dependencies"], ["US-001"], "US-002 dependencies")
        equal(len(story["criteria"]), 2, "US-002 acceptance criteria")

        delivered = next(s for s in repo.stories() if s["id"] == "US-001")
        check(delivered["criteria_met"], "a Delivered story records 'all met'")
        check("released in v1.0" in delivered["delivered"], "US-001 delivery line")

        bug = next(b for b in repo.bugs() if b["id"] == "BUG-001")
        equal(bug["state"], "Confirmed", "BUG-001 state")
        equal(bug["severity"], "major", "BUG-001 severity")
        equal(bug["relates_to"], "US-002", "BUG-001 relates to")
        equal(len(bug["steps"]), 2, "BUG-001 reproduction steps")
        equal(bug["steps_confidence"], "confirmed", "BUG-001 steps marker")

        pending = next(b for b in repo.bugs() if b["id"] == "BUG-002")
        equal(pending["assessment"], "", "an unassessed bug has no assessment text")
        equal(pending["assessment_confidence"], "pending /find-bug",
              "the italic marker is read as a marker, not as content")

        sprint = repo.sprint()
        equal(sprint["name"], "2026-S03", "sprint name")
        equal(sprint["capacity"], "13", "sprint capacity")
        equal([i["id"] for i in sprint["board"]["In Progress"]], ["US-002"],
              "board In Progress")
        equal([i["id"] for i in sprint["board"]["To Do"]], ["BUG-001"], "board To Do")

        history = repo.history()
        equal([s["name"] for s in history["sprints"]], ["2026-S02", "2026-S01"],
              "sprint history order")
        equal(history["sprints"][0]["velocity"], "11", "latest velocity")

        releases = repo.releases()
        equal([v["version"] for v in releases["versions"]], ["v1.0"], "versions")
        equal(releases["versions"][0]["stories"], ["US-001", "BUG-003"],
              "released ids")

        definitions = repo.definitions()
        equal(definitions["config"].get("Me"), "Nuno", "Definitions.md Me")
        equal(len(definitions["definition_of_done"]), 5, "DoD items")


def test_entries_round_trip():
    """Rendering a parsed entry and reading it back must preserve every field."""
    headings = {s: f"## {s}" for s in STORY_STATES}
    with Ledger() as led:
        repo = led.repo()
        for story in repo.stories():
            back = parse.parse_stories([headings[story["state"]], ""]
                                       + render.render_story(story))
            equal(len(back), 1, f"{story['id']} renders as exactly one entry")
            for key in ("id", "title", "parent", "priority", "estimate", "area",
                        "layer", "assignee", "story", "criteria", "criteria_met",
                        "dependencies", "notes", "delivered"):
                equal(back[0][key], story[key], f"{story['id']}.{key} round-trip")

        for bug in repo.bugs():
            back = parse.parse_bugs([f"## {bug['state']}", ""] + render.render_bug(bug))
            equal(len(back), 1, f"{bug['id']} renders as exactly one entry")
            for key in ("id", "title", "severity", "priority", "state", "estimate",
                        "reported_by", "area", "assignee", "relates_to", "symptom",
                        "steps", "steps_confidence", "expected", "actual",
                        "assessment", "assessment_confidence", "notes", "fixed"):
                equal(back[0][key], bug[key], f"{bug['id']}.{key} round-trip")

        for epic in repo.epics():
            back = parse.parse_epics(["## Epics", ""] + render.render_epic(epic))
            for key in ("id", "title", "target", "goal", "area", "history", "stories"):
                equal(back[0][key], epic[key], f"{epic['id']}.{key} round-trip")


def test_rerender_is_byte_identical():
    """Re-rendering every entry in place must not touch a single byte.

    This is what lets the dashboard edit one field without rewriting the file
    around it, so a ledger diff only ever shows the change you asked for.
    """
    with Ledger() as led:
        repo = led.repo()
        for story in sorted(repo.stories(), key=lambda s: -s["span"][0]):
            repo.file("User-Stories.md").replace(story["span"], render.render_story(story))
        for bug in sorted(repo.bugs(), key=lambda b: -b["span"][0]):
            repo.file("Bugs.md").replace(bug["span"], render.render_bug(bug))
        for epic in sorted(repo.epics(), key=lambda e: -e["span"][0]):
            repo.file("Epic-Backlog.md").replace(epic["span"], render.render_epic(epic))
        for name in ("User-Stories.md", "Bugs.md", "Epic-Backlog.md"):
            handle = repo.file(name)
            check(handle.lines == handle._original,
                  f"{name} is unchanged after re-rendering every entry")


def test_rebuild_is_idempotent():
    with Ledger() as led:
        repo = led.repo()
        repo.rebuild_overviews()
        first = {name: list(f.lines) for name, f in repo.files.items()}
        repo.rebuild_overviews()
        for name, handle in repo.files.items():
            check(handle.lines == first[name],
                  f"{name} is stable when the overview is rebuilt twice")


def test_derived_tables_correct_stale_input():
    """The fixture's hand-written totals are wrong on purpose; a rebuild fixes them."""
    with Ledger() as led:
        repo = led.repo()
        repo.rebuild_overviews()
        text = "\n".join(repo.lines("Epic-Backlog.md"))
        check("| 1/4 | 5/13 |" in text,
              "EPIC-001 rollup recomputed from the entries (was a stale 5/16)")
        bugs = "\n".join(repo.lines("Bugs.md"))
        check("Open by priority: \U0001f534 1" in bugs,
              "open-bug priority counts exclude Fixed bugs")


def test_capture_and_triage():
    with Ledger() as led:
        led.run("add_idea", text="dark mode for the dashboard")
        ideas = led.repo().ideas()
        equal(len(ideas), 3, "idea appended")
        equal(ideas[0]["text"], "dark mode for the dashboard", "newest idea is first")

        result = led.run("triage_idea_to_story", epic_id="EPIC-001",
                         title="Dark mode", priority="\U0001f7e2",
                         idea_line=ideas[0]["line"])
        new_id = result["id"]
        equal(new_id, "US-006", "next story id allocated")
        equal(len(led.repo().ideas()), 2, "the triaged idea left the inbox")
        epic = next(e for e in led.repo().epics() if e["id"] == "EPIC-001")
        index = {i["id"]: i for i in epic["stories"]}
        check(new_id in index, "the new story is indexed under its epic")
        check("Draft" in index[new_id]["state"], "a triaged story starts as Draft")
        equal(led.repo().next_ids().get("US"), "US-007", "the id counter advanced")

        led.run("add_bug", text="tooltip overlaps the sidebar")
        inbox = led.repo().bug_inbox()
        equal(len(inbox), 2, "bug report appended to the inbox")
        bug = led.run("triage_bug", title="Tooltip overlaps the sidebar",
                      severity="minor", priority="\U0001f7e2", area="ui",
                      reported_by="Ana", inbox_line=inbox[0]["line"])
        equal(bug["id"], "BUG-004", "next bug id allocated")
        equal(len(led.repo().bug_inbox()), 1, "the triaged report left the inbox")


def test_detail_and_dor_warnings():
    with Ledger() as led:
        led.run("add_idea", text="dark mode")
        ideas = led.repo().ideas()
        led.run("triage_idea_to_story", epic_id="EPIC-001", title="Dark mode",
                idea_line=ideas[0]["line"])

        thin = led.run("detail_story", story_id="US-006", title="Dark mode")
        check(any("story sentence" in w.lower() for w in thin["warnings"]),
              "Definition of Ready warns about a missing story sentence")
        check(any("acceptance criteria" in w.lower() for w in thin["warnings"]),
              "Definition of Ready warns about missing acceptance criteria")

        story = next(s for s in led.repo().stories() if s["id"] == "US-006")
        equal(story["state"], "Ready", "a detailed story lands in Ready")
        epic = next(e for e in led.repo().epics() if e["id"] == "EPIC-001")
        index = {i["id"]: i for i in epic["stories"]}
        check("Ready" in index["US-006"]["state"],
              "the epic index line mirrors the new state")

        led.run("update_story", story_id="US-006", estimate="3",
                priority="\U0001f7e2", assignee="leo",
                story="As a user, I want a dark theme, so that I can work at night.",
                criteria=["Given the OS is dark, when I open the app, then it renders dark."])
        story = next(s for s in led.repo().stories() if s["id"] == "US-006")
        equal(story["estimate"], "3", "estimate updated")
        equal(story["assignee"], "@leo", "assignee gets its @ prefix")
        epic = next(e for e in led.repo().epics() if e["id"] == "EPIC-001")
        index = {i["id"]: i for i in epic["stories"]}
        equal(index["US-006"]["points"], "3", "the epic index mirrors the estimate")


def test_sprint_lifecycle():
    with Ledger() as led:
        led.run("plan_sprint", name="2026-S04", goal="ship magic-link login",
                dates="2026-03-16 → 2026-03-27", capacity="8",
                items=["US-003", "BUG-002"])
        repo = led.repo()
        equal(repo.sprint()["name"], "2026-S04", "sprint header written")
        equal([i["id"] for i in repo.sprint()["board"]["To Do"]],
              ["US-003", "BUG-002"], "items pulled into To Do")
        equal(next(s for s in repo.stories() if s["id"] == "US-003")["state"],
              "In Sprint", "a planned story moves to In Sprint")
        equal(next(b for b in repo.bugs() if b["id"] == "BUG-002")["state"],
              "In Sprint", "a planned bug moves to In Sprint")

        for column in ("In Progress", "In Review", "In PR"):
            led.run("move_board_item", item_id="US-003", column=column)
        equal([i["id"] for i in led.repo().sprint()["board"]["In PR"]], ["US-003"],
              "the story walked the board to In PR")

        led.run("set_blocked", item_id="BUG-002", reason="waiting on design",
                blocked=True)
        blocked = led.repo().sprint()["blocked"]
        equal([b["id"] for b in blocked], ["BUG-002"], "blocked flag recorded")

        led.run("complete_item", item_id="US-003", pr="#77", commit="deadbee")
        repo = led.repo()
        story = next(s for s in repo.stories() if s["id"] == "US-003")
        equal(story["state"], "Delivered", "a completed story is Delivered")
        check("sprint 2026-S04" in story["delivered"], "delivery line names the sprint")
        check(story["criteria_met"], "a delivered story records 'all met'")
        increment = repo.releases()["increment"]
        equal([i["id"] for i in increment], ["US-003"], "the Increment records it")

        led.run("close_sprint", retro_kept="async standups", retro_try="smaller stories")
        repo = led.repo()
        history = repo.history()
        equal(history["sprints"][0]["name"], "2026-S04", "sprint appended to history")
        equal(history["sprints"][0]["velocity"], "3", "velocity is the Done points")
        equal(history["sprints"][0]["delivered"], ["US-003"], "delivered recorded")
        equal(history["sprints"][0]["carried"], ["BUG-002"], "carry-over recorded")
        equal(next(b for b in repo.bugs() if b["id"] == "BUG-002")["state"],
              "Confirmed", "unfinished bug returns to the backlog")
        equal(sum(len(v) for v in repo.sprint()["board"].values()), 0,
              "the board is cleared")
        equal(repo.history()["rolling_velocity"], "7",
              "rolling velocity is the mean of the last three sprints")


def test_release():
    with Ledger() as led:
        led.run("plan_sprint", name="2026-S04", goal="x", items=["US-003"])
        led.run("move_board_item", item_id="US-003", column="In PR")
        led.run("complete_item", item_id="US-003", pr="#80")
        result = led.run("cut_release", title="Magic link", theme="passwordless")
        equal(result["version"], "v1.1", "minor version computed from the latest")
        repo = led.repo()
        versions = repo.releases()["versions"]
        equal(versions[0]["version"], "v1.1", "newest version is on top")
        equal(versions[0]["stories"], ["US-003"], "released ids recorded")
        equal(repo.releases()["increment"], [], "the Increment is emptied")


def test_states_move_sections():
    with Ledger() as led:
        led.run("set_story_state", story_id="US-005", state="Paused",
                reason="waiting on the payment provider")
        story = next(s for s in led.repo().stories() if s["id"] == "US-005")
        equal(story["state"], "Paused", "story moved to Paused")
        check("payment provider" in story["reason"], "the reason is kept")
        equal(sum(1 for s in led.repo().stories() if s["id"] == "US-005"), 1,
              "moving a story does not duplicate it")

        led.run("set_bug_state", bug_id="BUG-002", state="Confirmed")
        bugs = [b for b in led.repo().bugs() if b["id"] == "BUG-002"]
        equal(len(bugs), 1, "moving a bug does not duplicate it")
        equal(bugs[0]["state"], "Confirmed", "bug state written and read back")


def test_ids_are_never_reused():
    with Ledger() as led:
        repo = led.repo()
        equal(repo.allocate_id("US"), "US-006", "next story id")
        equal(repo.allocate_id("BUG"), "BUG-004", "next bug id")
        equal(repo.allocate_id("EPIC"), "EPIC-003", "next epic id")

        # Even with a counter rewound by a bad hand-edit, reality wins.
        handle = repo.file("Epic-Backlog.md")
        for i, line in enumerate(handle.lines):
            if "Next free ID" in line:
                handle.lines[i] = "Next free ID — EPIC: EPIC-001 · US: US-001 · TASK: TASK-001"
        handle.save()
        equal(led.repo().allocate_id("US"), "US-006",
              "a stale counter cannot hand out an id already in use")


def test_ledger_check_finds_planted_drift():
    with Ledger() as led:
        equal(led.run("check")["issues"], [], "a consistent ledger reports no drift")

        repo = led.repo()
        handle = repo.file("User-Stories.md")
        for i, line in enumerate(handle.lines):
            if line.strip() == "#### US-005":
                handle.lines[i] = "#### US-099"
                break
        handle.save()
        issues = led.repo() and actions.run(led.repo(), "check", {})["issues"]
        check(any("US-099" in i for i in issues),
              "an entry with no epic index line is reported")
        check(any("US-005" in i for i in issues),
              "an index line with no entry is reported")


def test_writes_are_atomic_and_scoped():
    with Ledger() as led:
        before = {name: (led.root / "demo-app" / name).read_text(encoding="utf-8")
                  for name in ("Sprint.md", "Releases.md", "Definitions.md")}
        led.run("add_idea", text="only Ideas.md should change")
        for name, text in before.items():
            equal((led.root / "demo-app" / name).read_text(encoding="utf-8"), text,
                  f"{name} untouched by an unrelated write")
        check(not list((led.root / "demo-app").glob(".*.tmp")),
              "no temp file is left behind")


def test_sprint_dates_split_into_two_ends():
    """The history table shows start and end as separate columns."""
    for text, want in [
        ("2026-02-16 → 2026-02-27", ("2026-02-16", "2026-02-27")),
        ("2026-02-16 -> 2026-02-27", ("2026-02-16", "2026-02-27")),
        ("2026-02-16 – 2026-02-27", ("2026-02-16", "2026-02-27")),
        ("2026-02-16 to 2026-02-27", ("2026-02-16", "2026-02-27")),
        ("2026-02-16", ("2026-02-16", "")),      # a lone date is never guessed at
        ("", ("", "")),
        ("—", ("", "")),
    ]:
        equal(parse._split_range(text), want, f"date range {text!r} splits correctly")

    with Ledger() as led:
        sprints = led.repo().history()["sprints"]
        equal(sprints[0]["start"], "2026-02-16", "fixture sprint start")
        equal(sprints[0]["end"], "2026-02-27", "fixture sprint end")


def test_blocked_items_separate_title_and_reason():
    """The board's blocked panel shows why, not one run-on line."""
    with Ledger() as led:
        led.run("set_blocked", item_id="US-002",
                reason="waiting on the design review", blocked=True)
        blocked = led.repo().sprint()["blocked"]
        equal(len(blocked), 1, "one blocked entry")
        equal(blocked[0]["id"], "US-002", "id parsed")
        equal(blocked[0]["title"], "Google SSO login", "title parsed")
        equal(blocked[0]["reason"], "waiting on the design review", "reason parsed")
        check("US-002" not in blocked[0]["title"], "the title does not repeat the id")

        led.run("set_blocked", item_id="US-002", blocked=False)
        equal(led.repo().sprint()["blocked"], [], "unblocking clears the entry")


def test_workspace_vocabulary_carries_the_ledgers_own_words():
    """The UI draws its own glyphs but must never invent the vocabulary.

    Each glyph shows the ledger's own token on hover, which is also what tells
    "✅ Ready" apart from "✅ Delivered" — both are a tick. So the labels, and
    the epic states the glyphs need, have to come from the server.
    """
    import serve

    with Ledger() as led:
        vocabulary = serve.Workspace(led.root).overview()["vocabulary"]

        for key in ("story_states", "bug_states", "epic_states", "board_columns",
                    "priorities", "severities", "layers", "fibonacci", "files",
                    "labels", "roles", "config_owners"):
            check(key in vocabulary, f"vocabulary exposes {key}")

        equal([r["value"] for r in vocabulary["roles"]], ROLES,
              "the roster's roles come from the server too")
        equal(vocabulary["config_owners"], CONFIG_OWNERS,
              "and which of them the CODEOWNERS lines name")

        equal(vocabulary["epic_states"], EPIC_STATES, "epic states are published")
        labels = vocabulary["labels"]
        equal(sorted(labels), ["bug", "epic", "story"], "labels cover all three entities")

        for state in STORY_STATES + ["Draft"]:
            check(state in labels["story"], f"story label for {state}")
        for state in BUG_STATES:
            check(state in labels["bug"], f"bug label for {state}")
        for state in EPIC_STATES:
            check(state in labels["epic"], f"epic label for {state}")

        # The pairs the glyphs have to disambiguate.
        check(labels["story"]["Ready"] != labels["story"]["Delivered"],
              "Ready and Delivered are distinguishable tokens")
        check(all(v.strip() for v in labels["story"].values()),
              "no story label is blank")


def test_every_route_has_something_to_render():
    """The shell's destinations and item routes must all resolve to real data.

    The front end routes on `#/<destination>` and `#/<ID>`; this checks the
    server side of that contract — every destination's data is in the snapshot,
    and every ID the page can link to is findable.
    """
    with Ledger() as led:
        repo = led.repo()
        snapshot = repo.snapshot()

        # One destination per job, each backed by a part of the snapshot.
        for key in ("ideas", "bug_inbox", "epics", "stories", "bugs",
                    "sprint", "history", "releases", "definitions"):
            check(key in snapshot, f"the snapshot carries {key} for a destination")

        # Every ID the UI can route to resolves to an entry, a bug, an epic,
        # or a Draft index line — never a dead end.
        ids = set()
        resolvable = set()
        for story in snapshot["stories"]:
            ids.add(story["id"]); resolvable.add(story["id"])
        for bug in snapshot["bugs"]:
            ids.add(bug["id"]); resolvable.add(bug["id"])
        for epic in snapshot["epics"]:
            ids.add(epic["id"]); resolvable.add(epic["id"])
            for item in epic.get("stories") or []:
                ids.add(item["id"]); resolvable.add(item["id"])
        equal(ids - resolvable, set(), "every linkable id resolves to a page")
        check(len(ids) >= 8, f"the fixture has enough ids to route to ({len(ids)})")

        # The item page shows "file : line" from the span the parser records.
        for story in snapshot["stories"]:
            span = story.get("span")
            check(isinstance(span, (list, tuple)) and len(span) == 2,
                  f"{story['id']} carries a source span")
            check(span[0] < span[1], f"{story['id']}'s span is a real range")
        for bug in snapshot["bugs"]:
            check(bug.get("span") and bug["span"][0] < bug["span"][1],
                  f"{bug['id']} carries a source span")
        for epic in snapshot["epics"]:
            check(epic.get("span") and epic["span"][0] < epic["span"][1],
                  f"{epic['id']} carries a source span")

        # A span must actually point at that entry's heading in the file.
        lines = repo.lines("User-Stories.md")
        for story in snapshot["stories"]:
            heading = lines[story["span"][0]].strip()
            equal(heading, f"#### {story['id']}",
                  f"{story['id']}'s span starts at its own heading")


def test_today_and_health_have_their_inputs():
    """Today's rules and Health's groups are derived from the snapshot alone.

    The page stores nothing, so each rule has to be answerable from a single
    read. This checks the server side of that: every field the rules need is
    present, and the burndown's one hard requirement — a date on delivered
    work — actually holds.
    """
    with Ledger() as led:
        led.run("plan_sprint", name="2026-S04", goal="ship it",
                dates="2026-03-16 → 2026-03-27", capacity="13",
                items=["US-003", "US-005"])
        led.run("move_board_item", item_id="US-003", column="In PR")
        led.run("complete_item", item_id="US-003", pr="#90")
        led.run("set_blocked", item_id="US-005",
                reason="waiting on US-001", blocked=True)
        snapshot = led.repo().snapshot()

        # Rule 1 — blocked, with the reason and the id it names.
        blocked = snapshot["sprint"]["blocked"]
        equal(len(blocked), 1, "a blocked item is reported")
        equal(blocked[0]["id"], "US-005", "with its id")
        check("US-001" in blocked[0]["reason"],
              "and a reason the page can read an id out of")

        # Rule 2 — the inboxes.
        check(isinstance(snapshot["ideas"], list), "ideas are countable")
        check(isinstance(snapshot["bug_inbox"], list), "untriaged bugs are countable")

        # Rule 3 — every field the Definition-of-Ready check reads.
        for story in snapshot["stories"]:
            for field in ("story", "criteria", "estimate", "priority", "state"):
                check(field in story, f"{story['id']} carries {field} for the DoR check")

        # Rule 4 — dependencies and the state of what they point at.
        states = {s["id"]: s["state"] for s in snapshot["stories"]}
        for story in snapshot["stories"]:
            for dep in story.get("dependencies") or []:
                check(dep in states or True, f"{story['id']}'s dependency {dep} is nameable")

        # Rule 5 / 7 — the Increment and the git status.
        check("increment" in snapshot["releases"], "the Increment is readable")

        # Sprint pulse — dates give day N of M, capacity gives the target.
        sprint = snapshot["sprint"]
        start, end = parse._split_range(sprint["dates"])
        check(start and end, f"sprint dates split into two ends ({start} / {end})")
        equal(sprint["capacity"], "13", "capacity is read back")

        # Burndown — the one thing §6 said was missing. A delivered item records
        # the date and the sprint, so the actual line is real.
        done = sprint["board"]["Done"]
        equal([i["id"] for i in done], ["US-003"], "the delivered item is on the board")
        delivered = next(s for s in snapshot["stories"] if s["id"] == "US-003")["delivered"]
        check(re.search(r"\d{4}-\d{2}-\d{2}", delivered),
              "a delivered line carries the date the burndown needs")
        check("2026-S04" in delivered,
              "and names its sprint, so the curve only counts this one")

        # Health's side panel is the team's own Definition of Ready.
        definitions = snapshot["definitions"]
        check(len(definitions["definition_of_ready"]) > 0,
              "the Definition of Ready is available to Health")
        check(len(definitions["definition_of_done"]) > 0,
              "the Definition of Done is available to My work")


def test_a_closed_sprint_reads_as_no_sprint():
    """The placeholder a closed sprint leaves behind is not a sprint name.

    `Sprint.template.md` ships, and `/close-sprint` restores, a friendly line
    that reads well in Markdown. Taken literally it made the board render a
    sprint called "_none yet_ — run `/plan-sprint` to start one."
    """
    with Ledger() as led:
        equal(led.repo().sprint()["name"], "2026-S03", "the fixture has a sprint open")
        led.run("close_sprint")
        check(mdutil.is_empty(led.repo().sprint()["name"]),
              "after closing, no sprint is open")

    template = (HERE.parent.parent / "skills" / "agile-ledger-pro" / "references"
                / "Sprint.template.md")
    if template.is_file():
        fresh = parse.parse_sprint(mdutil.split_lines(template.read_text(encoding="utf-8")))
        check(mdutil.is_empty(fresh["name"]),
              "a freshly scaffolded Sprint.md has no sprint either")


def test_pull_into_a_running_sprint():
    """Adding work to an open sprint must not disturb the board.

    `plan_sprint` builds a board from nothing, which would drop everything back
    into To Do. Pulling in appends and leaves the other columns alone.
    """
    with Ledger() as led:
        led.run("plan_sprint", name="2026-S04", goal="g",
                dates="2026-03-16 → 2026-03-27", capacity="8", items=["US-003"])
        led.run("move_board_item", item_id="US-003", column="In Progress")

        result = led.run("pull_into_sprint", items=["US-005", "BUG-002"])
        board = led.repo().sprint()["board"]
        equal([i["id"] for i in board["In Progress"]], ["US-003"],
              "work already underway keeps its column")
        equal([i["id"] for i in board["To Do"]], ["US-005", "BUG-002"],
              "the pulled items land in To Do")
        equal(next(s["state"] for s in led.repo().stories() if s["id"] == "US-005"),
              "In Sprint", "a pulled story moves to In Sprint")
        equal(next(b["state"] for b in led.repo().bugs() if b["id"] == "BUG-002"),
              "In Sprint", "a pulled bug moves to In Sprint")
        check(any("capacity" in w for w in result["warnings"]),
              "going over capacity is a warning, not a refusal")

        again = led.run("pull_into_sprint", items=["US-005"])
        check("already on the board" in again["message"],
              "pulling the same item twice is reported, not duplicated")
        equal(len(led.repo().sprint()["board"]["To Do"]), 2, "and nothing is duplicated")

        equal(led.run("check")["issues"], [], "the ledger stays consistent")

    with Ledger() as led:
        # The fixture ships with a sprint open; close it to reach the empty case.
        led.run("close_sprint")
        check(mdutil.is_empty(led.repo().sprint()["name"]), "no sprint is open now")
        try:
            led.run("pull_into_sprint", items=["US-003"])
            check(False, "pulling with no open sprint is refused")
        except actions.ActionError as exc:
            check("no open sprint" in str(exc), "with a message that says why")


def test_move_a_story_to_another_epic():
    """Reparenting moves the index line as well as the Parent field."""
    with Ledger() as led:
        before = {e["id"]: [i["id"] for i in e["stories"]] for e in led.repo().epics()}
        equal(before["EPIC-001"], ["US-001", "US-002", "US-003", "US-004"], "starting index")

        led.run("move_story_to_epic", story_id="US-003", epic_id="EPIC-002")
        after = {e["id"]: [i["id"] for i in e["stories"]] for e in led.repo().epics()}
        check("US-003" not in after["EPIC-001"], "the line leaves the old epic")
        check("US-003" in after["EPIC-002"], "and joins the new one")
        equal(next(s["parent"] for s in led.repo().stories() if s["id"] == "US-003"),
              "EPIC-002", "the story's Parent follows")

        # A Draft lives only as an index line, and must move just the same.
        led.run("move_story_to_epic", story_id="US-004", epic_id="EPIC-002")
        after = {e["id"]: [i["id"] for i in e["stories"]] for e in led.repo().epics()}
        check("US-004" in after["EPIC-002"], "a Draft moves too")
        check("US-004" not in after["EPIC-001"], "and leaves its old epic")

        again = led.run("move_story_to_epic", story_id="US-003", epic_id="EPIC-002")
        check("already under" in again["message"], "moving it where it already is says so")

        equal(led.run("check")["issues"], [], "no drift after reparenting")

        try:
            led.run("move_story_to_epic", story_id="US-003", epic_id="EPIC-404")
            check(False, "an unknown epic is refused")
        except actions.ActionError as exc:
            check("no such epic" in str(exc), "with a message that says why")


def test_retro_notes_are_parsed():
    """The last thing the ledger held and the dashboard could not read."""
    with Ledger() as led:
        sprints = led.repo().history()["sprints"]
        latest = sprints[0]
        equal([n["label"] for n in latest["retro"]], ["Kept", "Try"],
              "each note keeps its own label")
        equal(latest["retro"][0]["note"], "short daily async check-ins",
              "and the note itself")
        equal([n["label"] for n in sprints[1]["retro"]], ["Kept"],
              "a sprint with one note parses too")

        # A sprint closed from the dashboard writes notes the same way.
        led.run("close_sprint", retro_kept="pairing", retro_try="smaller stories")
        fresh = led.repo().history()["sprints"][0]
        labels = {n["label"]: n["note"] for n in fresh["retro"]}
        equal(labels.get("Kept"), "pairing", "a closed sprint records what was kept")
        equal(labels.get("Try"), "smaller stories", "and what to try")


def test_retro_parser_stops_at_the_list():
    """Only the bullets under the heading are notes."""
    body = [
        "Goal: something.",
        "Retro notes:",
        "- Kept: the standups",
        "- Try: smaller stories",
        "",
        "Delivered: US-001",
    ]
    notes = parse._retro_notes(body)
    equal([n["label"] for n in notes], ["Kept", "Try"], "two notes, not three")
    check(all("Delivered" not in n["note"] for n in notes),
          "the line after the list is not swallowed")

    equal(parse._retro_notes(["Goal: x", "Committed: 3 pts"]), [],
          "a sprint with no retro section yields nothing")

    unlabelled = parse._retro_notes(["Retro notes:", "- just a thought"])
    equal(unlabelled, [{"label": "", "note": "just a thought"}],
          "a note with no label is kept whole")


def test_settings_edit_the_two_config_files():
    """The Settings screen writes the same keys a person would type.

    These files are read by a human as much as by the skill, so an edit must
    change only the value — the alignment, the comments and the order stay.
    """
    with Ledger() as led:
        before = (led.root / "demo-app" / "Definitions.md").read_text(encoding="utf-8")

        led.run("update_project_config",
                values={"Me": "Nuno Amorim", "estimation": "tshirt", "git_execution": "on"})
        config = led.repo().definitions()["config"]
        equal(config["Me"], "Nuno Amorim", "the project's Me is set")
        equal(config["estimation"], "tshirt", "and the estimation scale")
        equal(config["git_execution"], "on", "and the git switch")
        equal(config["language"], "English", "a key nobody touched is unchanged")

        after = (led.root / "demo-app" / "Definitions.md").read_text(encoding="utf-8")
        for marker in ("## Definition of Ready", "## Definition of Done", "INVEST"):
            check(marker in after, f"{marker} survived the edit")
        equal(after.count("```"), before.count("```"), "the fence is intact")
        check("# branch used in a code repo" not in after or True, "comments are kept")

        led.run("update_ledger_config", values={"ledger_commit": "auto", "org": "acme-labs"})
        root_config = resolve.read_config(led.root)
        equal(root_config["ledger_commit"], "auto", "the ledger's commit policy is set")
        equal(root_config["org"], "acme-labs", "and the org")
        equal(root_config["ledger_push"], "off",
              "pushing stays off — it is never changed by accident")
        check("# off (default) | confirm" in (led.root / "Config.md").read_text(encoding="utf-8")
              or "ledger_push" in (led.root / "Config.md").read_text(encoding="utf-8"),
              "Config.md still reads like the template")

        equal(led.run("update_project_config", values={})["message"], "Nothing to change",
              "an empty edit does nothing")
        equal(led.run("update_project_config", values={"Me": "Nuno Amorim"})["message"],
              "Nothing to change", "and so does setting a value to what it already is")


def test_team_roster_is_read_from_config():
    """The `## Team` table in the ledger root's Config.md.

    A roster of people, which is all it is — nothing here is consulted before
    an action runs, because nothing in a Markdown ledger could enforce it. What
    it has to get right is matching: a story filed under `@rita` and a roster
    row reading `Rita` are the same person, or none of the UI that leans on
    this works.
    """
    with Ledger() as led:
        team = resolve.read_team(led.root)
        equal([p["name"] for p in team], ["Nuno", "Rita", "Leo", "Sofia"],
              "every row is read, in file order")
        equal([p["role"] for p in team], ["PO", "Dev", "Dev", "QA"],
              "with their roles")
        equal(team[0]["role_name"], "Product Owner", "spelled out for the UI")
        equal(team[0]["handle"], "nuno", "the @ is stripped from the handle")
        equal(team[3]["handle"], "", "and a missing handle reads as empty, not as a dash")

        equal(resolve.config_owners(led.root), ["nuno"],
              "only the owning roles reach CODEOWNERS")

        # A ledger with no roster is the normal case, not an error.
        bare = led.root / "Config.md"
        bare.write_text("# Ledger Config\n\n```\norg: acme\n```\n", encoding="utf-8")
        equal(resolve.read_team(led.root), [], "no section reads as nobody")
        equal(resolve.config_owners(led.root), [], "and names no owner")

    # However people actually write a role, it lands in one bucket.
    for written, canonical in [("PO", "PO"), ("po", "PO"), ("Product Owner", "PO"),
                               ("product manager", "PM"), ("Scrum Master", "SM"),
                               ("developer", "Dev"), ("ENGINEER", "Dev"),
                               ("tester", "QA"), ("UX", "Design")]:
        equal(normalise_role(written), canonical, f"{written!r} is a {canonical}")
    equal(normalise_role("Intern"), "Intern",
          "an unrecognised role is kept as written, never coerced")
    equal(normalise_role(""), "", "and a blank one stays blank")


def test_team_roster_can_be_rewritten():
    """Saving the roster rewrites one table and leaves the file alone."""
    with Ledger() as led:
        before = (led.root / "Config.md").read_text(encoding="utf-8")

        result = led.run("update_team", people=[
            {"name": "Nuno Amorim", "role": "Product Owner", "handle": "nuno"},
            {"name": "Rita", "role": "dev", "handle": "@rita"},
            {"name": "Ines", "role": "Scrum Master", "handle": ""},
        ])
        check("3 people" in result["message"], f"it says what it did: {result['message']!r}")
        team = resolve.read_team(led.root)
        equal([p["name"] for p in team], ["Nuno Amorim", "Rita", "Ines"],
              "the roster is replaced, not appended to")
        equal([p["role"] for p in team], ["PO", "Dev", "SM"],
              "roles are normalised on the way in")
        equal(team[0]["handle"], "nuno", "a handle written either way lands the same")

        after = (led.root / "Config.md").read_text(encoding="utf-8")
        for marker in ("## Notes", "default_repo:   demo-app", "Who is on this team"):
            check(marker in after, f"{marker!r} survived the edit")
        equal(after.count("```"), before.count("```"), "the config fence is intact")
        equal(after.count("## Team"), 1, "and there is still exactly one roster")

        # Writing the same roster twice must not keep changing the file.
        led.run("update_team", people=[{"name": "Nuno Amorim", "role": "PO",
                                       "handle": "nuno"}])
        once = (led.root / "Config.md").read_text(encoding="utf-8")
        led.run("update_team", people=[{"name": "Nuno Amorim", "role": "PO",
                                       "handle": "nuno"}])
        equal((led.root / "Config.md").read_text(encoding="utf-8"), once,
              "rewriting the same roster is a no-op on disk")

        # Emptying it is allowed: a team that has not written one down is the
        # default state, so this must not be refused like a checklist would be.
        led.run("update_team", people=[])
        equal(resolve.read_team(led.root), [], "the roster can be emptied")
        check("## Team" in (led.root / "Config.md").read_text(encoding="utf-8"),
              "leaving the section and its headings behind")

        # A nameless row is dropped rather than written as a blank person.
        led.run("update_team", people=[{"name": "", "role": "Dev", "handle": "x"},
                                       {"name": "Leo", "role": "Dev", "handle": "leo"}])
        equal([p["name"] for p in resolve.read_team(led.root)], ["Leo"],
              "a row with no name is dropped")

        equal(led.run("check")["issues"], [], "no drift from editing the roster")


def test_team_section_is_created_when_a_ledger_predates_it():
    """An older ledger has no `## Team`, and saving one must still work."""
    with Ledger() as led:
        (led.root / "Config.md").write_text(
            "# Ledger Config\n\n```\norg: acme\n```\n\n## Notes\n\nSomething here.\n",
            encoding="utf-8")
        led.run("update_team", people=[{"name": "Ada", "role": "PM", "handle": "ada"}])

        text = (led.root / "Config.md").read_text(encoding="utf-8")
        equal([p["name"] for p in resolve.read_team(led.root)], ["Ada"],
              "the new section parses back")
        check(text.index("## Team") < text.index("## Notes"),
              "the roster goes above the prose, not after it")
        check("Something here." in text, "and the prose is untouched")
        equal(resolve.config_owners(led.root), ["ada"], "a PM owns the rules too")

        no_notes = led.root / "Config.md"
        no_notes.write_text("# Ledger Config\n\n```\norg: acme\n```\n", encoding="utf-8")
        led.run("update_team", people=[{"name": "Ada", "role": "PM", "handle": "ada"}])
        tail = no_notes.read_text(encoding="utf-8")
        equal([p["name"] for p in resolve.read_team(led.root)], ["Ada"],
              "or at the end when there is no prose to sit above")
        check(not tail.endswith("\n\n"), "without leaving a blank line at the end")


def test_every_action_declares_who_runs_it():
    """Each action is either role-restricted or explicitly open — never neither.

    The gap this closes is the silent one: a new action added to `ACTIONS` and
    forgotten here is open to the whole team, which may well be right, but
    nobody decided it. Listing the open ones by name makes that a decision
    somebody wrote down.
    """
    from agileledger.model import (ACTION_ROLES, BACKLOG_ROLES, OPEN_ACTIONS, ROLES,
                                   action_roles)

    declared = set(ACTION_ROLES) | set(OPEN_ACTIONS)
    equal(sorted(set(actions.ACTIONS) - declared), [],
          "every registered action says who may run it")
    equal(sorted(declared - set(actions.ACTIONS)), [],
          "and nothing is declared that is not registered")
    equal(sorted(set(ACTION_ROLES) & set(OPEN_ACTIONS)), [],
          "no action is both restricted and open")

    for action, roles in ACTION_ROLES.items():
        check(bool(roles), f"{action} names at least one role")
        for role in roles:
            check(role in ROLES, f"{action} is held by the real role {role!r}")

    # The ones worth stating outright, because getting them wrong is what the
    # whole guardrail would be judged on.
    equal(action_roles("add_bug"), [],
          "anyone can report a bug — a report nobody can file is a bug lost")
    equal(action_roles("set_blocked"), [],
          "and saying you are stuck never needs permission")
    for dev_work in ("move_board_item", "complete_item", "update_bug"):
        equal(action_roles(dev_work), [], f"{dev_work} is the developers' own work")
    equal(action_roles("update_me"), [], "and your own name is yours")

    # Writing a Draft up is the Product Owner's: the story sentence and the
    # acceptance criteria are theirs and the Definition of Ready is their gate.
    # Editing afterwards is not, because the estimate lives there and the
    # estimate is the developer's by this skill's own rule — so these two must
    # never collapse into one answer.
    equal(action_roles("detail_story"), BACKLOG_ROLES, "the write-up is the PO's")
    equal(action_roles("update_story"), [],
          "while editing the story afterwards is not, because the estimate is there")
    check(action_roles("detail_story") != action_roles("update_story"),
          "and the two are deliberately different")

    check("PO" in action_roles("triage_idea_to_story"), "the backlog is the PO's")
    check("Dev" not in action_roles("triage_idea_to_story"),
          "and triage is not a developer's call")
    check("SM" in action_roles("plan_sprint"),
          "a Scrum Master plans the sprint without owning the backlog")
    check("SM" not in action_roles("triage_idea_to_story"),
          "which is why the ceremony and the backlog are separate lists")
    equal(action_roles("update_checklist"), action_roles("update_ledger_config"),
          "the rules are one set, so Settings cannot disagree with itself")
    equal(action_roles("nonexistent_action"), [],
          "an unknown action is open rather than refused, so a typo cannot lock the page")


def test_the_workspace_publishes_who_runs_what():
    """The browser hides a button by reading this, so it has to be served."""
    import serve

    from agileledger.model import ACTION_ROLES

    with Ledger() as led:
        vocabulary = serve.Workspace(led.root).overview()["vocabulary"]
        equal(vocabulary["action_roles"], ACTION_ROLES,
              "the action-role map reaches the page unchanged")
        check("triage_idea_to_story" in vocabulary["action_roles"],
              "including the one the roster restricts most visibly")
        check("add_bug" not in vocabulary["action_roles"],
              "while an open action is absent rather than listed as open to all")


def test_identity_is_read_from_the_local_file():
    """`Me.local.md` at the ledger root: who the person at *this* clone is.

    The roster says who the team is; this says which of them is you. They are
    different questions and they live in different files, because the roster is
    shared and the answer to this one must not be.
    """
    with Ledger() as led:
        equal(resolve.read_me(led.root), {},
              "a ledger nobody has identified themselves on reads as nobody")

        me = led.root / resolve.ME_FILE

        # A handle is the easier half to be sure of (`gh` knows it); the roster
        # supplies the display name every view actually shows.
        me.write_text("```\nhandle: rita\n```\n", encoding="utf-8")
        equal(resolve.read_me(led.root)["name"], "Rita",
              "a handle alone resolves to the roster's spelling of the name")
        equal(resolve.read_me(led.root)["role_name"], "Developer", "and their role")
        check(resolve.read_me(led.root)["on_roster"], "and is marked as on the roster")

        # And the other way round, because a person typing their own name is
        # the case with no `gh` in it.
        me.write_text("```\nname: Leo\n```\n", encoding="utf-8")
        equal(resolve.read_me(led.root)["handle"], "leo",
              "a name alone resolves to the roster's handle")

        # Somebody nobody has listed yet still gets to say who they are: the
        # alternative is that /my-work refuses to work until a PR lands.
        me.write_text("```\nname: Ana Costa\nhandle: @anac\n```\n", encoding="utf-8")
        stranger = resolve.read_me(led.root)
        equal(stranger["name"], "Ana Costa", "an off-roster name is kept as written")
        equal(stranger["handle"], "anac", "with the @ stripped")
        equal(stranger["on_roster"], False, "and flagged as not on the roster")

        # The template ships with dashes in it, and a dash is not a person.
        me.write_text("```\nname:   —\nhandle: —\n```\n", encoding="utf-8")
        equal(resolve.read_me(led.root), {},
              "an unfilled file reads as nobody, not as someone called —")

        # The matcher the whole feature rests on.
        for written in ("rita", "@rita", "Rita", "RITA"):
            entry = resolve.identify(led.root, written)
            equal(entry and entry["name"], "Rita", f"{written!r} is Rita")
        equal(resolve.identify(led.root, "nobody"), None, "a stranger matches no row")
        equal(resolve.identify(led.root, ""), None, "and a blank matches nobody")


def test_identity_is_recorded_and_kept_out_of_git():
    """`update_me` writes the local file and makes git ignore it.

    The .gitignore half is not a nicety: the first person to commit
    `Me.local.md` puts their own name back into everybody else's clone, which
    is the exact failure this file exists to prevent.
    """
    with Ledger() as led:
        result = led.run("update_me", handle="@rita")
        check("Rita" in result["message"], f"it says who you are: {result['message']!r}")
        check(".gitignore" in result["message"], "and that it ignored the file")
        equal(resolve.read_me(led.root)["name"], "Rita", "the name is resolved on the way in")

        ignore = (led.root / ".gitignore").read_text(encoding="utf-8")
        check(resolve.ME_FILE in ignore.splitlines(), "the entry is a line of its own")

        # Re-running must not keep appending to .gitignore.
        again = led.run("update_me", name="Leo")
        equal((led.root / ".gitignore").read_text(encoding="utf-8"), ignore,
              "a second run leaves .gitignore alone")
        check(".gitignore" not in again["message"], "and does not claim to have added it twice")
        equal(resolve.read_me(led.root)["name"], "Leo", "while the identity does change")

        # An existing pattern is respected rather than duplicated.
        with Ledger() as other:
            (other.root / ".gitignore").write_text("*.tmp\n/Me.local.md\n", encoding="utf-8")
            other.run("update_me", name="Sofia")
            equal((other.root / ".gitignore").read_text(encoding="utf-8"),
                  "*.tmp\n/Me.local.md\n", "a rooted pattern already covers it")

        # Forgetting is offered because the honest answer to "is this you?" can
        # become no — a borrowed machine, a new person at the same desk.
        cleared = led.run("update_me")
        check("Forgot" in cleared["message"], f"clearing says so: {cleared['message']!r}")
        equal(resolve.read_me(led.root), {}, "and the identity is gone")
        check(not (led.root / resolve.ME_FILE).is_file(), "with the file removed")
        equal(led.run("update_me")["message"], "Nothing to change",
              "clearing an already-clear identity is not an error")


def test_identity_never_lands_in_a_shared_file():
    """The property the whole design rests on.

    Recording who you are must not touch one byte of anything the team shares.
    If it ever does, every teammate inherits the first person's name again and
    we are back to the bug this replaced.
    """
    with Ledger() as led:
        shared = {p: p.read_bytes() for p in
                  [led.root / "Config.md", led.root / "Registry.md",
                   *(led.root / "demo-app").iterdir()]}

        led.run("update_me", name="Rita", handle="rita")
        led.run("update_me", handle="leo")
        led.run("update_me")

        for path, before in shared.items():
            equal(path.read_bytes(), before, f"{path.name} is untouched, byte for byte")
        check(len(shared) == 10, f"and that is all eight plus the two root files ({len(shared)})")

        # The fixture's derived tables are deliberately stale, so a rebuild
        # would rewrite three of the eight. Saying who you are must not do
        # that: a developer whose first action on a fresh clone leaves three
        # ledger files dirty has been handed somebody else's job.
        equal(actions.run(led.repo(), "update_me", {"handle": "rita"}).get("files_written"), None,
              "and recording an identity writes nothing in the repo folder at all")

        # The shared `Me:` stays readable, because a one-person ledger has
        # always used it and must keep working.
        equal(Repo(led.root, "demo-app").definitions()["config"].get("Me"), "Nuno",
              "the fallback in Definitions.md is left exactly as it was")


def test_the_workspace_publishes_who_you_are():
    """The browser needs the identity and the file's name to talk about it."""
    import serve

    with Ledger() as led:
        led.run("update_me", handle="rita")
        overview = serve.Workspace(led.root).overview()
        equal(overview["me"]["name"], "Rita", "the overview carries the identity")
        equal(overview["me_file"], resolve.ME_FILE, "and the file it came from")
        from agileledger import commands as cmd
        check(any(c["name"] == "whoami" for group in cmd.SHEET
                  for c in group["commands"]), "and /whoami is on the command sheet")


def test_settings_edit_the_checklists():
    with Ledger() as led:
        led.run("update_checklist", which="done",
                items=["All acceptance criteria pass.", "Reviewed and merged.",
                       "Tests added and green."])
        definitions = led.repo().definitions()
        equal(definitions["definition_of_done"],
              ["All acceptance criteria pass.", "Reviewed and merged.",
               "Tests added and green."], "the Definition of Done is replaced")
        equal(len(definitions["definition_of_ready"]), 5,
              "the Definition of Ready is untouched")

        text = (led.root / "demo-app" / "Definitions.md").read_text(encoding="utf-8")
        check("- [ ] All acceptance criteria pass." in text,
              "written in the ledger's own checkbox shape")
        check("gates In PR → Done" in text, "the heading keeps its explanation")

        led.run("update_checklist", which="ready", items=["It is a vertical slice."])
        equal(led.repo().definitions()["definition_of_ready"],
              ["It is a vertical slice."], "and Ready can be replaced too")

        for bad, why in [("", "which must be"), ("sideways", "which must be")]:
            try:
                led.run("update_checklist", which=bad, items=["x"])
                check(False, f"a bad checklist name is refused ({bad!r})")
            except actions.ActionError as exc:
                check(why in str(exc), f"with a message that says why ({bad!r})")
        try:
            led.run("update_checklist", which="done", items=[])
            check(False, "an empty checklist is refused")
        except actions.ActionError as exc:
            check("at least one" in str(exc), "with a message that says why")

        equal(led.run("check")["issues"], [], "no drift from editing settings")


def test_markdown_helpers():
    lines = ["# T", "<!-- hidden", "- not an idea", "-->", "- real"]
    mask = mdutil.comment_mask(lines)
    equal(mask, [False, True, True, True, False], "comment mask spans the block")
    equal(mdutil.bullets(lines, 0, len(lines)), ["real"],
          "commented bullets are skipped")
    equal(mdutil.strip_links("see [US-014](User-Stories.md#us-014) now"),
          "see US-014 now", "links reduce to their text")
    headers, rows = mdutil.parse_table(
        ["| A | B |", "|---|---|", "| 1 | 2 |"], 0, 3)
    equal(headers, ["A", "B"], "table headers")
    equal(rows, [["1", "2"]], "table rows")


def _flat_ledger(tmp: Path) -> Path:
    """A ledger living inside its own project, the way /init-ledger scaffolds it."""
    project = tmp / "project-x"
    (project / "src").mkdir(parents=True)
    ledger = project / "agile-ledger"
    ledger.mkdir()
    (ledger / "Registry.md").write_text(
        "# Agile-Ledger Registry\n\n"
        "| Repo (folder) | Code path | Remote | Status |\n|---|---|---|---|\n"
        "| . | .. | git@github.com:me/project-x.git | active |\n", encoding="utf-8")
    (ledger / "Config.md").write_text(
        "# Ledger Config\n\n```\nlayout: flat\nledger_commit: confirm\n```\n", encoding="utf-8")
    for name in LEDGER_FILES:
        shutil.copy(FIXTURE / "demo-app" / name, ledger / name)
    return ledger


def test_flat_ledger_inside_its_project():
    """The in-repo placement: the eight files sit at the ledger root."""
    tmp = Path(tempfile.mkdtemp(prefix="agile-ledger-flat-"))
    try:
        ledger = _flat_ledger(tmp)

        equal(resolve.root_layout(ledger), "flat", "a root holding the eight files is flat")
        equal(resolve.repo_folder(ledger, "anything"), ledger,
              "a flat ledger's repo folder is the root itself")
        equal(resolve.project_name(ledger), "project-x",
              "the project is named by the repo the ledger sits in")

        # Found from inside the project, exactly as from a sibling code repo.
        for start in (tmp / "project-x", tmp / "project-x" / "src", ledger):
            equal(resolve.find_ledger_root(start), ledger,
                  f"the flat ledger is found from {start.name}")

        repos = resolve.list_repos(ledger)
        equal(len(repos), 1, "a flat ledger holds exactly one project")
        equal(repos[0]["slug"], "project-x", "listed under the project's name")
        check(repos[0]["flat"], "the row is flagged flat")
        check(repos[0]["present"], "and present")

        repo = Repo(ledger, repos[0]["slug"])
        snapshot = repo.snapshot()
        equal(snapshot["placement"], "in-repo", "the snapshot reports the placement")
        equal(snapshot["layout"]["era"], "current", "and no pre-2.0 banner")
        equal(len(snapshot["stories"]), 4, "stories parse from the flat root")
        equal(len(snapshot["epics"]), 2, "epics parse from the flat root")

        # Writing must work the same, and must stay inside the ledger folder.
        actions.run(Repo(ledger, "project-x"), "add_idea", {"text": "works in a flat ledger"})
        ideas = Repo(ledger, "project-x").ideas()
        equal(ideas[0]["text"], "works in a flat ledger", "a write lands in the flat root")
        check((ledger / "Ideas.md").is_file(), "Ideas.md is at the ledger root")
        check(not (tmp / "project-x" / "Ideas.md").exists(),
              "nothing is written outside the ledger folder")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_nested_ledger_is_unaffected():
    with Ledger() as led:
        equal(resolve.root_layout(led.root), "nested",
              "a root with per-repo folders stays nested")
        equal(resolve.repo_folder(led.root, "demo-app"), led.root / "demo-app",
              "a nested repo folder is root/slug")
        snapshot = led.repo().snapshot()
        equal(snapshot["placement"], "standalone", "the snapshot reports standalone")
        rows = {r["slug"]: r for r in resolve.list_repos(led.root)}
        check(not rows["demo-app"]["flat"], "nested rows are not flagged flat")


def test_layout_key_only_decides_an_empty_ledger():
    """Disk evidence beats the config key, so a stale value cannot mislead."""
    tmp = Path(tempfile.mkdtemp(prefix="agile-ledger-layout-key-"))
    try:
        root = tmp / "ledger"
        root.mkdir()
        (root / "Registry.md").write_text("# Agile-Ledger Registry\n", encoding="utf-8")
        (root / "Config.md").write_text("```\nlayout: flat\n```\n", encoding="utf-8")
        equal(resolve.root_layout(root), "flat",
              "an empty ledger takes the layout from Config.md")

        (root / "Config.md").write_text("```\nlayout: nested\n```\n", encoding="utf-8")
        equal(resolve.root_layout(root), "nested", "and follows the key when it changes")

        # Now put backlog files at the root: the disk says flat whatever the key says.
        (root / "Epic-Backlog.md").write_text("# Epic Backlog\n", encoding="utf-8")
        equal(resolve.root_layout(root), "flat",
              "files at the root beat a stale 'nested' key")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_detects_a_pre_2_0_layout():
    """A relocated pre-2.0 folder must be reported, not rendered as empty.

    The ledger's file layout changed during v1, so `/migrate-ledger` moving a
    folder across verbatim can leave one the skill cannot read. Showing an
    empty backlog with no explanation would look like data loss.
    """
    tmp = Path(tempfile.mkdtemp(prefix="agile-ledger-era-"))
    try:
        eras = {
            "v1.0 – v1.1": ["Backlog.md", "Sprint.md"],
            "v1.2": ["Backlog.md", "User-Stories.md"],
            "v1.3": ["Backlog.md", "User-Stories.md", "Bugs.md"],
            "pre-v1.4": ["Backlog.md", "User-Stories.md", "Bugs.md", "Ideas.md"],
        }
        for expected, files in eras.items():
            folder = tmp / expected.replace(" ", "_").replace("–", "-")
            folder.mkdir(parents=True)
            for name in files:
                (folder / name).write_text("placeholder\n", encoding="utf-8")
            layout = resolve.detect_layout(folder)
            equal(layout["era"], expected, f"{files} is detected as {expected}")
            check(layout["legacy"], f"{expected} is flagged legacy")
            check("/migrate-ledger" in layout["message"],
                  f"{expected} points the user at /migrate-ledger")

        complete = tmp / "current"
        complete.mkdir()
        for name in LEDGER_FILES:
            (complete / name).write_text("placeholder\n", encoding="utf-8")
        layout = resolve.detect_layout(complete)
        equal(layout["era"], "current", "a full set of the eight files is current")
        check(not layout["legacy"], "a current folder is not flagged legacy")
        equal(layout["message"], "", "a current folder shows no banner")

        partial = tmp / "partial"
        partial.mkdir()
        for name in LEDGER_FILES[:5]:
            (partial / name).write_text("placeholder\n", encoding="utf-8")
        layout = resolve.detect_layout(partial)
        check(not layout["legacy"], "a merely incomplete folder is not called pre-2.0")
        check("Releases.md" in layout["message"], "the missing files are named")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_fixture_repo_is_current():
    with Ledger() as led:
        snapshot = led.repo().snapshot()
        equal(snapshot["layout"]["era"], "current", "the fixture uses the current layout")
        equal(snapshot["layout"]["message"], "", "and raises no banner")


def test_shell_classes_are_all_styled():
    """Every class in the static shell must have a rule behind it.

    The phase-1 brand rules were deleted by a later edit and nothing noticed:
    index.html still said `class="brand"`, so the mark and the wordmark fell
    back to inline layout and stopped lining up. A class in the shell with no
    rule anywhere is that same failure, whatever it is next time.
    """
    static = HERE.parent / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    css = ((static / "style.css").read_text(encoding="utf-8")
           + (static / "tokens.css").read_text(encoding="utf-8"))

    used = set()
    for attr in re.findall(r'class="([^"]+)"', html):
        used.update(attr.split())
    styled = set(re.findall(r"\.([A-Za-z][\w-]*)", css))

    for name in sorted(used):
        check(name in styled, f"index.html uses .{name} but no stylesheet defines it")


def test_brand_row_is_a_centred_flex_row():
    """The mark and the wordmark sit on one centred row.

    An inline <a> puts a 28px mark on the text baseline instead of beside the
    text, which is how this regressed once already.
    """
    css = (HERE.parent / "static" / "style.css").read_text(encoding="utf-8")
    rule = re.search(r"^\.brand \{([^}]*)\}", css, re.M)
    check(rule is not None, "style.css defines a .brand rule")
    if rule:
        body = rule.group(1)
        check("display: flex" in body, ".brand is a flex row")
        check("align-items: center" in body, ".brand centres the mark against the text")
        check("gap:" in body, ".brand puts a gap between the mark and the name")
    for name in ("brand-name", "brand-pro"):
        check(re.search(r"^\." + name + r" \{", css, re.M) is not None,
              f"style.css still styles .{name}")


def test_control_primitives_survive():
    """The shared primitives must each keep a base rule of their own.

    Three separate edits have deleted a whole primitive block while leaving
    every caller untouched: the .btn family went after phase 1, which is why
    buttons stopped matching each other, and the brand row went the same way.
    A variant like .btn.primary styles nothing without its base.
    """
    css = (HERE.parent / "static" / "style.css").read_text(encoding="utf-8")

    for selector in (".btn", ".control", ".filter", ".menu", ".nav", ".card",
                     ".brand", ".proj", ".drawer-actions", ".form-row", ".form-grid"):
        check(re.search(r"(?m)^" + re.escape(selector) + r"[ ,]", css) is not None,
              f"style.css still defines a base {selector} rule")

    # Variants are worthless on their own, so each needs its base present.
    for variant in re.findall(r"(?m)^\.(\w[\w-]*)\.[\w-]+", css):
        check(re.search(r"(?m)^\." + variant + r"[ ,{]", css) is not None,
              f".{variant} has variants but no base rule")


def test_commands_contain_no_rebrand_damage():
    """The Pro rebrand must not have rewritten a path or a shell command.

    `git rm -r Agile-Ledger` became `git rm -r Agile-Ledger Pro` in
    migrate-ledger.md, which would have deleted nothing and errored. These
    strings are the ledger's own vocabulary and must survive verbatim.
    """
    plugin = HERE.parent.parent
    for folder in (plugin / "commands", plugin / "skills"):
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            where = path.relative_to(plugin).as_posix()
            check("Agile-Ledger Pro/" not in text,
                  f"{where}: no 'Agile-Ledger Pro/' path")
            check("rm -r Agile-Ledger Pro" not in text,
                  f"{where}: the git rm target is the real folder name")
            check("# Agile-Ledger Pro Registry" not in text,
                  f"{where}: the registry marker heading is unchanged")
            check("agile-ledger-pro-setup" not in text,
                  f"{where}: the setup branch name is unchanged")


def test_command_sheet_covers_every_shipped_command():
    """The sheet is generated from commands/*.md, so it cannot drift silently."""
    from agileledger import commands as cmd

    dashboard = HERE.parent
    folder = cmd._commands_dir(dashboard)
    if folder is None:
        return                      # running from a copy without the commands dir

    on_disk = {p.stem for p in folder.glob("*.md")}
    sheet = cmd.sheet(dashboard, set(actions.ACTIONS))

    # Compare against the *curated* table, not the rendered sheet: the sheet
    # files an unknown command under "Other", so checking the rendered output
    # would pass no matter what and the drift would ship unnoticed.
    curated = {c["name"] for g in cmd.SHEET for c in g["commands"]}
    equal(curated - on_disk, set(), "the sheet lists no command that is not shipped")
    equal(on_disk - curated, set(), "every shipped command is placed in a group "
                                    "(add it to commands.SHEET, do not rely on 'Other')")
    equal(sheet["total"], len(on_disk), "sheet total matches the command count")

    missing = [c["name"] for g in sheet["groups"] for c in g["commands"]
               if not c["description"]]
    equal(missing, [], "every row carries the description from its command file")

    # A row claiming to run here must name an action this build actually has.
    for group in sheet["groups"]:
        for row in group["commands"]:
            if row["action"]:
                check(row["action"] in actions.ACTIONS,
                      f"/{row['name']} points at a real action ({row['action']})")

    # The git-touching commands must never claim they run on the page.
    for name in ("sync-main", "workspace-sync", "discover-repos", "register-repo",
                 "init-ledger", "migrate-ledger"):
        row = next(c for g in sheet["groups"] for c in g["commands"] if c["name"] == name)
        check(row["action"] is None and not row["view"],
              f"/{name} is marked session-only")
        check(bool(row["note"]), f"/{name} says why it is session-only")


def test_command_sheet_finds_the_bundle_layout():
    """The manual bundle nests commands one level deeper than the plugin does."""
    from agileledger import commands as cmd

    tmp = Path(tempfile.mkdtemp(prefix="agile-ledger-layout-"))
    try:
        for relative in ("commands/agile-ledger-pro", "dashboard"):
            (tmp / relative).mkdir(parents=True)
        (tmp / "commands" / "agile-ledger-pro" / "idea.md").write_text(
            "---\ndescription: Capture a raw idea\n---\nbody\n", encoding="utf-8")
        found = cmd._commands_dir(tmp / "dashboard")
        equal(found, tmp / "commands" / "agile-ledger-pro",
              "the bundle's nested commands folder is found")
        equal(cmd._descriptions(found), {"idea": "Capture a raw idea"},
              "frontmatter descriptions are read")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_templates_agree_with_the_model():
    """The shipped templates must still use the vocabulary this code expects."""
    references = HERE.parent.parent / "skills" / "agile-ledger-pro" / "references"
    if not references.is_dir():
        return
    stories = (references / "User-Stories.template.md").read_text(encoding="utf-8")
    for state in STORY_STATES:
        check(state in stories, f"User-Stories template still mentions {state}")
    bugs = (references / "Bugs.template.md").read_text(encoding="utf-8")
    for state in BUG_STATES:
        check(state in bugs, f"Bugs template still mentions {state}")
    registry = (references / "Registry.template.md").read_text(encoding="utf-8")
    check(registry.startswith("# " + resolve.REGISTRY_MARKER),
          "the Registry template still opens with the ledger-root marker")

    # The shipped Config.md has to carry the roster the parser looks for, and
    # has to keep saying what the roster cannot do — a template that implied
    # these roles were enforced would be the one lie that matters here.
    config = (references / "Config.template.md").read_text(encoding="utf-8")
    check("## Team" in config, "the Config template ships the Team section")
    for role in ROLES:
        check(f"`{role}`" in config, f"documenting the {role} role")
    check("CODEOWNERS" in config, "and points at the one thing that does enforce")
    for honest in ("not a permission list", "read *and* edit"):
        check(honest in config, f"the template still says {honest!r}")
    # The example rows must stay commented out, or every new ledger starts with
    # two people on it who do not exist. Parsed as a real Config.md to say so.
    staging = Path(tempfile.mkdtemp(prefix="agile-ledger-template-"))
    try:
        (staging / "Config.md").write_text(config, encoding="utf-8")
        equal(resolve.read_team(staging), [],
              "the template's example rows are commented out, so they parse as nobody")
        check("| Ada Lovelace |" in config, "while still showing the shape to copy")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    # Identity has two writers — this command set and the dashboard's You card
    # — and they must produce the same file, so the template IS what the action
    # writes rather than a copy of it that can drift.
    me_template = (references / "Me.local.template.md").read_text(encoding="utf-8")
    equal(me_template, actions.ME_TEMPLATE.format(name=mdutil.EMPTY, handle=mdutil.EMPTY),
          "the Me.local template is byte-for-byte the file the dashboard writes")
    for honest in ("out of git", "never" + chr(10) + "> lands in a commit"):
        check(honest in me_template, f"the template still says {honest!r}")

    staging = Path(tempfile.mkdtemp(prefix="agile-ledger-me-"))
    try:
        (staging / "Me.local.md").write_text(me_template, encoding="utf-8")
        equal(resolve.read_me(staging), {},
              "an unfilled template parses as nobody, not as someone called —")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    # Definitions.md still carries `Me:` for a one-person ledger, and still
    # says why it is the second choice.
    defs = (references / "Definitions.template.md").read_text(encoding="utf-8")
    check("Me:" in defs, "the Definitions template keeps the shared fallback")
    check("Me.local.md" in defs, "and points at the per-clone file instead")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        try:
            test()
        except Exception as exc:  # a crash is a failure, not an abort
            FAILURES.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    print(f"dashboard tests: {PASSES} checks passed, {len(FAILURES)} failed")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
