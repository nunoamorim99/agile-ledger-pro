---
description: Plan a sprint — propose a Goal, pull Ready stories + high-priority bugs within velocity, build the board
---
Using the **Agile-Ledger** skill, plan the next sprint in the resolved repo folder's `Sprint.md` (`--repo <slug>` to plan another project's sprint).

Propose a **Sprint Goal**; pull top-ordered ✅ Ready stories whose points fit recent velocity (from `Sprints-History.md`); honour the dependency gate (do not pull a story with unfinished dependencies); optionally set an `Assignee` per story. Write the sprint header and board with each chosen story in **To Do** (referenced by ID). Confirm the selection with the user before committing it.

For each pulled story, move its entry in **`User-Stories.md`** from `## ✅ Ready` to `## 🏃 In Sprint`, set its epic index line to **In Sprint**, and refresh the overview at the top of both files (roll-up counts **and** each story's row in the index table).
