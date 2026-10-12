---
description: Start a story — dependency-gate, move To Do → In Progress, offer the branch
argument-hint: <US-ID>
---
Using the **Agile-Ledger Pro** skill, start `$ARGUMENTS`.

First run the **dependency gate**: if any linked dependency is not Done, stop and warn, naming it, and ask whether to proceed or build the dependency first. Otherwise move the story To Do → In Progress on the board and offer the branch name `us-<id>-<slug>` (lowercase, no type prefix). Only run `git` if `git_execution` is `on` in `Definitions.md`; otherwise just hand over the branch name.
