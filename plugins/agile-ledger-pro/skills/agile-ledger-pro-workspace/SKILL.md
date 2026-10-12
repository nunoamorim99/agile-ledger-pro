---
name: agile-ledger-pro-workspace
description: >-
  Owns the Agile-Ledger Pro **ledger repository** — the separate repo that holds one folder per code repo, so
  code repos stay clean. Create the ledger repo, register repositories into it, migrate a pre-2.0 in-repo
  `Agile-Ledger/` folder, discover repositories on a GitHub org (including ones nobody told you about),
  run a single cross-repo "what changed while I was away" sync, reconstruct undocumented work from git
  history into proposed drafts, and commit the ledger repo. Use this skill whenever the user talks about
  setting up or moving the ledger, the ledger repo, a registry of repos, multiple repos, a workspace root,
  "what changed across all projects", detecting new repositories, onboarding a repo, syncing everything
  after time off, or turning git commits and PRs into epics/stories. The per-repo PM rules live in the
  `agile-ledger-pro` skill; this one owns where the ledger is and which repos it covers.
---

# Agile-Ledger Pro Workspace (the ledger repo)

The layer that owns **where the ledger lives**. Since v2.0 that is a dedicated **ledger repository**
holding one folder per code repo:

```
<workspace-root>/                 e.g. ~/Projetos/
├── agile-ledger/                 ← THE LEDGER REPO — its own git repo, pushed like any other
│   ├── Registry.md               # the marker + the map: repo slug ↔ code path ↔ remote ↔ sync state
│   ├── Config.md                 # org, clone target, filters, commit/push policy, default repo
│   ├── repo-a/                   # the eight ledger files for repo-a
│   └── repo-b/
└── repo-a/ · repo-b/             ← the code repos, with NO ledger files in them
```

**Why this shape.** The PM layer changes on the PM's clock, many times a day; the code changes on the
developers' clock. Keeping the ledger out of the code repo means a backlog edit never reaches a
developer's working branch, nobody rebases or pulls to receive bookkeeping, and the whole portfolio is
readable — and diffable — in one place. One repo to clone, one place to look, one history of PM
decisions (`ledger(repo-a): …`).

The `agile-ledger-pro` skill holds the PM rules and writes inside a repo folder. This skill decides which
folder that is, keeps `Registry.md` true, and talks to the network.

---

## Golden safety rules (never violate)

These are stricter than the per-repo skill because this layer touches the network, the filesystem, and
two git repos at once:

- **Ledger files never go into a code repo.** The ledger repo is the only home. A command that would
  write Markdown into a project's working tree is wrong — the one exception is `/migrate-ledger`
  *removing* a legacy folder, on a branch, after confirmation.
- **`Registry.md` is the map, not the truth about work.** Each repo folder's own files are authoritative
  for that project's backlog, sprint, and releases.
- **Discovery uses your existing `gh` auth.** Run `gh repo list <org> …` (read-only). **Never** request,
  read, store, or handle tokens or credentials. If `gh` is not authenticated, say so and stop.
- **Cloning downloads code → always propose and wait.** List the repos that would be cloned and wait for
  explicit confirmation before any `git clone`. No hands-off cloning.
- **Never push, open a PR, or merge without confirmation** — in either repo. `ledger_commit` may commit
  in the ledger repo; `ledger_push` is `off` by default and every push is confirmed when it happens.
  Changes in a code repo stay local on a branch and the **user** pushes.
