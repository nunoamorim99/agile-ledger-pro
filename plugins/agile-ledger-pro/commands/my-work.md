---
description: Show one developer's stories in the current sprint (workload + blockers)
argument-hint: [name]
allowed-tools: Read, Grep, Glob
---
Using the **Agile-Ledger Pro** skill, show the current-sprint work for `$ARGUMENTS` (if empty, use the `Me:` value from `Definitions.md`): their stories, board column, acceptance criteria, branch name, and any blockers. Read-only. Frame strictly as workload and blockers — never as a ranking or productivity comparison.

Read each story's acceptance criteria from **`User-Stories.md`** (the board in `Sprint.md` holds only the column).
