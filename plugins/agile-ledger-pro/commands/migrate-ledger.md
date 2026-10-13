---
description: (Ledger) Move a pre-2.0 in-repo Agile-Ledger/ folder into the ledger repo, converting an older file layout, then clean the code repo
argument-hint: [path]
---
Using the **Agile-Ledger Pro Workspace** skill, migrate a pre-2.0 in-repo ledger into the ledger repository. Target the repo at `$ARGUMENTS`, or the cwd's repo when no argument is given. Safe to re-run.

1. Locate the code repo's `Agile-Ledger/` folder. If there is none, say so and stop.
2. **Detect which layout it uses** and say so before touching anything. v2.0 moved the ledger but the
   file layout changed during v1 — `Ideas.md` arrived in v1.4, `Bugs.md` in v1.3, and the
   `Backlog.md` → `Epic-Backlog.md` + `User-Stories.md` split in v1.2. A folder already holding the
   eight files only needs relocating; a `Backlog.md` needs **converting as well**, or the result is a
   folder the skill cannot read. Show the era, the per-file plan, and wait for confirmation.
3. Register the repo first if it isn't in `Registry.md` yet (`/register-repo` behaviour, no `--from-git`).
4. **Copy the files verbatim** into `<ledger-root>/<slug>/`. Never rewrite, re-date, re-number, or "tidy" content during a migration — the team's history moves across exactly as they wrote it. Carry over any extra files the team added alongside the eight.
5. If the target folder already holds files, **stop and report the conflict per file**. Never merge two ledgers silently; offer to keep the central copy, take the in-repo copy, or let the user resolve it by hand.
6. **Convert the layout when the era calls for it**, following the Workspace skill's
   `references/v1-migration.md`: the old `## 📥 Inbox` becomes `Ideas.md`, nested story detail moves to
   `User-Stories.md` leaving a one-line index entry on its epic, `Backlog.md` becomes
   `Epic-Backlog.md`, the files that did not exist yet are scaffolded, pre-v1.5 headings become
   **bare IDs** so anchors work, and links the rename invalidated are repointed. Conversion relocates
   text and never rewrites it, drops nothing, and **invents nothing** — a missing estimate, priority or
   severity stays `—`. Rebuild the overview tables afterwards; they are derived.
7. Commit the ledger repo (`ledger(<slug>): migrate ledger from the code repo`) per `ledger_commit`, then **verify** the files are present and committed, and run the `/ledger-check` audit over the result.
8. Only then **offer** to clean the code repo: create `setup_branch`, `git rm -r Agile-Ledger`, commit locally, and hand the branch over for the user to push and PR. **Never push, PR, or merge.** If `git_execution` is `off`, name the folder to delete and change nothing in the code repo.
9. Report the era detected, what moved where with counts, every heading rewritten to a bare ID, anything left under `## ❓ Unsorted from migration`, what `/ledger-check` still flags, and the new one-line location (`Ledger: <ledger-root> → <slug>`).

Until the code repo's copy is removed, treat the **central folder as the source of truth** and say that the in-repo copy is stale, so no one edits two ledgers at once.
