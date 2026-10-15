---
name: agile-ledger-pro
description: >-
  Plain-Markdown Scrum / Agile product-management system for Claude Code. Manage a product backlog of
  Epics and User Stories, plan and run sprints, drive a board, track velocity, cut Major.Minor releases,
  and keep GitHub branches/commits/PRs traceable to stories — all from slash commands, with no Jira and
  no database. Use this skill whenever the user mentions a backlog, epic, user story, sprint, sprint
  planning, standup, board, story points, velocity, acceptance criteria, definition of done/ready,
  release, changelog, roadmap, or wants to capture / triage / detail / ship a product idea, plan a
  sprint, open a PR for a story, or check what merged to main — even if they don't say "Agile-Ledger Pro"
  or "Agile-Ledger" explicitly. The ledger lives in its own **ledger repository**, one folder per code
  repo, so code repos stay clean: `<ledger-repo>/<repo-slug>/*.md` is the single source of truth; keep
  it true.
---

# Agile-Ledger Pro

A product-management system made of plain-Markdown files, applying the Scrum framework so a Product
Manager runs the whole lifecycle — backlog → sprint → increment → release — from the command line, and
shares the result with developers who don't need to learn a new tool.

**Two-layer model.** The team uses **GitHub for code** (branches, commits, PRs, merges) and
**Agile-Ledger Pro for the PM layer** (backlog, stories, sprints, board, releases). The two are stitched
together by one join key — the **User Story ID** — which travels through every branch, commit, and PR.

**Two repositories, one join key.** The PM layer lives in a **separate ledger repository** that holds
one folder per code repo. A code repo contains **no ledger files at all**: PM bookkeeping never lands
in the branch a developer is building on, so nobody rebases or pulls to receive a backlog edit, and
everyone reads the whole portfolio in one place. See **Where the ledger lives** below — resolve it
before any read or write.

**Priority of duties, always in this order:**
1. **Bookkeeping is the job** — keep the backlog, sprint, board, and release record true.
2. **Execution is optional** — git automation is opt-in; the developer may build however they like and
   the ledger still stays accurate.

This skill is the brain. The slash commands are thin entry points that delegate here. When natural
language matches ("new story", "let's plan the sprint", "what merged to main"), act through these rules.

---

## Golden invariants (never violate)

- **Plain Markdown only.** No database, no dependencies. This is why a no-Jira team can adopt it.
- **Never write ledger files into a code repo.** Every ledger file belongs to `<ledger-root>/<repo-slug>/`.
  If a command would create or edit Markdown inside the code repo you are standing in, you resolved the
  ledger wrong — stop and resolve again.
- **Resolve the ledger before the first read or write** of a session (see **Where the ledger lives**),
  and state the resolution in one line (`Ledger: ~/Projetos/agile-ledger → repo-a`). Never guess a path.
- **Never delete.** Nothing is removed — delivered, paused, and discarded items are kept forever;
  discarded items keep *why* they were rejected.
- **State = physical position, moved only by a command.** A status change is a move between sections
  or board columns, never a silent emoji swap.
- **Recompute IDs; never reuse.** On every registration, scan all files for the highest existing ID
  *of that type* and use max + 1. A `Next free ID` hint may exist but is reconciled, never trusted blindly.
- **Absolute dates only.** Resolve "today"/"yesterday" to a real `YYYY-MM-DD` before writing.
- **The human's voice, English ledger** (configurable in `Definitions.md`). Raw captures may be any
  language; translate at triage.
- **Re-read immediately before writing.** Makes multi-session capture safe.
- **Write entries for readable previews.** Put each metadata field on its own bulleted line and separate
  logical sections (story, acceptance criteria, dependencies, delivery, notes) with a blank line, so the
  rendered Markdown preview stacks them instead of collapsing into one paragraph. Follow
  `references/entry-templates.md` exactly; never collapse an entry into a single inline paragraph, and
  never rely on trailing-space line breaks — they are invisible and get lost when an entry is rewritten.
- **Case-insensitive ID matching** across the git boundary: ledger stores canonical `US-014`; git uses
  lowercase `us-014`; matching ignores case.
- **Epic status and rollups are derived from children**, never hand-set.
- **Confirm before any merge or push.** Git execution is opt-in (see Git conventions). Never auto-merge.
  This covers the ledger repo too: `ledger_commit` may commit, but pushing is always confirmed.
- **Session start:** resolve the ledger, read all `<ledger-root>/<repo-slug>/*.md` files first, load
  state silently, give at most a one-line orientation (including which ledger and repo you resolved).
- **Identity is per-clone, never committed.** Who the person is comes from `Me.local.md` at the ledger
  root, which git ignores; the shared `Me:` in `Definitions.md` is a fallback only. Never write a
  person's own name into `Definitions.md`, and never commit `Me.local.md`. When a command needs to
  know who is asking and nothing says, ask — and offer `/whoami`, which answers it once.

---

## Where the ledger lives (resolve this first)

A ledger sits in one of **two placements**, chosen once at `/init-ledger` and recorded as `layout` in
the ledger root's `Config.md`. Both are first-class; read which one you are in before writing anything.

