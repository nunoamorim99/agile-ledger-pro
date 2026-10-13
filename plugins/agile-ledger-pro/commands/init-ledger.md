---
description: (Ledger) Create the ledger — inside this project, or as its own repo — the one-time setup
argument-hint: [path]
---
Using the **Agile-Ledger Pro Workspace** skill, create the ledger. **Ask where it should live before creating anything** — this is the one decision that is awkward to undo, and both answers are right for different situations.

## 1. Ask which placement

Look at where the user is standing and propose the fitting default, but always let them choose:

**A — Inside this project** (`layout: flat`) · the default when the cwd **is a code repo**
```
project-x/
├── src/
└── agile-ledger/        ← Registry.md · Config.md · the eight files, together
```
One project, one repo, no second repository to clone. The backlog ships with the code and anyone who clones the project gets it. Its commits appear in the project's history — that is the trade, and for one person or a small team it is usually the right one.

**B — Its own repository** (`layout: nested`) · the default when the cwd **holds several code repos**
```
~/Projetos/
├── agile-ledger/        ← Registry.md · Config.md
│   ├── project-x/       ← the eight files
│   └── project-y/
└── project-x/ · project-y/
```
One folder per code repo. A backlog edit never lands on a developer's working branch, every project's ledger sits side by side, and `/workspace-status` reads them all with no code checked out. Right for an organisation, or anyone with more than one project.

Name the trade in one line each and ask. If `$ARGUMENTS` gives a path, still ask which shape that path should hold.

## 2. Create it

Place it at `$ARGUMENTS` if given; otherwise `./agile-ledger` for **A** (inside the current repo) or `./agile-ledger` beside the code repos for **B**. Write `Registry.md` and `Config.md` from the `agile-ledger-pro` skill's `references/` templates — keep `Registry.md`'s `# Agile-Ledger Registry` heading exactly as it is, since that heading is the marker the resolver looks for. Set `layout:` in `Config.md` to `flat` or `nested` to match the answer.

**For A (inside the project):** scaffold the eight files **at the ledger root** straight away — there is one project, so a per-repo subfolder would be redundant — and add the single Registry row with folder `.`, the code path `..`, and the repo's normalized git remote. The project is then ready to use; `/register-repo` is not needed. Do not run `git init`: the ledger belongs to the project's existing repository. Say that the folder is committed with the project like any other, and offer the first commit.

**For B (its own repo):** write only `Registry.md` + `Config.md`, ask for the GitHub org/owner and the clone target, and offer `git init` plus a first commit, telling the user to create the remote and push it themselves. Do **not** scan, clone, or register anything — that is `/discover-repos` and `/register-repo`.

## 3. Stop conditions

If a ledger root already exists at or above the cwd, report where it is and stop: one ledger per workspace. If the user has pre-2.0 `Agile-Ledger/` folders inside code repos, point them at `/migrate-ledger` next.

Switching placement later is a move, not a conversion: the eight files are the same either way. Say so if the user is unsure — it is a reason to pick the simpler option now rather than deliberate.
