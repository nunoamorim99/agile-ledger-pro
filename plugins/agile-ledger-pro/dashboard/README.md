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
- **Edits are patches, not rewrites.** An existing entry is never regenerated from the template.
  The parser keeps each entry's own lines, and a write changes only the field or block whose value
  the action changed — an estimate edit changes the `Estimate:` line and nothing else, even though
  the edit form sends every field back. Untouched list items keep their own lines, wrapped and
  nested; the prose after a `Dependencies:` link stays; fields and blocks the dashboard has no name
  for are never touched. An epic is edited one line at a time: its derived title line (state and
  rollups) when a value on it moves, and the one index line of the story that changed. Its goal
  and notes are never rewritten. (Before 1.0.1 the dashboard re-rendered entries from its model and
  every epic after every action, which dropped exactly this kind of text.)
- **A save that would delete text is refused.** Before anything is written, the words of every
  changed file are counted before and after. Text that moved (a story changing section, the
  Increment rolling into a version) is not a loss, and neither is what the action said it was
  replacing — the old value of the field you edited, a derived table. Any other word going missing
  stops the save: nothing is written, and the page says what would have been lost. A bug in the
  writer shows up as a refused save, never as a deleted sentence.
- **`serve.py --verify` checks a ledger before you trust it.** Read-only, over every project: it
  writes each entry back unchanged (it must come out byte for byte), changes one field in memory
  and asks the guard, and runs a rebuild of the derived tables. Run it once on a ledger written by
  hand or by an older version; it exits non-zero and names the entries if any write would lose text.
- **It records when, not just what.** A story carries `Ready`, `Started` and `Delivered`; a bug
  `Triaged`, `Started` and `Fixed`; an epic `Created`; a board line pulled in after planning says
  `pulled <date>` and a blocked one `since <date>`. Each is written when it happens and never
  otherwise, so an entry from before these existed re-renders byte for byte. They are what lead
  time, cycle time, blocked time and scope change are computed from.
- **Writes are atomic.** Each file is written to a temp file beside it and moved into place, so an
  interrupted write cannot leave a half-written ledger.
- **Nothing is deleted and no ID is reused.** Items move between sections and keep their row
  forever. Ideas included: triage and discard move an idea to `## ✅ Triaged` in `Ideas.md` with where
  it went, which is what lets the funnel from idea to story be counted later. The next free ID is the greater of the counter and the highest ID actually present, so
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

**Release notes are ready the moment a release is cut.** Cutting a release opens its notes
straight away, and every version on the Ship tab has a **Release notes** button. Two boxes: **for
the stores**, plain text with `•` bullets under *New* / *Improved* / *Fixed* — the App Store and
Google Play do not render Markdown — with a live character count against Google Play's 500 and the
App Store's 4000; and **for the team**, Markdown with item IDs for a GitHub release or a changelog.
Each story is worded from its own *I want … so that …* ("You can now sign in with your Google
account, so you don't have to create another password"), each bug as *Fixed an issue where …*.
The text is editable before copying and never written back: it is derived, so it can be
regenerated any time, and `/release` prints the same notes in the session.

**Insights** is the report a Product Manager steers by, computed from the files on every visit and
never stored: per-sprint velocity with **reliability** (completed ÷ committed) and carry-over; a
**forecast** — Ready points over velocity gives sprints of runway, and each epic an ETA; bugs
reported against fixed per month, open age, time to fix and the escape rate; the epic portfolio and
release cadence; **workload distribution**; backlog smells; **flow** — lead and cycle time from the
`Ready:`/`Started:`/`Delivered:` dates, blocked days, scope pulled in mid-sprint — and the ideas
funnel. A Kanban project leads with throughput and cycle time instead of velocity. Two rules hold
throughout: a number the ledger cannot support yet is shown as the reason it cannot, never as a zero
that looks like a measurement; and the Team section lists people alphabetically and says when one
person is carrying half of everything — it is a distribution, never a ranking, because the skill
promises the ledger is not a productivity leaderboard. `/insights` prints the same report in the
session, to the digit.

**Scrum or Kanban, per project.** Each project's `Definitions.md` carries `methodology:` (default
`scrum`), so an organisation's Portal can run Kanban while its App runs Scrum, in one dashboard. The
eight files are the same under both; what changes is which numbers lead and which ceremonies the
page offers. Under Kanban the Sprint tab becomes a **Board** with no sprint to plan or close, each
column wears its count against the `wip_limits:` from Definitions.md — over the limit is shown in the
warning tone and never enforced, because a limit is advice the board makes visible — the pulse on
Today reports flow instead of a burndown, and Insights opens with throughput and cycle time. Settings
has a **Switch to …** card that shows what a switch would keep, need and suggest, every number with
its derivation: WIP limits from the people on the board; a Scrum velocity computed from Kanban
throughput over six sprint-length windows, windows shown; and the gaps — unestimated stories, nothing
delivered recently — named rather than filled. The switch itself is one key; reconstructing undetailed
ideas from git is `/switch-methodology`'s job in the session.