**`nested` — the ledger has its own repository** (an org, or more than one project):

```
<workspace-root>/                 e.g. ~/Projetos/
├── agile-ledger/                 ← THE LEDGER REPO — its own git repo, pushed like any other
│   ├── Registry.md               # the marker + the map: repo slug ↔ code path ↔ remote ↔ sync state
│   ├── Config.md                 # ledger-wide config (org, commit/push policy, default repo)
│   ├── Me.local.md               # who *you* are — git-ignored, one per clone
│   ├── repo-a/                   # one folder per code repo — the eight ledger files
│   │   ├── Ideas.md … Definitions.md
│   └── repo-b/
└── repo-a/ · repo-b/             ← the code repos, with NO ledger files in them
```

**`flat` — the ledger lives inside the one project it belongs to** (one person, one repo):

```
project-x/                        ← the code repo
├── src/ · README.md              # the project
└── agile-ledger/                 ← the ledger, committed with the project
    ├── Registry.md               # the marker; one row, folder `.`
    ├── Config.md                 # layout: flat
    ├── Me.local.md               # who *you* are — git-ignored, one per clone
    └── Ideas.md … Definitions.md # the eight files, at the root — no per-repo folder
```

A **ledger root** is a directory containing a `Registry.md` whose first heading is
`# Agile-Ledger Registry`. That heading is the marker — never identify the ledger by folder name, and
never by placement.

**Which placement am I in?** The files on disk answer it: a ledger root holding `Epic-Backlog.md`
(or `Ideas.md`, or a pre-2.0 `Backlog.md`) is **flat**, and every path below reads
`<ledger-root>/<file>.md` with no repo folder. Otherwise it is **nested** and paths read
`<ledger-root>/<repo-slug>/<file>.md`. The `layout` key settles only the case where a freshly
scaffolded ledger has no backlog files yet.

**Resolution order** (run once per session, then cache it):

1. An explicit **`--repo <slug>`** argument on the command wins, as does an explicit path the user gives.
2. If the cwd is **inside a ledger root**, the active repo is the folder you are in; at the root itself
   use `default_repo` from `Config.md`, and if that is unset, ask. In a **flat** ledger the root *is*
   the project — there is one, so there is nothing to choose and `default_repo` is unnecessary.
3. Otherwise **walk up** from the cwd (the cwd, then each ancestor, stopping at the home directory):
   at each level check that directory *and its immediate children* for a ledger root. First hit wins.
   **Never write a ledger file anywhere but the resolved ledger root.** In a nested ledger that means
   nothing is ever written into a code repo; in a flat one the ledger root is deliberately inside the
   project, and anything outside it is still off-limits. If a write is about to land somewhere else,
   the resolution was wrong — stop and resolve again.
4. **Identify the code repo** against `Registry.md`: match `git remote get-url origin` normalized
   (drop scheme, credentials, trailing `.git`; compare host + path case-insensitively), else the
   absolute code path, else the folder name. The remote is the strongest key — a folder rename does
   not break it, so prefer it and refresh the stale path column when they disagree.
   **Without a shell**: the read-only commands (`/board`, `/status`, `/roadmap`, `/my-work`, `/guide`,
   `/changelog`) declare `allowed-tools` that exclude Bash, so they cannot read the git remote. They
   match the **cwd path, then the folder name** against `Registry.md` instead, and ask when that is
   ambiguous — never guess a repo for a command that is about to print someone's sprint.
5. **No ledger root found** → say so and offer `/init-ledger`. **Found but this repo is unregistered**
   → offer `/register-repo .`. Never silently scaffold a ledger root somewhere you guessed.
6. **A legacy `Agile-Ledger/` folder inside the code repo** (the pre-2.0 layout) → report it once and
   offer `/migrate-ledger`. If a central folder for the repo *also* exists, treat the **central one as
   the source of truth**, do not merge silently, and tell the user the in-repo copy is now stale.

State the resolution in one line before working, e.g. `Ledger: ~/Projetos/agile-ledger → repo-a`, or
`Ledger: project-x/agile-ledger (in-repo)` when it is flat. Every file path below is relative to the
resolved repo folder — `<ledger-root>/<repo-slug>/` when nested, `<ledger-root>/` when flat — so the
in-folder links between the eight files are identical in both placements. Cross-repo references are possible and written as `../repo-b/User-Stories.md#us-021`.

---

## Committing to the ledger repo

The ledger repo is a git repo; keeping its history clean is part of the bookkeeping. `Config.md` sets
the policy — `ledger_commit: confirm` (default) · `auto` · `off`, and `ledger_push: off` (default) ·
`confirm`.

- After a command finishes writing, **offer one commit** covering that command's writes, scoped to the
  repo folder: `ledger(repo-a): US-014 → Done (sprint 7)`. Under `auto`, commit without asking; under
  `off`, leave the files dirty and say so.
- **Push only** when `ledger_push: confirm` *and* the user confirms this push. Never force-push, never
  rewrite ledger history, never open a PR against the ledger repo on your own.
