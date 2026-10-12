---
description: (Ledger) Review and commit the ledger repo's changes (push only on confirmation)
allowed-tools: Read, Grep, Glob, Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*), Bash(git branch:*), Bash(git push:*)
---
Using the **Agile-Ledger Pro Workspace** skill, commit the pending changes in the **ledger repo** (never the code repo).

1. Show `git status` and `git diff --stat` for the ledger root, grouped by repo folder, plus the ledger-root files (`Registry.md`, `Config.md`) as their own group.
2. Propose one commit message per group, describing what actually changed — `ledger(repo-a): US-014 → Done (sprint 7)`, `ledger(repo-b): triage 3 ideas → EPIC-007`, `ledger: register repo-c`. Read the diff to write the message; never guess from the command history.
3. Commit on confirmation, one commit per group, on `ledger_branch`.
4. Push only if `ledger_push` is `confirm` **and** the user confirms this push. Never force-push, never rewrite ledger history, never open a PR.

If the ledger root is not the cwd, a `git -C <ledger-root> ...` call falls outside the whitelisted plain forms and will ask for approval once — expected, not a reason to skip the commit.

If the working tree is clean, say so and stop. This is the manual counterpart to `ledger_commit: confirm` in `Config.md`, and the way to tidy up after a session run with `ledger_commit: off`.
