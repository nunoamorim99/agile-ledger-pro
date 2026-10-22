# README image assets

Drop the Higgsfield-generated images here with these exact filenames so the README picks them up:

| File | Used in | Suggested prompt theme |
|---|---|---|
| `logo/agile-ledger-pro-horizontal-color-{dark,light}.svg` | top of README | the suite logo lockup (not Higgsfield — from the suite logo pack); GitHub picks the one matching the reader's theme |
| `cover.png` | GitHub social preview only (no longer in the README) | hero banner for the whole skill — calm, organized, plain-Markdown command center |
| `group-capture.png` | LinkedIn / optional README | capturing ideas & bugs (green) |
| `group-triage.png` | LinkedIn / optional README | sorting inbox into epics/stories (green) |
| `group-backlog.png` | LinkedIn / optional README | shaping detailed user stories (blue) |
| `group-sprint.png` | LinkedIn / optional README | a kanban board in motion (amber) |
| `group-inspect.png` | LinkedIn / optional README | dashboards & status views (purple) |
| `group-release.png` | LinkedIn / optional README | shipping a release (red) |
| `group-workspace.png` | LinkedIn / optional README | the ledger repo + many managed repos (gray) |
| `groups.png` | optional README strip | the 7 group images composited side by side |

All generated with Higgsfield. Keep a consistent palette: green=capture/triage, blue=backlog,
amber=sprint, purple=inspect, red=release, gray=workspace.

## Pro rebrand status

These images carried over from Agile-Ledger. Those that render text still show the **old** wordmark and
need regenerating before the first public Pro release; the rest are text-free and reuse as they are.

| File | Carries text? | Status |
|---|---|---|
| `cover.png` | yes — the "Agile-Ledger" wordmark | **regenerate** as "Agile-Ledger Pro" |
| `flow.png` | yes — "How work flows through Agile-Ledger" | **regenerate**; the Mermaid source in the README is already correct |
| `files.png` | yes — "plain Markdown inside `Agile-Ledger/`" | **regenerate**; that path is also stale since v2.0 — it should read `<ledger-root>/<repo-slug>/` |
| `group-*.png` (7) | no | reuse as-is |

`Agile-Ledger-Pro-cheatsheet.pdf` at the repo root is in the same position: the filename is updated, the
artwork inside still says "Agile-Ledger".
