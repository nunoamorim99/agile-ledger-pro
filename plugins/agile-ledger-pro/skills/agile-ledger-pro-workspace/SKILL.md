---
name: agile-ledger-pro-workspace
description: >-
  Owns the Agile-Ledger Pro **ledger repository** — the separate repo that holds one folder per code repo, so
  code repos stay clean. Create the ledger repo, register repositories into it, migrate a pre-2.0 in-repo
  `Agile-Ledger/` folder, discover repositories on a GitHub org (including ones nobody told you about),
  run a single cross-repo "what changed while I was away" sync, reconstruct undocumented work from git
  history into proposed drafts, and commit the ledger repo. Use this skill whenever the user talks about
  setting up or moving the ledger, joining a ledger somebody else created, who they are on a ledger,
  the ledger repo, a registry of repos, multiple repos, a workspace root,
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
│   ├── Me.local.md               # who *you* are — git-ignored, one per clone
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
- **Never commit `Me.local.md`, and never write a person's own name into a shared file.** Identity
  belongs to one clone; `Definitions.md` and `Config.md` belong to the team. A name in a committed
  file reaches everyone who clones and is overwritten by the next person to fix it.
- **Never delete** rows from the Registry; mark them `archived`/`gone` instead.
- **Migration copies before it removes.** Verify the files landed in the ledger repo (and are committed)
  before offering to delete anything from a code repo.

---

## Setup

`/init-ledger` scaffolds the ledger root — `Registry.md` and `Config.md` from the `agile-ledger-pro` skill's
`references/` templates — and offers `git init`. A ledger root is identified by a `Registry.md` whose
first heading is `# Agile-Ledger Registry`; never by folder name. `Config.md` keys:

```
layout:         nested                     # nested = own ledger repo | flat = inside its one project
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

Beside those two sits **`Me.local.md`** — who *this* clone's person is, git-ignored and never
committed. It is not part of the ledger's content; see **Joining a ledger somebody else created**.

`Config.md` also holds the team, under a `## Team` heading — optional, and absent in older ledgers:

```
| Name | Role | GitHub |
|---|---|---|
| Ada Lovelace | PO | @ada |
| Grace Hopper | Dev | @grace |
```

Roles are `PO` · `PM` · `SM` · `Dev` · `QA` · `Design`, matched case-insensitively and through the
obvious synonyms (`Product Owner`, `developer`, `tester`, `ux`); an unrecognised role is kept as
written rather than coerced. Use the roster when a command needs a person: to offer names for
`Assignee` instead of asking the user to retype one, and to resolve `Me:` in a project's
`Definitions.md` whether it is written as a handle (`@ada`) or a display name (`Ada Lovelace`) —
`@ada` and `Ada Lovelace` are the same person, and `/my-work` must treat them so.

## Joining a ledger somebody else created

The second person onwards does **not** set the ledger up again. A Product Manager runs
`/init-ledger`, chooses the placement, writes the `## Team` roster and the team's rules; everyone
else clones and has one question to answer — *which of these people am I?*

So before asking a setup question, **resolve the ledger first**. A ledger root at or above the cwd
means this is a joiner, and the answer is `/whoami`, not `/init-ledger`. Re-running setup on a
joiner is the failure to avoid: it invites a second answer to a question the team has settled, and
it writes their name into a file everybody shares.

**Identity is per-clone; the roster is shared.** `Me:` in a project's `Definitions.md` is committed
like every other line in that file, so one person's name there reaches every clone and is
overwritten by the next person to correct it — and when the team has put `Definitions.md` under
`CODEOWNERS`, a developer cannot land the correction at all. Each person's own name therefore goes
in `Me.local.md` at the **ledger root**:

```
name:   Rita Soares
handle: rita
```

