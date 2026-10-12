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

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from agileledger import actions, mdutil, parse, render, resolve  # noqa: E402
from agileledger.model import BUG_STATES, STORY_STATES  # noqa: E402
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
