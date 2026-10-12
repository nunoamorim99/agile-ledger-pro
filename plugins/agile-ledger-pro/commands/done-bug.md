---
description: Mark a bug Fixed (In PR → Fixed), record into the Increment
argument-hint: <BUG-ID>
---
Using the **Agile-Ledger Pro** skill, move `$ARGUMENTS` In PR → **✅ Fixed**, gated by the fix being verified against the reproduction (the steps now pass and the expected outcome is restored). Move the entry to `## ✅ Fixed` in `Bugs.md` with a fix line (sprint · PR/commit · release), remove it from the `Sprint.md` board, add a line to the 🚧 Increment in `Releases.md` tagged **Fixed**, and refresh the overview at the top of `Bugs.md` (roll-up counts **and** the bug's row in the index table — the row moves to the Fixed group, it is never removed).