written from `references/Me.local.template.md`, with `Me.local.md` appended to
`<ledger-root>/.gitignore` — the ledger root in both placements, since git honours a `.gitignore` in
a subdirectory. **Never commit it**, and exclude it from a `ledger_commit: auto` commit. The shared
`Me:` is still read when no local file exists, because that is what a one-person ledger has always
used and it must keep working.

Being on the roster and having said who you are are two different things: a name in `## Team` means
the team can assign you work, and `Me.local.md` means this clone knows which of them to filter by.
A person can have either without the other.

## Roles are a roster, not permissions

**Never tell a user that a role in this file restricts anything.** The ledger is Markdown in a git
repo: everyone who can clone it can read *and* edit every file, `Config.md` included. The dashboard
is a server each person runs on their own machine against their own clone, with no authentication
and no accounts. Claiming a role protects something would be lying to the user about a protection
they do not have — and trivially so, because the file that says who they are is in their own
working tree.

**What the roster does change, and it is cosmetic.** The dashboard reads it twice:

- The **Settings** screen shows the shared rules — the ledger config, the estimation scale, the
  Definition of Ready and Done, the roster — *read-only* to anyone it is not told is a `PO` or `PM`.
- **Buttons for actions the roster assigns elsewhere are hidden**: triage, discarding an idea,
  capturing one, **writing a Draft up into a Ready story**, moving a story to an epic, planning and
  closing the sprint, cutting a release. The board, the bug report, editing a story that exists,
  the estimate, the blocked flag and everything else a developer does are untouched.
  `model.ACTION_ROLES` is the whole list, one line per action.

  The write-up and the edit are deliberately on opposite sides of that line. `detail_story` takes a
  Draft to Ready, which means writing the story sentence and the acceptance criteria against the
  Definition of Ready — the Product Owner's. `update_story` edits a story that already exists, and
  that is where the **estimate** lives, which is the developer's by this skill's own rule on who
  owns size and who owns value. Never collapse the two into one answer.

Both exist to stop the accidental edit, which is most unwanted edits. They stop nothing else: that
person can rewrite their own `Me.local.md`, open `Config.md` in an editor, or POST to the
dashboard's action endpoint. Nothing is ever *hidden* — the rules are shown in full, the idea inbox
stays readable, and the command sheet still lists every command with a line saying whose it is —
because a developer who cannot see the Definition of Done cannot meet it.

**Slash commands do not check.** A command is typed by a person who may well be acting for the
Product Owner, and refusing it would be obstructive for a guardrail this thin. When a role the
roster does not give them runs a backlog or ceremony command, **say whose it is in one line and
offer to carry on** — the same way a Definition-of-Ready gap is reported rather than enforced. Do
it once per session, not before every command, and never refuse.

What *does* enforce it is the git host. When a team asks how to stop the Definition of Done or the
estimation scale being changed without the Product Owner, the answer is a `CODEOWNERS` file at the
ledger root naming the `PO`/`PM` handles from the roster:

```
/Config.md          @ada
/*/Definitions.md   @ada          # layout: flat → /Definitions.md
```

plus branch protection on `ledger_branch` requiring code-owner review. A developer can still edit
those files locally; the change cannot reach the branch without the owner approving the PR. Say both
halves when you offer it: `CODEOWNERS` alone does nothing until branch protection is switched on in
the repository's settings, which is a manual step you cannot do for them.

## Two placements

The ledger lives in one of two places, chosen once at `/init-ledger` and recorded as `layout`.

**`nested` — the ledger has its own repository**, holding one folder per code repo
(`<ledger-root>/<repo-slug>/*.md`). The ledger repo and the code repos sit as **siblings** under one
workspace root. Right for an organisation or anyone with more than one project: a backlog edit never
lands on a developer's working branch, every project's ledger is in one place, and
`/workspace-status` reads them all with no code checked out.

```
~/Projetos/
├── agile-ledger/     Registry.md · Config.md · repo-a/ · repo-b/
└── repo-a/ · repo-b/
```

