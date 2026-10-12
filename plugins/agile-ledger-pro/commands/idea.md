---
description: Capture a raw idea instantly to the Inbox (append-only, any language, safe mid-work)
argument-hint: <text>
---
Capture a raw idea using the **Agile-Ledger Pro** skill.

Append `$ARGUMENTS` verbatim — in whatever language it was written — together with today's absolute date (`YYYY-MM-DD`) to the **💡 Inbox** in the resolved repo folder's `Ideas.md`.

Resolve the ledger first (the sibling **ledger repo**, then this repo's folder in it — `--repo <slug>` overrides); the file lives in `<ledger-root>/<repo-slug>/`, never in the code repo.

Rules: no ID, no deduplication, no rewriting, no questions. This must be instant and safe to run in the middle of other work. Re-read the file immediately before writing. If the repo's folder doesn't exist in the ledger yet, scaffold its eight files from the skill's reference templates first; if there is no ledger repo at all, say so and offer `/init-ledger` rather than guessing a location.
