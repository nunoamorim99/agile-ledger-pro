---
description: Report a bug instantly to the bug Inbox (append-only, any language, safe mid-work)
argument-hint: <text>
---
Capture a bug using the **Agile-Ledger Pro** skill.

Append `$ARGUMENTS` verbatim — in whatever language it was written, as the reporter's own words — together with today's absolute date (`YYYY-MM-DD`) to the top of the **🐛 Inbox** section of the resolved repo folder's `Bugs.md`.

Resolve the ledger first (the sibling **ledger repo**, then this repo's folder in it — `--repo <slug>` overrides); the file lives in `<ledger-root>/<repo-slug>/`, never in the code repo.

Rules: no ID, no deduplication, no rewriting, no investigation, no questions. Instant and safe mid-work. Re-read the file before writing. If the repo's folder doesn't exist in the ledger yet, scaffold its eight files from the skill's reference templates first (including `Bugs.md`); if there is no ledger repo at all, say so and offer `/init-ledger`.