- Commit the **ledger repo only**. A command that also touches the code repo (a branch for a story, the
  legacy-folder removal in `/migrate-ledger`) keeps those changes in a separate commit there, under the
  existing `git_execution` rule.
- One command, one commit. Do not bundle unrelated repos' folders into a single ledger commit.

---

## Files & where things live

Inside `<ledger-root>/<repo-slug>/`:

```
<repo-slug>/
├── Ideas.md             # 💡 idea inbox — raw captures from /idea. Triage promotes them out of here.
├── Epic-Backlog.md      # Epics, each with a lightweight STORY INDEX. Epic dashboard table on top.
├── User-Stories.md      # full detail for Ready+ stories, grouped by state. State-summary table on top.
├── Bugs.md              # bug reports, grouped by state. Bug dashboard table on top.
├── Sprint.md            # current sprint: goal, board (To Do→In PR→Done), assignees, blocked flags, sync cursor
├── Sprints-History.md   # closed sprints + velocity (never-delete)
├── Releases.md          # 🚧 Increment (Done, unreleased) at top, then Major.Minor history (newest first)
└── Definitions.md       # DoD, DoR, INVEST, branch/commit/PR conventions, config (git opt-in, language)
```

**One command, one place — the file each phase writes to:**

| Phase | Command(s) | Writes to |
|---|---|---|
| Capture an idea | `/idea` | `Ideas.md` (💡 inbox) |
| Triage → register | `/triage` | reads `Ideas.md` → writes Epic + suggested story-index in `Epic-Backlog.md` |
| Detail a story | `/detail-us` `/detail-epic` | `User-Stories.md` (detail) + `Epic-Backlog.md` (index mirror) |
| Report / fix a bug | `/bug` `/triage-bug` `/find-bug` `/done-bug` | `Bugs.md` |
| Plan / run a sprint | `/plan-sprint` `/start-*` `/review` `/pr` `/done-*` `/close-sprint` | `Sprint.md` (board) + the item's home file |
| Release / report | `/release` `/changelog` `/status` `/roadmap` | `Releases.md` (read across all) |

**Two-file story model (for scale).** `Epic-Backlog.md` is the **epic file** — epics plus a one-line
**index** of each of their stories (`US-id · title · state · priority · pts · assignee`), so you follow
what's done or not without scrolling through Gherkin. `User-Stories.md` holds the **full story detail**
(As-a/I-want/So-that, acceptance criteria, dependencies, notes), grouped by state. Raw ideas live
separately in `Ideas.md` until `/triage` promotes them, so the epic backlog stays clean.

- A **📝 Draft** story (triaged, not yet detailed) exists **only** as an index line under its epic in
  `Epic-Backlog.md`. There is nothing to detail yet.
- `/detail-us` writes the story's full entry into `User-Stories.md` (under `## ✅ Ready`) and flips its
  epic index line to **Ready**. From then on the detail lives in `User-Stories.md`.
- **Source of truth:** for Ready-and-beyond, the story **detail and its lifecycle grouping live in
  `User-Stories.md`**; the epic index line in `Epic-Backlog.md` is a derived **mirror**. While a story is
  in a sprint, `Sprint.md` tracks its **fine board column** (To Do→In PR) by ID; the epic index keeps the
  **coarse** state (`In Sprint`). `/ledger-check` reconciles index ↔ detail ↔ board.
- **Epic index coarse states:** `Draft · Ready · In Sprint · Delivered · Paused · Discarded`. The live
  board columns are shown by `/board`.
- **Overview tables (top of each file):** every backlog file opens with a one-line **roll-up** of the
  state counts followed by a **per-item index table whose ID cell links to that item's entry**, so the
  top of the file works as a jump list. `Epic-Backlog.md` — epic dashboard
  (`Epic · Title · Status · Stories done/total · Points done/total · Target`); `User-Stories.md` —
  (`ID · Title · State · Pri · Pts · Epic · Assignee`); `Bugs.md` —
  (`ID · Title · State · Sev · Pri · Relates to · Assignee`) plus `Open by priority`.
  Rows follow the file's own section order (active work first, done last), highest priority first within
  a group, and are **kept forever** so every anchor stays reachable. Tables are **derived, never
  hand-typed**: any command that changes an item's state, priority, estimate, assignee, or title rebuilds
  the affected table(s). Exact shapes in `references/entry-templates.md`.

If the resolved repo folder does not exist yet inside the ledger root, scaffold all eight files from the
`references/*.template.md` files and add the repo's Registry row before doing anything else. If there is
no ledger root at all, scaffold that first (`Registry.md` + `Config.md` from their templates) — that is
`/init-ledger`, and it is the one thing to do before any capture.

---

## The ID system (typed hierarchy)

| Type | Shape | Parent field |
|---|---|---|
| Epic | `EPIC-001` | — (top level) |
| User Story | `US-014` | `Parent: EPIC-001` |
| Task *(optional)* | `TASK-031` | `Parent: US-014` |
| Bug | `BUG-014` | `relates to US-xxx / EPIC-xxx` (optional) |

