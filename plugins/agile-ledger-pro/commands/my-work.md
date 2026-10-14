---
description: Show one developer's stories in the current sprint (workload + blockers)
argument-hint: [name]
allowed-tools: Read, Grep, Glob
---
Using the **Agile-Ledger Pro** skill, show the current-sprint work for `$ARGUMENTS`: their stories, board column, acceptance criteria, branch name, and any blockers. Read-only. Frame strictly as workload and blockers — never as a ranking or productivity comparison.

**With no name given, resolve who is asking** in this order, and say which answer you used:

1. `Me.local.md` at the ledger root — this machine's own answer, ignored by git.
2. `Me:` in the project's `Definitions.md` — the shared fallback, which is all a solo ledger ever needed.
3. Neither → say so and point at `/whoami`. Do not guess from the git config here; this command has no shell, and showing the wrong person's sprint is worse than asking.

Match the resolved name against the `## Team` roster in the ledger root's `Config.md` before filtering: a story assigned `@rita` and a `Me` of `Rita Soares` are the same person, and both have to find the same work.

Read each story's acceptance criteria from **`User-Stories.md`** (the board in `Sprint.md` holds only the column).
