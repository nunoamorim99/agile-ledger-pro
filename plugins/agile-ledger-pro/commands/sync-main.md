---
description: Reconcile git main vs. the ledger — what merged while you were away (read-only)
allowed-tools: Read, Grep, Glob, Edit, Bash(git fetch:*), Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git branch:*), Bash(git show:*)
---
Using the **Agile-Ledger Pro** skill, reconcile `main` against the ledger. Read git in the **code repo**; write only in the resolved **ledger folder** — take the code path from `Registry.md` or the cwd. Fetch main, list merges since the `Last main sync` cursor in `Sprint.md`, and map each commit to its US via the bracketed or parenthesized ID (case-insensitive). Flag two cases: (1) merged but the ledger does not show it Done → propose marking Done and filling the Increment; (2) merged with no US ID → surface it as off-plan work to back-fill or query. Read-only by default; update the sync cursor and sync log only after the user reviews.

Run the git commands **from the code repo's directory** where possible — the `allowed-tools` whitelist covers the plain `git fetch` / `log` / `diff` / `status` / `branch` / `show` forms, so a `git -C <path> ...` variant (needed when the code repo is elsewhere) falls outside it and will ask for approval once. Never reach for a git subcommand that writes.
