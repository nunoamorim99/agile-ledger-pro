---
description: Open the local Agile-Ledger Pro dashboard in a browser (read and update the ledger from a page)
allowed-tools: Read, Grep, Glob, Bash(python3:*), Bash(python:*), Bash(py:*)
---
Start the **Agile-Ledger Pro dashboard**: a local web page that renders the whole ledger — ideas, epics, stories, bugs, the sprint board, velocity, releases — grouped by project, and can apply the same updates the slash commands do.

Arguments in `$ARGUMENTS` are passed straight through (`--port 4200`, `--no-browser`, `--ledger <path>`).

1. **Find the server.** It ships inside this plugin at `${CLAUDE_PLUGIN_ROOT}/dashboard/serve.py`. If that variable is not set (a manual `.claude/` install rather than a marketplace one), look for `dashboard/serve.py` next to the `skills/` folder you were loaded from, then under `~/.claude/` and `./.claude/`. Say which copy you are starting.

2. **Pick the interpreter.** Try `python3`, then `python`, then `py -3`. It needs Python **3.8+** and no packages at all. If none is available, say so plainly, point at <https://python.org/downloads>, and stop — do not try to install anything.

3. **Resolve the ledger.** With no `--ledger`, the server applies the same resolution rule as the skill: it walks up from the current directory for a `Registry.md` whose first heading is `# Agile-Ledger Registry`, then checks that directory's children. Run it from the workspace root or from inside a code repo. If it reports no ledger, run `/init-ledger` first.

4. **Run it in the background** so the session stays usable, then report the URL (`http://127.0.0.1:4173/` by default), the ledger path, and the repos it found. The server binds **127.0.0.1 only** — it has no authentication and the ledger is the team's whole product record, so it is never exposed on the network. If the port is taken, it says so; re-run with `--port`.

5. **Tell the user how to stop it** — Ctrl+C in that process, or ask you to stop the background task.

## What the dashboard can do

Read-only views for every ledger file, plus the write actions matching `/idea`, `/bug`, `/triage`, `/triage-bug`, `/detail-us`, `/plan-sprint`, `/start-*`, `/review`, `/pr`, `/done-*`, `/close-sprint`, `/release` and `/ledger-commit`. It applies the same rules this skill does: nothing is deleted, IDs are never reused, overview tables and epic rollups are rebuilt from the entries, and a state change updates the entry, its epic index line and the board together. Definition-of-Ready and Definition-of-Done gaps and unmet dependencies are reported as warnings for the human to judge, not silently enforced.

**It does not run git in a code repo.** `/sync-main`, `/workspace-sync`, `/discover-repos`, `/register-repo`, `/init-ledger` and `/migrate-ledger` stay here in the session, because they read git history, clone, and propose reconstructed work that needs your judgement. `/ledger-commit` is available from the page (it commits the selected repo folder in the ledger repo, and never pushes).

The page polls the ledger files and reloads when they change, so updates you make here in the session appear in the browser within a couple of seconds, and vice versa — but tell the user to avoid editing the same item in both places at once.