- Each type is sequential **within its own type**, never reused.
- Use **parent pointers**, never nested numbers (`US-014.3` is forbidden — it renumbers on reorder).
- **Default hierarchy is Epic → User Story.** Tasks are off by default — create one only for an
  explicit sub-unit (unplanned/harder work, or a genuine FE/BE two-developer split).
- **Bugs are a separate track** (their own file and capture/triage/assess flow, see Bug tracking) but
  they share the sprint board with stories. A bug *relates to* a story/epic; it is not a child of one.
- The **Inbox is type-agnostic**: a raw `/idea` has no type; `/triage` decides epic vs story.

### Anchors & links (stable, rename-proof navigation)

Every registered entry's **heading is its bare ID** — `### EPIC-005`, `#### US-014`, `### BUG-014` — and
the human-readable **title goes on the line just below**. This gives each entry a stable lowercase anchor
(`#epic-005`, `#us-014`, `#bug-014`) that the Markdown preview generates automatically and that **does not
change when the title changes**. Reference any item as a relative file+anchor link (same repo folder
in the ledger):

- `[US-014](User-Stories.md#us-014)` · `[EPIC-005](Epic-Backlog.md#epic-005)` · `[BUG-014](Bugs.md#bug-014)`
- Anchor = the **ID lowercased** (hyphen kept). Within the same file you may shorten to `[EPIC-005](#epic-005)`.

Always write these as **live links**, not bare text, in: epic story-index lines, a story's `Parent`,
**`Dependencies`**, a bug's `relates to`, and sprint-board entries — so the reader clicks straight from
the backlog to the detail. This works in GitHub and VS Code preview; custom `<a id>` anchors are avoided
because they behave inconsistently across viewers. `/ledger-check` verifies every link resolves.

---

## The two state machines

