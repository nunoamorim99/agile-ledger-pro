---
description: Export user-facing release notes from the version history (derived, never edits the ledger)
allowed-tools: Read, Grep, Glob
---
Using the **Agile-Ledger Pro** skill, derive user-facing release notes / a `CHANGELOG.md` from the version history in `Releases.md`. This is derived output only — do not edit the ledger.

With a version (`/changelog v2.1`), print that version's **release notes** instead: the store block (plain text, `•` bullets, `New:` / `Improved:` / `Fixed:`, with its length against Google Play's 500 and the App Store's 4000 characters) and the team block (Markdown with item IDs), worded from each story's *I want … so that …* as `dashboard/agileledger/releasenotes.py` does. `/release` prints the same notes for the version it just cut.
