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
from agileledger.model import (BUG_STATES, EPIC_STATES, LEDGER_FILES,  # noqa: E402
                               STORY_STATES)
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
                    "labels"):
            check(key in vocabulary, f"vocabulary exposes {key}")

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
