---
description: The numbers a PM steers by — velocity, reliability, forecast, bugs, flow, the ideas funnel — from the ledger as it is
argument-hint: [--repo <slug>]
allowed-tools: Read, Grep, Glob
---
Using the **Agile-Ledger Pro** skill, compute and print the project's insights report from the eight files. Read-only; nothing is written. The dashboard's **Insights** tab shows the same numbers — this is the version for a sprint review in the session, and the two must agree to the digit, so compute each the way `dashboard/agileledger/insights.py` does (its docstrings say how).

## What to report, in this order

1. **Delivery** *(Scrum)* — per closed sprint from `Sprints-History.md`: committed, completed, **reliability** (completed ÷ committed), carried over, pulled in after planning. Rolling velocity over the last three and its trend. *(Kanban)* — **throughput** (items and points per week over the last twelve weeks, from `Delivered:`/`Fixed:` dates) and **cycle time** instead; velocity is not a Kanban number and must not be the headline there.
2. **Forecast** — Ready points ÷ rolling velocity = sprints of runway, with a date only when the history gives a sprint length. Per epic with remaining points: sprints to land and an ETA, nearest first. With no velocity, say *no closed sprint yet* rather than guess.
3. **Quality** — bugs reported and fixed per month (from `Reported by (date)` and `Fixed:`), open by severity and priority, median age of open bugs, median time to fix, and the **escape rate**: bugs whose `relates to` is a delivered story, over delivered stories.
4. **Portfolio** — epics by derived state with progress in points; releases with dates, the median gap between them, days since the last, and how much is in the Increment unreleased.
5. **Team** — WIP per person now, and each person's share of delivered points. **Alphabetical, never ranked.** Say when one person carries half or more: that is a bus-factor and burnout signal, not an achievement. The skill promises the ledger is never a productivity leaderboard; this is where that promise is kept or broken.
6. **Backlog health** — stories at 8+ points (slice them), Ready stories failing the Definition of Ready and why, Draft count, ideas waiting and their median age, the unplanned share (bug points over all board points), blocked items.
7. **Flow** — from the dates the ledger has carried since `Ready:`/`Started:` were introduced: median and p85 **lead time** (Ready → Delivered) and **cycle time** (Started → Delivered), work in flight with its age, blocked items with days since the flag, and scope change (points `pulled` after planning over board points). Say how many stories carry the dates out of how many; a ledger that predates them reports *written from now on*, not zero.
8. **Ideas** — captured, promoted and discarded per month from the inbox and `## ✅ Triaged`, the promotion rate, and median days from capture to triage.

Keep it to the numbers and one sentence of reading per section — what the figure means for the next planning, not a narrative. Where a number cannot be computed, print the reason in its place; never estimate one. A PM makes decisions with this, so a guessed figure is worse than a missing one.
