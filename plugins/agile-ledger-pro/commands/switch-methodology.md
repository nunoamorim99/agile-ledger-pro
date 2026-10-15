---
description: (Ledger) Move this project between Scrum and Kanban without losing the backlog, the history or a date — derived numbers, confirmed first
argument-hint: <scrum|kanban> [--repo <slug>]
---
Using the **Agile-Ledger Pro Workspace** skill, switch this project's methodology to `$ARGUMENTS`. This is a **proposal first, then a write**: everything below is shown and confirmed before `Definitions.md` changes. Heavy by design — it reads the whole ledger and may reconstruct from git — and safe to abandon at any point before the confirmation.

## What never changes

The eight files are the same under both methodologies. Say so first, because it is the reason the switch loses nothing: every epic, story and bug keeps its state; the board keeps what is on it; `Sprints-History.md` is kept untouched (history is never deleted — under Kanban it becomes a record, not a headline); `Releases.md`, the roster, the rules, and every `Ready:`/`Started:`/`Delivered:` date stay exactly where they are. What changes is which numbers lead and which ceremonies the commands run.

## 1. Assess — the same arithmetic as the dashboard

Compute what `dashboard/agileledger/insights.py::transition` computes, so the session and the Settings screen propose the same figures:

**Scrum → Kanban**
- If a sprint is open, it is **closed first** with `/close-sprint`, so its velocity is recorded; the board itself is left as it is.
- Propose **WIP limits** per column: In Progress = the number of people on the board (one each, the textbook start) or the count there now if higher; In Review and In PR from today's counts, at least 1. Show the counts the numbers came from.
- Say what becomes the headline: throughput and cycle time, from the dates the ledger already carries.

**Kanban → Scrum**
- Propose a **sprint length** from the old history's typical length, or 14 days.
- Derive a **velocity from throughput**: points delivered per sprint-length window over the last six windows, from `Delivered:`/`Fixed:` dates, averaged over the windows that had work. **Print the windows** so the number can be argued with. If no window has work, say no velocity can be derived and that the first sprint is planned by count, with the real velocity recorded at close.
- Count Ready stories **without an estimate**. Kanban teams often never estimated; Scrum planning needs points. Offer an estimation pass (`/refine`) or planning by count for the first sprint. Never invent an estimate.
- Say what the first sprint needs: a start day, and `/plan-sprint` using the derived velocity as capacity.

## 2. Reconstruct what Kanban left undetailed — proposals only

A Kanban team pulls work straight from ideas and drafts, so the backlog may hold ideas never triaged and Drafts never written up while the code moved on. For each, **propose** — never assert — what it became, following `references/reconstruction-guide.md`: mine the code repo's history for commits and PRs that match, and draft the epic or story as `🔍 reconstructed from git — needs review`, with value left as `?? (confirm)` and no acceptance criteria, estimate or state invented. Present the proposals for confirmation. This is the heavy part; skip it on request, and skip it entirely when `git_execution` is `off` and the repo cannot be read.

## 3. Confirm, then write

Show the whole plan — what is kept, what is suggested with its derivation, what is still missing — and **wait**. On confirmation:

- Set `methodology:` in the project's `Definitions.md`; for Kanban also write `wip_limits:` (`In Progress 3 · In Review 2`).
- Close the open sprint if moving to Kanban (already confirmed above).
- Write the confirmed reconstructed drafts into `Ideas.md` / `Epic-Backlog.md`.
- Commit in the ledger repo per `ledger_commit` (`ledger(<slug>): switch to kanban`).

Report what was kept, what was derived and from what, and what the team still has to decide. Never claim a velocity exists that was not computed from delivered work, and never say the switch is "complete" while a gap in step 1 is unresolved — say which one.