- **Reconstructed work is always a proposal, never truth.** Epics/stories mined from git land **only** in
  the target repo folder's 💡 Inbox (`Ideas.md`) as drafts flagged `🔍 reconstructed from git — needs
  review`. Never write acceptance criteria, estimates, or a Ready/Delivered state from inference. Never
  invent the "so that…". Never overwrite anything a human wrote.
- **Sweeps are read-only by default.** Every state-changing action (clone, register, draft, commit) is
  surfaced and confirmed, then performed — not assumed.
- **Never delete** rows from the Registry; mark them `archived`/`gone` instead.
- **Migration copies before it removes.** Verify the files landed in the ledger repo (and are committed)
  before offering to delete anything from a code repo.

---

## Setup

`/init-ledger` scaffolds the ledger root — `Registry.md` and `Config.md` from the `agile-ledger-pro` skill's
`references/` templates — and offers `git init`. A ledger root is identified by a `Registry.md` whose
first heading is `# Agile-Ledger Registry`; never by folder name. `Config.md` keys:

```
default_repo:   <repo-slug>                # folder commands act on when run from the ledger root
org:            <github-org-or-owner>      # scanned via gh
clone_target:   ../                        # where new repos are cloned (relative to the ledger root)
include:        []                         # optional name globs (empty = all)
exclude:        [archived, forks]          # skipped from proposals (still listed, marked)
ledger_commit:  confirm                    # confirm | auto | off — commits in the ledger repo
ledger_push:    off                        # off | confirm
ledger_branch:  main                       # branch ledger commits land on
git_execution:  off                        # off = text only; on = allow git in code repos
setup_branch:   agile-ledger-setup         # branch used in a code repo to remove a migrated folder
```

Recommended layout: the ledger repo and the code repos as **siblings** under one workspace root. The
resolver walks up from the cwd and checks each level and its children, so a developer standing in
`~/Projetos/repo-a` finds `~/Projetos/agile-ledger` without configuring anything.

---

## Commands

### `/init-ledger [path]`
Create the ledger repo. Default location: `./agile-ledger` if the cwd looks like a workspace root,
otherwise ask. Write `Registry.md` + `Config.md` from the templates, ask for the GitHub org and clone
target, and offer `git init` + a first commit (`chore: init agile-ledger`). Do **not** scan or clone.
If a ledger root already exists at or above the cwd, say where it is and stop — one ledger per workspace.

### `/register-repo <path|remote> [--from-git]`
Add one code repo to the ledger.
1. Resolve the repo: a local path, or a remote to clone into `clone_target` (**propose and confirm**
   before cloning).
2. Derive the slug (lowercase-hyphenated repo name); if it is taken, ask rather than overwrite.
3. Create `<ledger-root>/<slug>/` and scaffold the eight files from the `agile-ledger-pro` skill's
   `references/*.template.md` — **only if absent** (if the folder exists, report and stop).
4. Add a Registry row: slug, code path, normalized remote, `active`, no sync SHA yet.
5. With **`--from-git`**: mine the repo's history and **propose** reconstructed epics/stories as drafts
   in that folder's `Ideas.md`, each flagged `🔍 reconstructed from git`, following
   `references/reconstruction-guide.md`. Proposals for `/triage`, never confirmed truth.
6. Commit in the ledger repo per `ledger_commit` (`ledger(<slug>): register repo`). **Nothing is written
   into the code repo.**

### `/migrate-ledger [path]`
Move a pre-2.0 in-repo ledger into the ledger repo. The upgrade path, and safe to run repeatedly.
1. Find the code repo's `Agile-Ledger/` folder (the cwd's repo by default, or `path`).
2. Register the repo if it isn't yet, then **copy the files verbatim** into `<ledger-root>/<slug>/` —
   content is never rewritten, re-dated, or re-numbered; history is preserved as the team wrote it.
3. If the target folder already has files, **stop and report the conflict** per file. Never merge two
   ledgers silently; offer to keep the central copy, take the in-repo copy, or let the user resolve it.
4. Commit the ledger repo (`ledger(<slug>): migrate ledger from the code repo`) — then **verify** the
   files are present and committed.
5. Only then **offer** to remove `Agile-Ledger/` from the code repo: create `setup_branch`, `git rm -r`
   the folder, commit locally, and tell the user the branch is ready to push / PR. Never push, PR, or
   merge; if `git_execution` is `off`, just say which folder to delete and leave it untouched.
