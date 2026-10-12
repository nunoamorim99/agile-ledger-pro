---
description: Read-only investigation of a bug — reproduce, locate the cause, fill the detail
argument-hint: <BUG-ID>
allowed-tools: Read, Grep, Glob, Edit
---
Using the **Agile-Ledger** skill, investigate `$ARGUMENTS`. This is **read-only**: locate and report, never edit code.

Try to reproduce the bug and find its cause, then fill, in the `Bugs.md` entry: **steps to reproduce**, **expected** vs **actual** outcome, and the **assessment** (suspected root cause / files).

Honesty guardrail — fill a field only if you can **confirm it from the code** (mark `confirmed`) or the **reporter supplied it** (mark `reported`). If you cannot verify something, mark it `unconfirmed — needs input` and ask the reporter; never invent a reproduction or a root cause. On a successful assessment, move the bug 🔍 Triaged → 🔬 Confirmed and refresh the overview at the top of the file (roll-up counts **and** the bug's row in the index table).