**Shaping states** (a story's life *before* a sprint):

```
📥 Inbox  →  📝 Draft  →  ✅ Ready        (+ ❄️ Paused, 🗑️ Discarded — kept with reason)
```
- 📥 Inbox: raw capture, no ID, in `Ideas.md`. · 📝 Draft: triaged — has ID, parent, priority, **index
  line under its epic in `Epic-Backlog.md` only** (not yet detailed).
- ✅ Ready: detailed — story sentence + Gherkin AC + estimate, Definition of Ready met (pullable). **Full
  entry written to `User-Stories.md`**; epic index line flips to Ready.

For Ready-and-beyond, **physical position = state** plays out in `User-Stories.md`: stories are grouped
under `## ✅ Ready`, `## 🏃 In Sprint`, `## ✅ Delivered`, `## ❄️ Paused`, `## 🗑️ Discarded`, and a state
change is a move between those groups (with the epic index line updated to match).

**`Sprint.md` — board / execution states** (only once pulled into a sprint):

```
To Do  →  In Progress  →  In Review  →  In PR  →  Done
```
plus a **🚧 Blocked flag** that can sit on a story in *any* column (a flag, not a column — so a blocked
story never loses its real column; this is also where the dependency gate surfaces). The board tracks the
fine column by ID; the story's detail stays in `User-Stories.md` (grouped under In Sprint).

**The handoffs (all command-gated):** `/plan-sprint` references a Ready story into To Do · `/start-us`
→ In Progress · `/review` → In Review · `/pr` → In PR · `/done-us` → Done · `/close-sprint` sends Done
onward to the Increment and unfinished stories back to Ready.

**Epics never go on the board** (they span many sprints). Follow them via `/roadmap`.

**Bug states** (in `Bugs.md`, a separate track that shares the board):

```
🐛 Inbox  →  🔍 Triaged  →  🔬 Confirmed  →  🛠️ In Sprint  →  ✅ Fixed
                                              (+ ❄️ Deferred, 🚫 Won't fix / Can't reproduce — kept with reason)
```
- 🐛 Inbox: raw report (`/bug`). · 🔍 Triaged: `/triage-bug` set BUG-id, severity, priority. · 🔬 Confirmed:
  `/find-bug` reproduced + assessed it from the code. · 🛠️ In Sprint: pulled onto the board. · ✅ Fixed: done.
- A bug becomes **pullable** once Triaged with a priority (Confirmed preferred). On the board it moves
  through the **same columns** as stories (To Do → In PR → Done), with its own `bug-xxx` branch.

---

## Lifecycle at a glance

```
Inbox → /triage → Draft → /detail-us → Ready
   → /plan-sprint → To Do
       → /start-us  → In Progress   (branch us-014-slug offered)
       → /review    → In Review     (code-complete on branch; verify AC + DoD — "is it really done?")
       → /pr        → In PR         (verified work only; PR opened, AC checklist pre-ticked)
       →  …PR approved + merged on GitHub…
       → /done-us   → Done          (DoD met; recorded into the Increment)
   → /close-sprint  (Done → Increment + velocity; unfinished → Ready)
   → /release       (Major.Minor cut from the Increment) → /changelog
```

---

## Commands

Thin entry points; the rules below are authoritative. Always re-read the target file before writing.

**Every command accepts `--repo <slug>`** to target a repo other than the resolved one — the way to work
on `repo-b`'s backlog while standing in `repo-a` or in the ledger repo itself. Without it, the resolution
order above decides.

### Set up the ledger

The ledger repo and its registry belong to the **Agile-Ledger Pro Workspace** skill; these four commands are
listed here because they gate everything else.

- **`/init-ledger [path]`** — Create the ledger repo: `Registry.md` + `Config.md` from the templates,
  `git init` offered, nothing else. Run once per workspace.
- **`/register-repo <path|remote> [--from-git]`** — Add a code repo: create `<ledger-root>/<slug>/` with
  the eight files and a Registry row. Writes nothing into the code repo.
- **`/migrate-ledger [path]`** — Move a pre-2.0 in-repo `Agile-Ledger/` folder into the ledger repo
  verbatim, then offer to remove it from the code repo on a branch (confirmed; never pushed).
- **`/ledger-commit`** — Review the ledger repo's diff and commit it (push only on confirmation).

### Capture & shape the backlog

- **`/idea <text>`** — Append `<text>` verbatim (any language) + today's absolute date to the 💡 inbox
  in `Ideas.md`. No ID, no dedup, no rewrite, no questions. Instant and safe mid-work.
- **`/triage`** — Process each idea in `Ideas.md`: run **duplicate detection** (four outcomes below);
  decide **epic or story**; assign the next typed ID; set `Parent`, priority, area; rewrite **in the
  user's voice, in English**; write it into `Epic-Backlog.md` and **move the line to `## ✅ Triaged`
  in `Ideas.md`** as `→ US-xxx (date)` — or `→ discarded (date): why` — never delete it: the funnel
  from idea to story is only answerable later if the ideas are still there. A new epic gets
  `**Created:** <date>`.
  When an idea becomes a **new epic**, also propose a few **suggested 📝 Draft stories** (index lines)
  under it, derived from the epic goal — present them for confirmation, never as truth. When an idea maps
  to an **existing epic**, add it as a single 📝 Draft story-index line under it. No AC or estimate yet
  (that's `/detail-us`). Reconcile each `Next free ID`.
- **`/detail-us <US-ID>`** — Fill one story to Ready: `As a <role>, I want <goal>, so that <benefit>`,
  Gherkin acceptance criteria, Fibonacci `Estimate`, `Layer`, `Dependencies`, and `**Ready:** <today>`
  (the start of lead time). Apply **INVEST**; flag
  horizontal slicing (see Vertical slicing). **Write the full entry into `User-Stories.md` under
  `## ✅ Ready`, flip the epic index line in `Epic-Backlog.md` to Ready, and refresh both top tables.** Move
  to Ready only once the **Definition of Ready** holds. (Stories are born as Draft index lines at
  `/triage`; this is the step that gives them detail — there is no separate create step.)
- **`/detail-epic <EPIC-ID>`** — Run `/detail-us` across **all** of the epic's stories.
- **`/create-task <US-ID>`** *(optional)* — Add a `TASK-xxx` under a story (in `User-Stories.md`, with
  the story) carrying `Parent`, `Layer`, `Assignee`. Tasks are work splits, not units of value.
- **`/refine`** — Refinement pass over `Epic-Backlog.md` (Draft index) + `User-Stories.md` (Ready detail):
  surface under-detailed items, oversized or **horizontally-sliced** stories, dangling dependencies,
  stories failing INVEST or the DoR. Report; fix only on request.

### Report & fix bugs

- **`/bug <text>`** — Instant bug capture: append the reporter's symptom verbatim (any language) + today's
  date to the 🐛 Inbox in `Bugs.md`. No ID, no questions. The symptom stays in the reporter's voice.
- **`/triage-bug`** — Process the bug Inbox: duplicate check; assign the next `BUG-xxx`; set **severity**
  (`critical / major / minor / trivial`) and **priority** (🔴🟡🟢); link `relates to [US-xxx](User-Stories.md#us-xxx)`/area;
  move to 🔍 Triaged with `**Triaged:** <today>`; refresh the bug dashboard. Flag a `critical` bug as
  **pull-now** (it may warrant
  interrupting the current sprint rather than waiting for planning). Separate from `/triage` so an empty
  bug Inbox costs nothing.
- **`/find-bug <BUG-ID>`** — **Read-only** code investigation. Try to reproduce and locate the cause, then
  fill **steps to reproduce, expected vs. actual outcome, and the assessment (suspected root cause /
  files)**. *Honesty guardrail:* write a field only if you **confirm it from the code** (`confirmed`) or
  the **reporter supplied it** (`reported`); otherwise mark it `unconfirmed — needs input` and ask. Never
  invent a repro or a root cause. Never edit code. On success the bug moves 🔍 Triaged → 🔬 Confirmed.
- **`/start-bug <BUG-ID>`** — Move To Do → In Progress on the board and write `**Started:** <today>`
  on the bug's entry the first time (a bounce back to To Do keeps the original); offer the branch
  `bug-<id>-<slug>` (lowercase). Git only if opted in.
- **`/done-bug <BUG-ID>`** — Move In PR → ✅ Fixed (gated by the fix verified against the repro). Move the
  entry to `## ✅ Fixed` in `Bugs.md`, remove it from the board, and record a line in the 🚧 Increment of
  `Releases.md` tagged **Fixed**. Refresh the bug dashboard.

### Run the sprint

- **`/plan-sprint`** — Propose a **Sprint Goal**; pull top-ordered ✅ Ready stories **and** triaged/confirmed
  **bugs** (highest priority first — a 🔴 critical bug sits above stories) whose points fit recent
  **velocity** (from `Sprints-History.md`); optionally set `Assignee`; write the new sprint header + board.
  Work pulled in **after** planning ends its board line `· pulled <date>`, and a 🚧 Blocked line ends
  `· since <date>` — the date the flag first went up, never moved when the reason is edited
  into `Sprint.md` with each item in **To Do** (by ID reference). **Move each pulled story to `## 🏃 In
  Sprint` in `User-Stories.md` (mirror its epic index line) and each pulled bug to `🛠️ In Sprint` in
  `Bugs.md`; refresh all top tables.** Honour the dependency gate. Bug points are optional (count toward
  velocity if set).
- **`/board`** *(alias `/standup`)* — Print the current sprint snapshot: the five columns with their
  items (stories **and** bugs — ID, title, assignee, points), plus 🚧 blocked items and their reasons.
  Read-only. This is the async-team daily view.
- **`/insights`** — The report a PM steers by, read-only, from the eight files: per-sprint velocity,
  **reliability** (completed ÷ committed) and carry-over; **forecast** (Ready points ÷ velocity = runway;
  per-epic ETA); bugs reported vs fixed per month, open age, time to fix and the **escape rate**; the
  epic portfolio and release cadence; **workload distribution** (alphabetical, never a ranking — flag
  when one person carries half); backlog smells (8+ point stories, Ready stories failing DoR, draft
  and idea age, unplanned share); **flow** (lead and cycle time from `Ready:`/`Started:`/`Delivered:`,
  blocked days, scope pulled in mid-sprint) and the **ideas funnel** from `## ✅ Triaged`. A Kanban
  project leads with throughput and cycle time instead of velocity. A number the ledger cannot
  support is printed as its reason, never estimated. The dashboard's Insights tab is the same report.
- **`/my-work <name>`** — One developer's slice of the current sprint: their stories, board column,
  acceptance criteria (from `User-Stories.md`), branch, and any blockers. Read-only. Framed as
  **workload + blockers**, never a ranking. If `<name>` is omitted, resolve who is asking —
  `Me.local.md` at the ledger root first, then the shared `Me:` in `Definitions.md` — and say which
  one you used; with neither, ask rather than guess, and point at `/whoami`. Match the name against
  the ledger root's `## Team` roster when it has one, so `@ada` and `Ada Lovelace` find the same
  person's work.
- **`/start-us <US-ID>`** — Run the **dependency gate**: if any linked dependency is not Done,
  stop and warn, naming it. Otherwise move To Do → In Progress in `Sprint.md`, write
  `**Started:** <today>` on the story's entry in `User-Stories.md` **the first time only** (the epic
  index stays coarse `In Sprint`) and **offer** the branch
  `us-014-slug` (lowercase). Only run git if execution is opted in; otherwise just hand over the name.
- **`/review <US-ID|BUG-ID>`** — Move In Progress → In Review. Work is code-complete **on the branch, no
  PR yet**. Generate a verification checklist: for a story, the acceptance criteria as Given/When/Then +
  the Definition of Done; for a bug, the **steps to reproduce now passing** + expected outcome restored.
  This is the "is it really done?" gate.
- **`/pr <US-ID|BUG-ID>`** — Move In Review → In PR (verified work only). Generate the PR body from the
  ledger and the title `<title> [US-014]` (story) or `<title> [BUG-014]` (bug, `Fixes BUG-014`). Hand it
  over to paste, or run `gh pr create` only if execution is opted in.
- **`/done-us <US-ID>`** — Move In PR → Done, **gated by the DoD + all acceptance criteria checked**.
  **Move the story's entry in `User-Stories.md` from `## 🏃 In Sprint` to `## ✅ Delivered`** (append the
  delivery line), set its epic index line to `Delivered`, remove it from the `Sprint.md` board, and
  refresh both top tables. Record a line in the 🚧 Increment of `Releases.md`. If the parent epic was
  previously Done, this re-opens it (derived status); on the epic's return to Done, close a new epic
  version (see below).
