---
description: (Ledger) Move a pre-2.0 in-repo Agile-Ledger/ folder into the ledger repo, then clean the code repo
argument-hint: [path]
---
Using the **Agile-Ledger Workspace** skill, migrate a pre-2.0 in-repo ledger into the ledger repository. Target the repo at `$ARGUMENTS`, or the cwd's repo when no argument is given. Safe to re-run.

1. Locate the code repo's `Agile-Ledger/` folder. If there is none, say so and stop.
2. Register the repo first if it isn't in `Registry.md` yet (`/register-repo` behaviour, no `--from-git`).
3. **Copy the files verbatim** into `<ledger-root>/<slug>/`. Never rewrite, re-date, re-number, or "tidy" content during a migration — the team's history moves across exactly as they wrote it. Carry over any extra files the team added alongside the eight.
4. If the target folder already holds files, **stop and report the conflict per file**. Never merge two ledgers silently; offer to keep the central copy, take the in-repo copy, or let the user resolve it by hand.
5. Commit the ledger repo (`ledger(<slug>): migrate ledger from the code repo`) per `ledger_commit`, then **verify** the files are present and committed.
6. Only then **offer** to clean the code repo: create `setup_branch`, `git rm -r Agile-Ledger`, commit locally, and hand the branch over for the user to push and PR. **Never push, PR, or merge.** If `git_execution` is `off`, name the folder to delete and change nothing in the code repo.
7. Report what moved, what is still pending, and the new one-line location (`Ledger: <ledger-root> → <slug>`).

Until the code repo's copy is removed, treat the **central folder as the source of truth** and say that the in-repo copy is stale, so no one edits two ledgers at once.