**`flat` — the ledger lives inside the single project it belongs to**
(`<project>/agile-ledger/*.md`), so the eight files sit at the ledger root with **no per-repo
folder**. Right for one person with one repo: nothing extra to clone, and the backlog ships with the
code. Its commits do appear in the project's history — that is the trade, and it is the one the user
accepted when they chose it.

```
project-x/
├── src/
└── agile-ledger/     Registry.md · Config.md · the eight files
```

**Reading the placement.** The files on disk are the answer: a root holding `Epic-Backlog.md` (or
`Ideas.md`, or a pre-2.0 `Backlog.md`) is **flat**; otherwise it is **nested**. The `layout` key only
decides a freshly scaffolded ledger that has no backlog files yet. Never infer the placement from the
folder's name.

In a flat ledger the Registry has exactly **one** row, its folder column is `.`, and the project is
named by the repo the ledger sits in. `default_repo` is unnecessary there.

The resolver is the same either way: it walks up from the cwd and checks each level **and its
children**, so it finds `~/Projetos/agile-ledger` from `~/Projetos/repo-a`, and
`project-x/agile-ledger` from `project-x/src/`, with nothing configured.

---

## Commands

### `/init-ledger [path]`
**Resolve the ledger before asking anything.** A ledger root at or above the cwd means this person is
joining one that exists: say where it is, do **not** run any of the setup below, and run `/whoami`
instead (see **Joining a ledger somebody else created**). Another project for an existing ledger is
`/register-repo`; a pre-2.0 in-repo folder is `/migrate-ledger`.

With no ledger in the workspace, create one. **Ask which placement first** — it is the one decision
that is awkward to undo.
Propose the fitting default from where the user is standing (inside a code repo → `flat`; in a
directory holding several code repos → `nested`), name the trade in a line each, and let them choose.

Write `Registry.md` + `Config.md` from the templates, keeping the `# Agile-Ledger Registry` heading
exactly as it is, and set `layout` to match.

- **`flat`** — scaffold the **eight files at the ledger root** immediately and add the single Registry
  row (folder `.`, code path `..`, the repo's normalized remote). The project is ready at once;
  `/register-repo` is not needed. Do **not** `git init`: the ledger belongs to the project's existing
  repository. Offer the first commit and say the folder travels with the project.
- **`nested`** — write only the two root files, ask for the GitHub org and clone target, and offer
  `git init` + a first commit (`chore: init agile-ledger`), telling the user to create the remote and
  push it themselves. Do **not** scan or clone.

Then ask for the `## Team` roster, offer `CODEOWNERS` when a `PO`/`PM` has a handle, and finish by
recording the creator through the `/whoami` step — `Me.local.md` plus its `.gitignore` entry — even
for a team of one. Their own name must not go into `Definitions.md`'s shared `Me:`.

### `/whoami [name|@handle]`
Record who the person at this clone is — the whole of a joiner's setup, and the last step of
`/init-ledger` for whoever creates the ledger.

1. Resolve the ledger root. **No ledger** → nothing to join; offer `/init-ledger`. **`Me.local.md`
   already names someone** → say who, in one line, and stop; an argument overrides it.
2. Try to work out who they are, strongest signal first: `gh api user --jq .login` against the
   roster's GitHub column (`gh` is authenticated as them, so this one is theirs rather than a
   guess), then `git config user.name` against the Name column, then the local part of
   `git config user.email`.
3. **Propose, never assert.** One match → name the signal that matched and wait for a yes; a
   self-declared git name and a shared machine both give wrong answers, and a wrong `Me` silently
   shows somebody else's sprint. No match, several matches, or no shell → list the roster
   (name · role · handle) and ask, offering *not on the roster* as a real answer. No roster at all →
   just ask for their name.
