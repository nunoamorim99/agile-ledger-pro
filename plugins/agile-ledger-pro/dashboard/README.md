# The Agile-Ledger Pro dashboard

A local web page that renders the whole ledger — ideas, epics, stories, bugs, the sprint board,
velocity, releases — grouped by project, and applies the same updates the slash commands do.

```
/dashboard                      # from Claude Code — finds the ledger, opens the browser
/dashboard --port 4200
/dashboard --ledger ~/Projetos/agile-ledger --no-browser
```

or directly:

```sh
python3 dashboard/serve.py --ledger ~/Projetos/agile-ledger
```

**Python 3.8+, standard library only.** Nothing to install, no build step, no network access. It
binds `127.0.0.1` and nothing else: there is no authentication and the ledger is the team's whole
product record, so it is never served to the network.

## How it treats your files

The ledger Markdown is the source of truth; this is a view onto it, not a second database.

- **Entries are the truth, tables are derived.** `SKILL.md` calls the overview tables and epic
  rollups "derived, never hand-typed", so they are recomputed from the entries on every write
  rather than edited in place. A stale hand-written total gets corrected the first time you save.
- **Edits are surgical.** The parser records the exact line span of every entry, and a write
  replaces only that span. Re-rendering every entry in a ledger without changing anything produces
  a byte-identical file (`tests/run_tests.py::test_rerender_is_byte_identical`), so a ledger diff
  only ever shows the change you actually made. Fields the dashboard does not model are carried
  through untouched.
- **Writes are atomic.** Each file is written to a temp file beside it and moved into place, so an
  interrupted write cannot leave a half-written ledger.
- **Nothing is deleted and no ID is reused.** Items move between sections and keep their row
  forever. The next free ID is the greater of the counter and the highest ID actually present, so
  a counter rewound by a bad hand-edit still cannot hand out an ID that is in use.
- **One writer at a time.** The server serialises writes, so two browser tabs cannot interleave.
- **Both placements work.** A ledger with its own repo (`layout: nested`) keeps one folder per code
  repo; a ledger living inside its one project (`layout: flat`) keeps the eight files at its root. The
  dashboard reads the shape off disk rather than trusting the config key, so a hand-moved folder still
  resolves, and the Overview says which placement you are in.
- **It reloads itself.** The page polls the files' modification times, so edits you make through
  Claude in the terminal show up within a couple of seconds. Avoid editing the same item in both
  places at once.

## What it can and cannot do

Everything that only touches the ledger files is available from the page: `/idea`, `/bug`,
`/triage`, `/triage-bug`, `/detail-us`, editing any story or bug, state changes, `/plan-sprint`,
the board moves (`/start-*`, `/review`, `/pr`), `/done-*`, `/close-sprint`, `/release`,
`/ledger-check`, and `/ledger-commit` (the selected repo folder only; it never pushes).

The **Commands** tab is the full sheet: every command the plugin ships, grouped by phase, with what
it does, which file it writes, and whether it runs here or in a Claude Code session. The rows are
generated from the installed `commands/*.md` frontmatter, so the sheet always matches your version
rather than a copy that goes stale. Each row copies its command on click; the ones the page can do
carry a button that opens the right form.

**Settings** is a screen of its own: everything the skill reads before it acts — this project's
`Definitions.md` (your name, language, estimation scale, whether git may run in the code repo) and
the ledger's `Config.md` (placement, default project, org, commit and push policy, branches) — plus
the team roster and the team's own Definition of Ready and Definition of Done. Saving writes the
same keys a person would type, and leaves the comments and alignment in those files exactly where
they were.

The **team roster** is the `## Team` table in `Config.md`: a name, a role and a GitHub handle per
person. Those are the names offered when you assign work — so you can assign a story to someone who
has none yet — and what `Me` is matched against, which is why a story filed under `@rita` shows up
as Rita and answers a filter for her.

A role in that roster is a **label, not a permission.** Everyone who can clone the ledger can read
and edit every file in it, this one included, and this server has no accounts — it is something you
run on your own machine against your own copy, and no role is checked before anything happens. To
actually require the Product Owner's approval before the Definition of Done or the estimation scale
changes, protect those files with `CODEOWNERS` and branch protection in the ledger repository; the
Settings screen shows you the file to use, built from the roster. Then the edit can still be made
but cannot land without a review — enforced by your git host, which is why it holds.

**It never runs git in a code repo.** `/sync-main`, `/workspace-sync`, `/discover-repos`,
`/register-repo`, `/init-ledger` and `/migrate-ledger` stay in the Claude Code session: they read
git history, clone repositories, and propose reconstructed work that needs a human's judgement.

Definition-of-Ready and Definition-of-Done gaps, and unmet dependencies, are reported as warnings
on the response rather than enforced — the dashboard tells you, you decide.

## Layout

```
dashboard/
├── serve.py              # HTTP server + CLI (the entry point)
├── agileledger/
│   ├── mdutil.py         # Markdown primitives: sections, tables, comment masking, spans
│   ├── model.py          # the ledger's vocabulary: states, emoji, ordering
│   ├── resolve.py        # ledger-root discovery, Registry.md and Config.md
│   ├── commands.py       # the command sheet: grouping + descriptions read from commands/*.md
│   ├── parse.py          # readers for the eight files (records a span per entry)
│   ├── render.py         # writers for entries and the derived tables
│   ├── store.py          # load, splice, rebuild derived data, write atomically
│   └── actions.py        # one function per command the dashboard exposes
├── static/               # index.html · style.css · app.js (vanilla, no libraries)
└── tests/
    ├── run_tests.py      # python3 tests/run_tests.py
    └── fixture/          # a small ledger exercising every shape
```

## Tests

```sh
python3 plugins/agile-ledger-pro/dashboard/tests/run_tests.py
```

No test runner needed. The load-bearing cases are `test_entries_round_trip` and
`test_rerender_is_byte_identical` — together they say that reading the ledger and writing it back
changes nothing, which is what makes every targeted edit safe. `test_templates_agree_with_the_model`
fails if the shipped templates drift from the vocabulary this code expects.

The fixture is deliberately left with a few wrong hand-written totals, so
`test_derived_tables_correct_stale_input` can prove a rebuild corrects them.

`test_command_sheet_covers_every_shipped_command` fails if a command is added without being placed
in `commands.SHEET`. It compares against the curated table rather than the rendered sheet on
purpose: the sheet files an unknown command under "Other", so checking the rendered output would
pass no matter what.

## Reading the ledger's own formatting

Story sentences, goals, notes and bug assessments are Markdown, so the page renders their inline
formatting — **bold**, *italic*, `code`, ~~struck~~ — instead of showing the asterisks, and an id
written inside prose (`[US-014](User-Stories.md#us-014)`) becomes a button that opens that entry.
Everything is built as DOM nodes, never `innerHTML`, because this is free text typed by people.

There is no underline: Markdown has none, and inventing a syntax for it would render as literal
punctuation in GitHub and VS Code preview, where the same ledger has to stay readable.

## Colour

Charts follow the data-viz reference palette: one categorical slot (blue) for the single-series
velocity chart — validated against both the light and dark surfaces — the reserved status palette
for state, and the documented chrome and ink tokens for everything else. State is never carried by
colour alone: every badge pairs its colour with the ledger's own glyph and word.