6. Report what moved, what is pending, and the one-line new location.

### `/discover-repos`
Find repositories — the new-repo detector.
1. **Local scan:** find directories containing `.git` under the workspace root; record path + remote.
2. **Org scan:** `gh repo list <org> --limit 1000 --json name,url,isArchived,isFork …` (read-only).
3. **Diff against `Registry.md`:** classify each repo as **new** (not registered), **known**, or
   **local-only** (checked out but not in the org list). Apply `exclude` filters (still list them, marked).
4. **Report** the three groups. For **new** repos, **propose** `git clone` into `clone_target` where
   needed and `/register-repo` on each — and **wait for confirmation** before cloning anything.
5. After confirmed registration, add Registry rows (never overwrite existing rows).

### `/workspace-sync`
The one-command "what changed while I was away." Across every repo in `Registry.md`:
1. Run **`/discover-repos`** to catch any new repos.
2. For each known repo, run the per-repo **`/sync-main`** reconciliation — reading git in the **code
   repo** at its registered path, writing only into its **ledger folder** (merges to `main` since that
   repo's last-sync SHA, mapped to `[US-xxx]`/`[BUG-xxx]` case-insensitively).
3. **Flag undocumented work:** merges with **no** id are delivered work nobody registered — for each,
   **propose** a reconstructed draft in that folder's `Ideas.md` (flagged, linked to the commit/PR).
4. Produce **one consolidated report**, per repo: new / merged-and-reconciled / undocumented-drafted /
   unchanged, plus blocked items and unreleased counts.
5. Update each repo's last-sync SHA and `last swept` after the user reviews, then offer **one** commit
   (`ledger: workspace sync <date>`) — the one case where touching several folders in a single commit is
   correct, because it is a single sweep.
A repo whose code path is missing is reported as `path not found`, not silently skipped. Read-only by
default: it drafts and reconciles only on confirmation. The point: you learn *where* to look from one
command, then walk into each flagged repo to triage the news.

### `/workspace-status`
A dashboard from `Registry.md` + every repo folder: per repo, the current sprint + goal, unreleased
(Increment) count, blocked count, open bugs, and last-sync date. Read-only, and it needs **only the
ledger repo** — the code repos don't have to be checked out at all, which makes it the view to run from
a laptop that has just the ledger cloned.

### `/ledger-commit`
Review and commit the ledger repo. Show `git status` / `git diff --stat` for the ledger root, group the
changes by repo folder, propose a message per group (`ledger(repo-a): …`), and commit on confirmation.
Push only if `ledger_push: confirm` and the user confirms. This is the manual counterpart to
`ledger_commit: confirm`, and the way to tidy up after a session run with `ledger_commit: off`.

---

## Reconstruction (git → proposed backlog)

The detection signal already exists in the per-repo skill: `/sync-main` flags **merges to main with no
`[US-xxx]` id** — that *is* undocumented delivered work. For a newly registered repo, the whole history
is the signal. Turn signal into *proposals*, never into confirmed stories — see
`references/reconstruction-guide.md` for the clustering heuristics and the hard guardrails (no invented
value, no invented acceptance criteria, conservative output, Inbox-only, human triages).

This keeps the skill's core philosophy intact: the tool does the bookkeeping legwork; the human keeps
judgment over what is real, what the user value is, and how it's sliced.

---

## Idempotency

Everything here is safe to re-run. `/init-ledger` refuses to nest a second ledger root; discovery diffs
against the Registry; `/register-repo` skips a folder that already exists; `/migrate-ledger` re-run after
a partial move reports what is already in place instead of copying over it; sweeps only look at commits
after each repo's recorded last-sync SHA; reconstructed items only ever appear once in the Inbox (don't
re-propose an already-drafted commit/PR). Never overwrite human-written ledger content under any
circumstances.
