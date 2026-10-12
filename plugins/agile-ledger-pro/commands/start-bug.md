---
description: Start fixing a bug — move To Do → In Progress, offer the branch
argument-hint: <BUG-ID>
---
Using the **Agile-Ledger Pro** skill, start `$ARGUMENTS`. Move it To Do → In Progress on the `Sprint.md` board (the `Bugs.md` state stays the coarse 🛠️ In Sprint) and offer the branch name `bug-<id>-<slug>` (lowercase, no type prefix). Only run `git` if `git_execution` is `on` in `Definitions.md`; otherwise just hand over the branch name. Then `/review` and `/pr` carry it forward, same as a story.
