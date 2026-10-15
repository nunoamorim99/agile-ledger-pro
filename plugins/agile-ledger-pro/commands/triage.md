---
description: Promote ideas from Ideas.md into Epics or User Stories in the Epic backlog (dedup, typed ID, voice)
---
Triage the Inbox using the **Agile-Ledger Pro** skill.

Resolve the ledger first — every file below lives in `<ledger-root>/<repo-slug>/`, never in the code repo (`--repo <slug>` targets another project).

For each idea in the resolved repo folder's `Ideas.md`:
1. Run duplicate detection across ALL files (four outcomes: exact / improved / related-distinct / new), including Paused and Discarded.
2. Decide whether it is an **Epic** or a **User Story** — same user goal as an existing epic → a new User Story under that epic; a new goal → a new epic, cross-linked `[EPIC-xxx](Epic-Backlog.md#epic-xxx)`.
3. Assign the next sequential typed ID (recompute from the highest existing ID of that type), and set `Parent`, priority, and area.
4. Rewrite it in the user's voice, in English.
5. Write it into `Epic-Backlog.md` and **move the line to `## ✅ Triaged` in `Ideas.md` with where it went**. Reconcile each `Next free ID`.
   - If the idea becomes a **new epic**, also propose a few **suggested 📝 Draft story-index lines** under it, derived from the epic goal. Present them for the user's confirmation — they are proposals, not truth.
   - If it maps to an **existing epic**, add it as a single **📝 Draft** story-index line under that epic.

Do not write acceptance criteria or estimates yet — that happens at `/detail-us` (there is no separate create-story step; stories are born here as Draft index lines and detailed later).
