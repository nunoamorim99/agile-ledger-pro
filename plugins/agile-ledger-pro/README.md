# Agile-Ledger Pro (plugin)

Plain-Markdown Scrum/Agile product management for Claude Code. The rules live in
`skills/agile-ledger-pro/SKILL.md`; the commands below delegate to it. State is stored in a dedicated
**ledger repository** holding one folder per code repo — plain Markdown, no database, and **no ledger
files inside your code repos**. Read in the Markdown preview (IDs are clickable links); make changes
through the commands.

```
~/Projetos/
├── agile-ledger/            # the ledger repo (its own git repo)
│   ├── Registry.md          # which repos are managed, and where their code is
│   ├── Config.md            # org, commit/push policy, default repo
│   ├── repo-a/              # the eight ledger files for repo-a
│   └── repo-b/
└── repo-a/ · repo-b/        # the code repos — clean
```

Run `/init-ledger` once, then `/register-repo` per project (or `/migrate-ledger` to move a pre-2.0
in-repo ledger across). From inside a code repo the skill finds the sibling ledger automatically; every
command also takes `--repo <slug>` to act on another project.

## Commands

**Set up the ledger**
- `/init-ledger [path]` — create the ledger repo (`Registry.md` + `Config.md`); run once per workspace
- `/register-repo <path|remote> [--from-git]` — add a code repo: its folder, the eight files, a Registry row
- `/migrate-ledger [path]` — move a pre-2.0 in-repo `Agile-Ledger/` into the ledger repo, then clean the code repo
- `/ledger-commit` — review and commit the ledger repo (push only on confirmation)

**Capture**
- `/idea <text>` — drop a raw idea into `Ideas.md` (instant, any language, safe mid-work)
- `/bug <text>` — drop a raw bug report into the `Bugs.md` inbox (instant)

**Triage (inbox → registered)**
- `/triage` — promote ideas into epics / stories; new epics also get a few suggested Draft stories
- `/triage-bug` — register inbox bugs with ID, severity, and priority

**Shape the backlog**
- `/detail-us <US-ID>` — detail one story to Ready (As-a/I-want/So-that + Gherkin AC + estimate + deps)
- `/detail-epic <EPIC-ID>` — detail every story under an epic
- `/create-task <US-ID>` — *(optional)* add a task for an FE/BE split or unplanned sub-work
- `/find-bug <BUG-ID>` — read-only investigation; fills repro / expected / actual / assessment
- `/refine` — INVEST / Definition-of-Ready / vertical-slice / dependency / broken-link checks (report only)

**Plan & run the sprint**
- `/plan-sprint` — propose a Goal, pull Ready stories **and** high-priority bugs within velocity, build the board
- `/start-us <US-ID>` — dependency-gate, To Do → In Progress, offer the branch
- `/start-bug <BUG-ID>` — To Do → In Progress for a bug, offer the branch
- `/review <US-ID | BUG-ID>` — In Progress → In Review (verify on branch, no PR yet)
- `/pr <US-ID | BUG-ID>` — In Review → In PR (PR body filled from the ledger)
- `/done-us <US-ID>` — In PR → Done (gated by DoD + AC), record into the Increment
- `/done-bug <BUG-ID>` — In PR → Fixed, record into the Increment
- `/close-sprint` — record Increment + velocity, return unfinished items to the backlog

**Inspect (read-only views)**
- `/dashboard [--port N] [--ledger PATH]` — serve the whole ledger as a local web page (read it, and apply the same updates from a form)
- `/board` *(alias `/standup`)* — the async sprint snapshot
- `/my-work [name]` — one developer's stories, AC, branch, blockers
- `/status` — whole-product snapshot (states, sprint, velocity, open bugs, unreleased, version)
- `/roadmap` — epics grouped by target version, with rollups
- `/guide` — the command-to-file map + a one-glance state summary
- `/ledger-check` — audit all files for drift and broken links
- `/sync-main` — reconcile git `main` vs. the ledger (what merged while you were away)

**Release & communicate**
- `/release [version]` — cut a Major.Minor version from the Increment
- `/changelog` — derive release notes (Added/Changed + Fixed)

**Across every managed repo**
- `/discover-repos` — detect new repos locally **and** on your GitHub org; propose clone + register
- `/workspace-sync` — one-command "what changed while I was away" across every managed repo
- `/workspace-status` — dashboard across all managed repos (reads the ledger repo only)

These live in the second skill, `skills/agile-ledger-pro-workspace/SKILL.md`, which owns the ledger repo and
the Registry. It discovers, syncs, and *proposes*: cloning, committing, and reconstructed backlog drafts
are always confirmed first, it never writes into a code repo (except removing a migrated folder, on a
branch, after you confirm), and it never pushes, opens PRs, or merges on its own.

Several read-only commands (`/board`, `/status`, `/roadmap`, `/guide`, `/my-work`, `/changelog`) declare
`allowed-tools` so they physically cannot modify files; `/find-bug` and `/sync-main` are likewise
restricted from executing arbitrary shell. `/ledger-commit` is limited to git in the ledger repo. Installed via a marketplace, commands are
namespaced (e.g. `/agile-ledger-pro:idea`, `/agile-ledger-pro:workspace-sync`).

## Files it manages

Per repo, inside `<ledger-repo>/<repo-slug>/`: `Ideas.md` · `Epic-Backlog.md` · `User-Stories.md` ·
`Bugs.md` · `Sprint.md` · `Sprints-History.md` · `Releases.md` · `Definitions.md`. Edit that repo's
`Definitions.md` to configure language, estimation scale, your name, and git execution in the code repo.
At the ledger root: `Registry.md` (the repo map, and the marker that identifies a ledger) and `Config.md`
(org, clone target, and the ledger repo's own commit/push policy).

The dashboard ships in `dashboard/` and needs Python 3.8+ and nothing else; it binds `127.0.0.1` only. See [`dashboard/README.md`](dashboard/README.md) for what it may and may not write.

See the repository README for install options and `SKILL.md` for the full rules.