**Settings** is a screen of its own: everything the skill reads before it acts — this project's
`Definitions.md` (language, estimation scale, whether git may run in the code repo) and the ledger's
`Config.md` (placement, default project, org, commit and push policy, branches) — plus the team
roster, who you are, and the team's own Definition of Ready and Definition of Done. Saving writes the
same keys a person would type, and leaves the comments and alignment in those files exactly where
they were.

The **team roster** is the `## Team` table in `Config.md`: a name, a role and a GitHub handle per
person. Those are the names offered when you assign work — so you can assign a story to someone who
has none yet — and what `Me` is matched against, which is why a story filed under `@rita` shows up
as Rita and answers a filter for her.

**Who you are** is the one setting on that screen that is not the team's, so it has its own file:
`Me.local.md` at the ledger root, which `.gitignore` keeps out of git. It has to be separate. `Me:`
in `Definitions.md` is committed like every other line there, so one person's name reaches everyone
who clones the ledger and is overwritten by the next person to correct it — and once `Definitions.md`
is under `CODEOWNERS`, a developer cannot land that correction at all. The **You** card picks you off
the roster, writes the local file, and adds it to `.gitignore` the first time. The shared `Me:` is
still read when no local file exists, which is what a one-person ledger has always used; when both
exist the card says which one is winning. In a Claude Code session, `/whoami` does the same job and
can match you by your `gh` login.

**The rules go read-only for anyone who is not an owner.** If the roster names a `PO` or a `PM`,
Settings shows the ledger config, the estimation scale, the roster and the two checklists read-only
to everybody else, with a banner saying whose they are. The **You** card is never locked — your own
name is yours — and nothing is hidden: the Definition of Done is shown in full, because the people
who have to meet it need to read it. A ledger whose roster names no owner stays fully editable, so a
ledger with one person on it is unaffected, and an owner who has not yet run `/whoami` on that
machine sees the read-only view until they pick themselves in the You card.

**Backlog and ceremony buttons are hidden from people the roster does not give them to.** Triage,
discarding or capturing an idea, **writing a Draft up** (the `Write up` button), moving a story to
an epic, planning and closing the sprint and cutting a release belong to the `PO`/`PM` — and the
sprint ceremony to the `SM` as well. Everything a developer does is untouched: the board, reporting
a bug, **editing** a story that exists and its estimate, the blocked flag, committing the ledger,
and saying who they are.

The write-up and the edit sit on opposite sides of that line on purpose. Writing a Draft up means
writing the story sentence and the acceptance criteria against the Definition of Ready, which is the
Product Owner's job; editing a story afterwards is where the estimate lives, and the estimate is the
developer's. A Draft page a developer opens says who writes it up rather than just missing a button. `model.ACTION_ROLES` is the whole
list, one line per action, and deleting a line opens that action back up to the team.

Nothing is hidden that someone needs to read. The idea inbox still lists every idea, so a developer
sees what is coming; the **Commands** sheet still lists every command, with a line saying whose it
is rather than a gap where it used to be. The "Needs you" lens does drop findings whose only answer
is an action you may not run — being told the inbox needs triaging when you may not triage is worse
than not being told.

Be clear with your team about what that is: a **guardrail against the accidental edit**, which is
most unwanted edits, and nothing more. The person reading it starts this server themselves, against
their own clone, and `Me.local.md` — the file it asks who they are — is a text file they own. They
can say they are the Product Owner, open `Config.md` in an editor, or POST to the action endpoint.
It is not a boundary and the screen says so. The slash commands do not check at all: `/triage` run
by a developer in a Claude Code session says whose call it is and then does it, the same way a
Definition-of-Ready gap is reported rather than enforced.

Until somebody picks themselves in the You card, the dashboard does not know which of the team they
are, so the restricted buttons stay hidden — including from the Product Owner. **Today** says so in
a card with a button straight to Settings, because buttons that are simply missing look like a
broken page.

A role in that roster is a **label, not a permission.** Everyone who can clone the ledger can read
and edit every file in it, this one included, and this server has no accounts — it is something you
run on your own machine against your own copy. The read-only view above is the only thing that reads
a role, and it is a guardrail rather than a check that could hold. To actually require the Product
Owner's approval before the Definition of Done or the estimation scale
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
│   ├── store.py          # load, splice, rebuild derived data, guard, write atomically
│   ├── actions.py        # one function per command the dashboard exposes
│   └── verify.py         # serve.py --verify: the read-only write-safety check
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
changes nothing, which is what makes every targeted edit safe. The fixture alone is too tidy to
prove that, so `test_hand_written_text_survives_every_action` plants entries written the way
people write without a tool watching — criteria wrapped over lines with a nested bullet, prose
after a dependency, a multi-line epic goal and notes, a note on an index line and on a board card,
an epic outside `## Epics`, a combined Paused / Discarded section — and runs the actions over them,
checking that every hand-written phrase is still there afterwards.
`test_a_lossy_write_is_refused_and_nothing_is_saved` writes an entry the old way on purpose and
expects the guard to refuse it. `test_templates_agree_with_the_model`
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
