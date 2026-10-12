---
description: Mark a story Done (In PR → Done), gated by DoD + acceptance criteria
argument-hint: <US-ID>
---
Using the **Agile-Ledger** skill, move `$ARGUMENTS` In PR → **Done**, gated by the Definition of Done and all acceptance criteria checked. Update the story's full entry under its epic (delivery line with sprint + PR/commit) and add a line to the 🚧 Increment in `Releases.md`. If the parent epic was previously Done, this re-opens it (derived status); when the epic next returns to Done, close a new epic version (`vN`).

Move the story's entry in **`User-Stories.md`** from `## 🏃 In Sprint` to `## ✅ Delivered`, set its epic index line to **Delivered**, remove it from the `Sprint.md` board, and refresh the overview at the top of both files (roll-up counts **and** the story's row in the index table — the row moves to the Delivered group, it is never removed).
