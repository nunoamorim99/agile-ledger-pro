---
description: Open the PR for a verified story (In Review → In PR), body filled from the ledger
argument-hint: <US-ID | BUG-ID>
---
Using the **Agile-Ledger Pro** skill, move `$ARGUMENTS` In Review → **In PR** (verified work only). Generate the PR body from the ledger using the PR template: story sentence, parent epic, acceptance criteria as a reviewer checklist, how-to-test, and the DoD checklist; title `<title> [US-<id>]` (no type prefix). Hand it over to paste, or run `gh pr create` only if `git_execution` is `on`. Never merge.

For a **bug**, title `<title> [BUG-xxx]`, body references the bug and says `Fixes BUG-xxx`.
