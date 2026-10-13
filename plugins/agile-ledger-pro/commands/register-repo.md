---
description: (Ledger) Register a code repo into the ledger — its folder + the eight files + a Registry row
argument-hint: <path | remote> [--from-git]
---
Using the **Agile-Ledger Pro Workspace** skill, register the repository at `$ARGUMENTS` into the ledger repo.

1. Resolve it: a local path, or a remote to clone into `clone_target` — **propose the clone and wait for confirmation** before downloading anything.
2. Derive the folder slug (lowercase-hyphenated repo name). If that slug is taken, ask rather than overwrite.
3. Create `<ledger-root>/<slug>/` and scaffold the eight ledger files from the `agile-ledger-pro` skill's `references/*.template.md` — **only if absent**; if the folder already exists, report and stop.
4. Add a row to `Registry.md`: slug, code path, normalized remote (no scheme, no credentials, no trailing `.git`), status `active`, no sync SHA yet. Never overwrite an existing row.
5. With `--from-git`, mine the repo's history and **propose** reconstructed epics/stories as drafts in that folder's `Ideas.md`, each flagged `🔍 reconstructed from git`, following `references/reconstruction-guide.md` — no invented value or acceptance criteria, Inbox-only, the human triages.
6. Commit in the ledger repo per `ledger_commit` (`ledger(<slug>): register repo`). Push only on confirmation.

**Write nothing outside the ledger root** — not a ledger file, not a config file, not a marker. In a `nested` ledger that means nothing at all goes into the code repo; the resolver finds the ledger by walking up from the code repo to the sibling ledger root.

In a **`flat`** ledger there is nothing to register: it holds exactly one project, scaffolded by `/init-ledger`. Asked to add a second project to one, explain that and offer the two real choices — move the ledger out into its own repository so it can hold several, or give the other project its own flat ledger. Never reshape the folder silently.
