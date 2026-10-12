---
description: Detail one User Story to Ready (As a/I want/So that + Gherkin AC + estimate + layer + deps)
argument-hint: <US-ID>
---
Using the **Agile-Ledger** skill, detail `$ARGUMENTS` to **✅ Ready**.

Fill: `As a <role>, I want <goal>, so that <benefit>`; acceptance criteria in Given / When / Then; a Fibonacci `Estimate`; the `Layer` (frontend / backend / fullstack); and `Dependencies` (as live links, e.g. `[US-009](User-Stories.md#us-009)`). Apply INVEST and flag any horizontal (FE/BE) slicing — prefer a vertical split. Move 📝 Draft → ✅ Ready only when the Definition of Ready in `Definitions.md` is met.

Write the full entry into **`User-Stories.md`** under `## ✅ Ready`, flip the story's index line under its epic in `Epic-Backlog.md` to **Ready**, and refresh the overview at the top of both files — roll-up counts **and** index tables, adding the story's row to `User-Stories.md` (it had none while it was a 📝 Draft).

Write the entry with a **bare-ID heading** (e.g. `#### US-014`) and the title on the line below, and render `Parent` and `Dependencies` as live links (e.g. `[EPIC-005](Epic-Backlog.md#epic-005)`) so the preview can jump to them.
