# Agile-Ledger Workspace — Spec (Phase 2, design-complete)

> Companion to `Agile-Ledger-skill-spec.md`. Ships as a **second skill inside the same plugin**
> (`skills/agile-ledger-workspace/`), so installation is still one step and the core skill stays lean.
>
> **Revised in v2.0.** This layer was designed as an *optional* orchestrator sitting above per-repo
> ledgers. Since v2.0 it **owns the ledger repository itself** — the ledger is no longer a folder in the
> code repo, so this skill is no longer optional: it creates the ledger, keeps `Registry.md` true, and
> decides which folder the core skill writes to. The architecture, command list, and files below are
> updated accordingly; the safety boundaries in section 4 are unchanged and still binding.

## 1. Problem it solves

A remote PM running many repos hits two blind spots, especially after time off: **repos created on the
host that nobody mentioned**, and **work merged to `main` that was never registered**. Going folder by
folder to find both is the pain. This layer makes it one command.

## 2. Architecture

```
<workspace-root>/
├── agile-ledger/                # THE LEDGER REPO — its own git repo
│   ├── Registry.md              # marker + map: repo slug ↔ code path ↔ remote ↔ sync state
│   ├── Config.md                # org, clone target, filters, commit/push policy, default repo
│   ├── repo-a/                  # the eight ledger files for repo-a
│   └── repo-b/
└── repo-a/ · repo-b/            # the code repos — no ledger files in them
```

This skill owns *where* the ledger is; the core skill owns *what* goes in it. Each repo folder is
authoritative for that project's backlog, sprint, and releases; `Registry.md` is only the map.
Resolution from a code repo is a walk up the tree to the sibling ledger root plus a git-remote match in
the Registry — nothing is written into the code repo to make it work.

## 3. Locked decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Discovery scope | **Local + org-level** via `gh repo list <org>` — needed to catch truly-new, uncloned repos |
| 2 | Onboard policy | **Always propose and wait for confirmation** before cloning/bootstrapping |
| 3 | Reconstruction | **Flag undocumented work, then follow the normal flow to validate** — propose as Inbox Drafts, human triages; never auto-register as truth |
| 4 | Ledger placement *(revised v2.0)* | A **central ledger repo**, one folder per code repo; the orchestrator commits there per `ledger_commit`, and pushing is confirmed (`ledger_push: off` by default). In a **code** repo it only ever removes a migrated folder, on a branch, for the user to push |
| 5 | Upgrade path *(v2.0)* | `/migrate-ledger` copies an in-repo ledger across verbatim, verifies it, then offers the cleanup branch |

## 4. Safety boundaries (stricter than the core skill)

- Each repo folder is the source of truth for its own project; `Registry.md` is only the map.
- **Never write a ledger file into a code repo.** The single exception is `/migrate-ledger` *removing* a
  legacy folder, on a branch, after confirmation.
- Discovery uses the user's existing `gh` auth (read-only). The skill never requests, stores, or handles
  tokens or credentials.
- Cloning downloads code → always propose the list and wait for explicit confirmation.
- **Never push, open a PR, or merge without confirmation** — in either repo. `ledger_commit` may commit
  in the ledger repo; `ledger_push` is `off` by default. In a code repo, work stays local on
  `setup_branch` and the user does the rest.
- Reconstructed Epics/Stories are **proposals only** — Inbox Drafts flagged `🔍 reconstructed from git`,
  never with invented value or acceptance criteria, never Ready/Delivered, never overwriting human content.
- Sweeps read-only by default; every state-changing action is confirmed. Registry rows are never deleted.

## 5. Commands (7; namespaced under the plugin)

- `/init-ledger [path]` — create the ledger repo: `Registry.md` + `Config.md`, org + clone target,
  offered `git init`. Setup only; refuses to nest a second ledger root.
- `/register-repo <path|remote> [--from-git]` — add a code repo: its folder with the eight files (only
  if absent) and a Registry row; `--from-git` seeds proposed drafts from history. Writes nothing into
  the code repo.
- `/migrate-ledger [path]` — the v1 to v2 upgrade: copy an in-repo `Agile-Ledger/` across verbatim,
  report per-file conflicts instead of merging, commit, verify, then **offer** the cleanup branch.
- `/discover-repos` — local `.git` scan + `gh repo list <org>`, diff against the Registry, classify
  new / known / local-only, **propose** clone + register for new repos (confirm before cloning).
- `/workspace-sync` — the holidays command: discovery + per-repo `/sync-main` (git read in the code
  repo, writes in the ledger folder) + flag/propose undocumented merges → **one consolidated report**.
  Read-only by default; `path not found` is reported, never skipped silently.
- `/workspace-status` — dashboard across managed repos (sprint, unreleased, blocked, open bugs, last
  sync). Reads the ledger repo only, so no code needs to be checked out.
- `/ledger-commit` — review the ledger repo's diff, commit per repo folder, push only on confirmation.

## 6. Reconstruction logic (git → proposed backlog)

Signal: merges to `main` with no `[US-xxx]` id (per-repo `/sync-main` already detects these); for a new
repo, the whole history. Heuristics (see `references/reconstruction-guide.md`): prefer merged PRs (≈ one
candidate story), cluster by area/theme into candidate epics, propose `feat`/user-facing work and skip
chore/ci/style noise, stay conservative (3–8 epics with a few stories, not a per-commit dump). Output is
always Inbox Drafts with `value: ?? (confirm)` where unclear — the human writes value, AC, and slicing at
`/triage`. Idempotent: only looks past each repo's last-sync SHA; never re-proposes a drafted commit/PR.

## 7. Files

```
agile-ledger/                 # the ledger repo
├── Registry.md               # managed repos: slug, code path, remote, status, last-sync SHA, last
│                             # swept (never-delete rows); its heading is the ledger-root marker
├── Config.md                 # default_repo, org, clone_target, include/exclude, ledger_commit,
│                             # ledger_push, ledger_branch, git_execution, setup_branch
└── <repo-slug>/              # the core skill's eight files, one folder per managed repo
```

Skill assets: `skills/agile-ledger-workspace/{SKILL.md, references/reconstruction-guide.md}`. The two
ledger-root templates (`Registry.template.md`, `Config.template.md`) live in the **core** skill's
`references/`, next to the eight per-repo templates — so a standalone core-skill install (the Claude.ai
web upload) can still scaffold a complete ledger.

## 8. Deliberately NOT included

Hands-off auto-onboarding (always confirm, per decision 2); unconfirmed pushes/PRs/merges; epics or
sprints shared across repos (each folder keeps its own; cross-repo work is linked, not merged);
auto-registering reconstructed work as truth; keeping the v1 in-repo layout as a supported second mode
(one model, with `/migrate-ledger` as the bridge).

## 9. Extension points

A non-GitHub host adapter (the `gh` call is the only host-specific piece); a `/workspace-roadmap` rolling
epics up across repos; scheduled sweeps. Keep every safety boundary above when extending.