4. Write `Me.local.md` at the ledger root from the template and make sure `.gitignore` covers it.
5. **Not on the roster** → record the identity anyway, then say what is missing: no row in `## Team`
   means nobody can assign them work from the dashboard. Adding the row edits `Config.md`, the file
   most often under `CODEOWNERS`, so offer the two honest routes — ask the `PO`/`PM`, or open a PR —
   and never claim a protected branch accepted a push it will refuse.

### `/register-repo <path|remote> [--from-git]`
Add one code repo to the ledger.

**In a `flat` ledger there is nothing to register** — it holds exactly one project, already scaffolded
by `/init-ledger`. If asked to register a second project into one, do not reshape the folder silently:
explain that a flat ledger belongs to its own repo, and offer the two real options — move the ledger
out into its own repository (`nested`) so it can hold several projects, or give the other project its
own flat ledger. Let the user choose.

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
Move a pre-2.0 in-repo ledger into the ledger repo, **and reshape it if it predates the eight files**.
The upgrade path, and safe to run repeatedly.

v2.0 changed only where the ledger lives, but the **file layout changed during v1**: `Ideas.md` arrived
in v1.4, `Bugs.md` in v1.3, and the `Backlog.md` → `Epic-Backlog.md` + `User-Stories.md` split in v1.2.
So relocation alone is enough for a team already on v1.4+, and **not** enough for anyone earlier — a
verbatim copy would leave a `Backlog.md` sitting where four files are expected, which the per-repo
skill cannot read.

1. Find the code repo's `Agile-Ledger/` folder (the cwd's repo by default, or `path`).
2. **Detect the era** from the files actually present, then confirm it against the content of
   `Backlog.md` (full story entries under an epic, or one-line index entries?). State the era and the
   per-file plan, and **wait for confirmation** before touching anything.
3. Register the repo if it isn't yet, then **copy the files verbatim** into `<ledger-root>/<slug>/` —
   content is never rewritten, re-dated, or re-numbered; history is preserved as the team wrote it.
4. If the target folder already has files, **stop and report the conflict** per file. Never merge two
   ledgers silently; offer to keep the central copy, take the in-repo copy, or let the user resolve it.
5. **Convert, only when the era calls for it**, following `references/v1-migration.md`: lift the old
   `## 📥 Inbox` into `Ideas.md`, split nested story detail out into `User-Stories.md` leaving a
   one-line index entry on the epic, rename `Backlog.md` to `Epic-Backlog.md`, scaffold the files that
   did not exist yet, rewrite pre-v1.5 headings to **bare IDs** so anchors work, and repoint the links
   the rename invalidated. Conversion **relocates text and never rewrites it**, drops nothing (what
   cannot be classified goes under `## ❓ Unsorted from migration`), and **invents nothing** — a
   missing estimate, priority or severity stays `—`. Rebuild the overview tables afterwards; they are
   derived.
6. Commit the ledger repo (`ledger(<slug>): migrate ledger from the code repo`) — then **verify** the
   files are present and committed, and run the `/ledger-check` audit over the result.
7. Only then **offer** to remove `Agile-Ledger/` from the code repo: create `setup_branch`, `git rm -r`
   the folder, commit locally, and tell the user the branch is ready to push / PR. Never push, PR, or
   merge; if `git_execution` is `off`, just say which folder to delete and leave it untouched.
8. Report the era detected, what moved where with counts, every heading rewritten to a bare ID,
   anything left unsorted, what `/ledger-check` still flags, and the one-line new location.

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

Everything here is safe to re-run. `/init-ledger` refuses to nest a second ledger root and sends a
joiner to `/whoami`; `/whoami` reports the identity already recorded instead of asking again; discovery diffs
against the Registry; `/register-repo` skips a folder that already exists; `/migrate-ledger` re-run after
a partial move reports what is already in place instead of copying over it; sweeps only look at commits
after each repo's recorded last-sync SHA; reconstructed items only ever appear once in the Inbox (don't
re-propose an already-drafted commit/PR). Never overwrite human-written ledger content under any
circumstances.