- **`/close-sprint`** — Summarize Done vs. carried-over; ensure Done stories **and Fixed bugs** are
  recorded in the Increment; **move unfinished stories back to `## ✅ Ready` in `User-Stories.md` (reset
  epic index) and unfinished bugs back to 🔬 Confirmed in `Bugs.md`**, clearing both from `Sprint.md`;
  append the closed sprint + its **velocity** to `Sprints-History.md`; refresh the tables; offer retro notes.
- **`/sync-main`** — Read-only reconcile of git `main` vs. the ledger. **Reads git in the code repo,
  writes only in the ledger folder** — so it needs the code path from `Registry.md` (or the cwd) and the
  resolved ledger folder at the same time. Fetch main, list merges since
  the `Last main sync` cursor in `Sprint.md`, map each commit to its **US or BUG** id via the
  bracketed/parenthesized id (case-insensitive), and flag: (1) **merged but ledger not Done/Fixed** →
  propose marking it + filling the Increment; (2) **merged with no id** → the off-plan surprise; surface
  it so the user back-fills a story/bug or asks. Update the sync cursor + sync log only after review.

### Release & communicate

- **`/release [version]`** — Cut a `Major.Minor` version from the 🚧 Increment in `Releases.md`. No arg
  → sweep everything currently in the Increment; `[version]` overrides the computed number. Move the
  released lines into a new dated version-history entry (newest at top); leave the Increment clean.
  Increment to existing functionality ⇒ **Minor**; brand-new capability/epic ⇒ **Major**.
