---
description: (Ledger) Create the ledger repository — Registry + Config — the one-time setup
argument-hint: [path]
---
Using the **Agile-Ledger Workspace** skill, create the **ledger repository**: the separate repo that holds one folder per code repo, so code repos stay clean.

Place it at `$ARGUMENTS` if given; otherwise propose `./agile-ledger` when the cwd looks like a workspace root (a directory holding your code repos), and ask if it doesn't. Write `Registry.md` and `Config.md` from the `agile-ledger` skill's `references/` templates — keep `Registry.md`'s `# Agile-Ledger Registry` heading exactly as it is, since that heading is the marker the resolver looks for. Ask for the GitHub org/owner and the clone target and write them into `Config.md`.

Offer `git init` plus a first commit, and tell the user to create the remote and push it themselves. Do **not** scan, clone, or register anything — that is `/discover-repos` and `/register-repo`.

If a ledger root already exists at or above the cwd, report where it is and stop: one ledger per workspace. If the user has pre-2.0 `Agile-Ledger/` folders inside code repos, point them at `/migrate-ledger` next.
