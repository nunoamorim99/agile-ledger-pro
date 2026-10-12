---
description: Audit all ledger files for drift (report; fix only on request)
---
Using the **Agile-Ledger** skill, audit the resolved repo folder's eight files for drift: duplicate or mis-sequenced typed IDs, dangling `Parent`/dependency links, plus any ID link that doesn't resolve to an existing `#id` anchor, childless epics, a story on the board but missing under its epic (or vice versa), a board column not matching the story's recorded state, orphan Increment lines, and stale `Next free ID` counters. Report findings clearly; fix only on explicit request.

Also reconcile the two-file split: epic index line state vs. the story's group in **`User-Stories.md`**, a Ready+ story missing its index line (or vice versa), and a Draft story that wrongly has a detail entry.

Then verify the **overview index table** at the top of `Epic-Backlog.md`, `User-Stories.md`, and `Bugs.md` against the entries below it: every entry has exactly one row, no row points at a missing entry, each row's state / priority / estimate / assignee / title matches its entry, every ID link resolves to a real `#id` anchor, rows are in section order (active first, done last, highest priority first within a group), and the roll-up counts and points equal the rows they summarize.