- **`/changelog`** — Derive user-facing release notes / `CHANGELOG.md` from the version history, grouped
  into **Added / Changed** (from stories & epics) and **Fixed** (from bugs). Derived only — never edits
  the ledger.
- **`/dashboard [--port N] [--ledger PATH] [--no-browser]`** — Serve the whole ledger as a local web
  page: the board, the backlog, each epic's progress, velocity over time, open bugs, releases,
  grouped by project. It also applies the ledger-only commands from a form (capture, triage, detail,
  plan, the board moves, done, release, `/ledger-commit`), under the same rules written here —
  nothing deleted, no ID reused, derived tables rebuilt from the entries, and only the lines an edit
  owns rewritten. It never runs git in a code repo, so `/sync-main`, `/workspace-sync`,
  `/discover-repos` and the setup commands stay in this session. Python 3.8+, standard library only,
  bound to `127.0.0.1`. The server lives in the plugin at `dashboard/serve.py`.
- **`/status`** — The whole picture: counts by shaping state and board column, current sprint progress,
  velocity trend, blocked items, **open bugs by severity/priority**, Increment (unreleased) contents,
  latest version.
- **`/roadmap`** — Epics grouped by **target version**, each with its derived rollup
  (`stories done/total · points done/total`) and status. The strategic follow-up; also where epics map
  to versions.
- **`/ledger-check`** — Audit all files for drift: duplicate or mis-sequenced typed IDs (incl. `BUG`),
  dangling `Parent`/dependency links, childless epics, board column not matching the recorded state, orphan
  Increment lines, stale `Next free ID`, and — for the split files — **an epic index line whose state
  disagrees with the story's group in `User-Stories.md`; a Ready+ story with no index line (or vice
  versa); a detailed story missing from `User-Stories.md`; a Draft story that wrongly has a detail entry;
  a bug on the board whose `Bugs.md` state isn't In Sprint; stale overview tables.** Also audit
  **navigation**: every entry heading is a **bare ID** (so its anchor is stable), and every ID link
  (`[US-xxx](User-Stories.md#us-xxx)`, parent, dependency, relates-to, board) **resolves** to an existing
  anchor in the named file. Report; fix on request.

---

## Duplicate detection (four outcomes)

Before registering anything, scan **every** section across all files — including Paused/Discarded
(re-raising a discarded item is valuable because its reason is right there). Resolve to one and say which:

1. **Exact match** → surface the existing entry; don't duplicate.
2. **Same thing, improved** → a new story under the relevant epic (increments the epic version on ship).
3. **Related but distinct** → register new, cross-linked with a relative ID link.
4. **Genuinely new** → register fresh.

---

## Epic version control & the triage decision

An epic is the **permanent home** for its stories and carries a `History` of `vN` lines — the
"how many times did we increment this capability?" metric (the signature mechanic, lifted from idea to
epic level).

**Version-close trigger:** the **first** time an epic reaches Done = **v1**. Each time it **returns to
Done after previously being Done** = the next version. A round bundles whatever stories shipped before
it went green again. An epic increment typically lands as a **Minor** release; a new epic as a **Major**.

**Increment vs. new epic — decide at triage:** does the idea serve the **same user goal** as an
existing epic, or a **new goal**?
- **Same goal** → new **User Story under that epic** (bumps its version on ship). The common
  "improve something already built" case. Adding a story to a Done epic re-opens it automatically
  (derived status: ✅ → 🔨), and it returns to ✅ on ship, closing a new version.
- **New goal** → new **`EPIC-xxx`**, cross-linked `[EPIC-xxx](Epic-Backlog.md#epic-xxx)`.

Never edit an epic's value directly — an epic improves only *by delivering a story*.

**Versioning lives at the epic level only.** Delivered stories are one-and-done (kept, not
re-versioned); to change what a story did, write a new story under the epic.

---

## Estimation, priority & velocity (two distinct axes)

- **Priority** (value, PM-owned): 🔴 high · 🟡 medium · 🟢 low, plus backlog **order**. Descriptive,
  not a strict queue; capture the rationale.
- **Estimate** (size, developer-owned): **story points on the Fibonacci series** (1, 2, 3, 5, 8, 13…).
- **Velocity**: sum of completed points per sprint, in `Sprints-History.md`, used to size `/plan-sprint`.
  A **team** metric.
- **Assignee** (optional): surfaces **workload and blockers**, never a productivity leaderboard.
  Written `@name`. The ledger root's `Config.md` may carry a `## Team` roster of names, roles and
  GitHub handles — offer those names rather than asking for one to be retyped, and resolve a handle
  to its person. Which of them is *you* is a different question, answered per clone in
  `Me.local.md`, never in the shared `Definitions.md`. A role in the roster is a **label, never a
  permission**: see the workspace skill for why nothing can be gated on it, and for the `CODEOWNERS`
  setup that does protect this file. The dashboard does hide its *buttons* for backlog and ceremony
  actions from people the roster does not give them to; **slash commands never refuse.** If a
  developer runs `/triage`, `/plan-sprint` or `/release`, say in one line that the roster gives it to
  the `PO`/`PM`, offer to carry on, and do it — reported like a Definition-of-Ready gap, not enforced.

---

## Vertical slicing (a guardrail, not just advice)

A user story must be a **vertical slice** that delivers user value end-to-end (it normally touches both
front-end and back-end). Never split one story into a "frontend story" + a "backend story" — that
horizontal split delivers no value until both integrate and floods the backlog with developer-only
tech stories. When two developers must divide the work, use optional FE/BE **tasks** under the *same*
story, plus a `Layer` tag. If a story keeps wanting to break along FE/BE lines, it is too big — split
it **vertically** instead (by workflow step, data variation, CRUD operation, or happy-path-then-edges).
`/refine` flags horizontal slices and suggests vertical splits.

---

## Git & traceability conventions

The **US ID is the join key**. Strip it and `/sync-main` becomes guesswork. Bugs follow the same pattern
with `BUG-` and a `fix` commit type.

| Artifact | Shape | Rule |
|---|---|---|
| Branch | `us-014-google-sso` · `bug-014-safari-login` | lowercase, **no type prefix**, ID + slug |
| Commit | `feat(auth): add Google SSO sign-in (US-014)` · `fix(auth): … (BUG-014)` | Conventional Commits — type **kept** |
| PR title | `Google SSO sign-in [US-014]` · `Fix Safari login [BUG-014]` | **no type**, ID in brackets |
| Ledger commit | `ledger(repo-a): US-014 → Done (sprint 7)` | in the **ledger repo**; scope = repo slug |

The first three live in the **code repo**; the ledger commit lives in the **ledger repo**. Keeping the
repo slug as the ledger commit's scope makes `git log --oneline --grep "^ledger(repo-a)"` the per-project
history of PM decisions.

- Match IDs **case-insensitively** (`US-014` ↔ `us-014` ↔ `[US-014]` ↔ `(US-014)`; same for `BUG-`).
- **Squash-merge note:** a squash subject inherits the type-less PR title, so it won't parse as a
  Conventional Commit. This does not affect Agile-Ledger Pro (the changelog is ledger-derived), but teams
  relying on GitHub-side conventional-commit automation should keep the type on the squash subject.
- **FE/BE sub-branches** (optional, two-dev split): `us-014-fe` / `us-014-be` branch off the US branch
  and merge back **into the US branch only — never into main**, preserving 1 US → 1 PR → main. Ephemeral.
- **Git execution is opt-in per project** via `Definitions.md` (default: generate text, don't execute).
  **Never auto-merge**; merges happen on GitHub; the skill reconciles after via `/sync-main`. Always
  confirm before any push or merge.

---

## Templates (read from `references/` when you need the exact shape)

- `references/entry-templates.md` — Epic (with story-index lines) · the overview tables · User Story
  (the full entry, written in `User-Stories.md`) · **Bug** · Task · acceptance criteria (Gherkin) ·
  PR body · commit · delivery note.
- `references/Ideas.template.md`, `Epic-Backlog.template.md`, `User-Stories.template.md`, `Bugs.template.md`, `Sprint.template.md`,
  `Sprints-History.template.md`, `Releases.template.md`, `Definitions.template.md` — the eight scaffold
  files to write when a fresh `<ledger-root>/<repo-slug>/` folder is created.
- `references/Registry.template.md`, `references/Config.template.md` — the two ledger-root files, written
  once by `/init-ledger`.

Read the relevant template before scaffolding or registering, so shapes are never re-derived.

---

## Deliberately NOT included

Story-level versioning (epic-level only); tasks by default; the skill facilitating ceremonies (it
produces the *material* for them); heavy burndown-style dashboards; hard-coded git providers/stacks;
**epics or sprints that span repos** — each repo folder keeps its own backlog, sprint, and velocity, and
cross-repo work is linked (`../repo-b/User-Stories.md#us-021`), never merged into one shared sprint.
If rigor is added later it must stay opt-in and must never slow down `/idea`.
