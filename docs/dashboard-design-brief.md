# Agile-Ledger Pro — dashboard design brief

**For:** a designer proposing the front-end and information architecture for the dashboard.
**Status of the thing being designed:** working, tested, unstyled-by-a-designer. Every behaviour
described here exists and runs today; 550 automated checks cover the data layer. What it has never
had is a design pass.

**What we want back:** a proposal for the screens, the information architecture, and the visual
system — not a code change. Tell us what the portal should be, not just how it should look.

---

## 1. What the product is

Agile-Ledger Pro is a Scrum/Agile product-management system for **Claude Code** (a terminal AI
coding agent). Its distinguishing idea: **the entire backlog is plain Markdown files in a git repo.**
No database, no SaaS, no Jira. A product manager runs the whole lifecycle — idea → backlog → sprint
→ release, plus bug tracking — from 34 slash commands typed at Claude, and the result is eight
Markdown files a developer can read in GitHub without learning anything.

The dashboard is the newest piece. It serves those same files as a local web page, so people can
*read* the backlog without opening eight Markdown files, and *act* on it without memorising
commands. It is launched with `/dashboard`, runs on `127.0.0.1`, and is the thing you are designing.

### Why this matters to the design

The files are the product. The dashboard is a **lens onto them**, never a separate database. Two
consequences you should design around:

1. **Everything shown is already text somewhere.** Nothing is computed-and-stored; totals are
   derived on read. A user can edit the Markdown by hand, and the page picks it up within seconds.
2. **The vocabulary is fixed by the file format.** States, emoji and field names come from the
   ledger spec. You can restyle how a state looks, but "✅ Ready" and "🏃 In Sprint" are the
   system's actual words, and they appear in the files themselves.

---

## 2. Who uses it

| Persona | What they open it for | Today's experience |
|---|---|---|
| **PM / PO** (the author, daily) | Is the sprint on track? What's blocked? What do I triage next? Is the backlog ready for planning? | Has to assemble the answer across Overview, Board and Stories |
| **Developer** (a few times a day) | What's assigned to me? What's next? Is my story's acceptance criteria complete? What branch do I use? | A single "Person" dropdown filter; no personal view |
| **Stakeholder** (occasional) | What shipped? What's coming? | Releases tab is a flat list; no narrative |

The PM is the primary user and the one whose job the page should make obviously faster. The
developer case is currently the weakest.

---

## 3. Hard constraints

These are not negotiable without a conversation — they come from the product's promises.

| Constraint | Why |
|---|---|
| **No build step, no npm, no frameworks.** Vanilla HTML/CSS/JS, served by a stdlib Python server. | The plugin advertises "dependencies: none". A user runs `/dashboard` and it works. |
| **No CDN, no external fonts or scripts.** | It must work offline, on a plane, behind a corporate proxy. |
| **Local only** (`127.0.0.1`), single user, no auth, no accounts. | It reads a private backlog. There is no login to design. |
| **Light and dark themes, both first-class.** | Developers live in dark mode. There's a 3-way toggle (auto/light/dark). |
| **System font stack.** | No webfonts (see no-CDN). |
| **Ledger prose is user text.** Rendered as DOM nodes, never `innerHTML`. | It is free text typed by people; no markup injection. |
| **Must stay usable at phone width.** | PMs check the board on a phone. Currently the board stacks to one column; the rest is untested. |

Colour currently follows a validated data-viz palette (one blue series for charts; a reserved
status palette of good/warning/serious/critical). **You may replace it** — but any categorical
chart palette must pass a colourblind-separation check, and status must never be carried by colour
alone.

---

## 4. The domain model

Five entity types. Understanding the state machines is most of understanding the product.

### 4.1 Idea → Story → Sprint

```
💡 Idea (no ID)  →  📝 Draft  →  ✅ Ready  →  🏃 In Sprint  →  ✅ Delivered
   Ideas.md         epic index    full entry    on the board      shipped
                                                      ↓
                                        To Do → In Progress → In Review → In PR → Done
```

A story has **two states at once** while it's in a sprint: a coarse lifecycle state
(`In Sprint`) and a fine board column (`In Review`). Designers consistently miss this. The board
column only exists during a sprint; the lifecycle state is permanent.

A **📝 Draft** story is special: it exists *only* as a one-line index entry under its epic, with no
detail record anywhere. There is nothing to open. It is the "we know we want this, we haven't
written it up" state, and it is very common.

### 4.2 The entities

| Entity | ID | Lives in | States |
|---|---|---|---|
| **Idea** | none | `Ideas.md` | inbox only — triage promotes or discards it |
| **Epic** | `EPIC-001` | `Epic-Backlog.md` | 💡 Proposed · 🔨 In Progress · ✅ Done · ❄️ Paused · 🗑️ Discarded *(derived from its stories, never set by hand)* |
| **User Story** | `US-014` | `User-Stories.md` | 📝 Draft · ✅ Ready · 🏃 In Sprint · ✅ Delivered · ❄️ Paused · 🗑️ Discarded |
| **Bug** | `BUG-003` | `Bugs.md` | 🐛 Inbox · 🔍 Triaged · 🔬 Confirmed · 🛠️ In Sprint · ✅ Fixed · ❄️ Deferred · 🚫 Won't fix |
| **Sprint** | `2026-S04` | `Sprint.md` (current), `Sprints-History.md` (closed) | open / closed |
| **Release** | `v2.1` | `Releases.md` | Increment (done, unreleased) → numbered version |

Bugs are a **parallel track**: their own file and triage flow, their own severity axis — but they
share the sprint board with stories and move through the same five columns.

### 4.3 Field inventory

What we actually hold for each entity. Fields marked **unused** are parsed but shown nowhere —
see §9.

**Story:** `id · title · state · parent (epic) · priority (🔴🟡🟢) · estimate (Fibonacci 1-21) ·
area · layer (frontend/backend/fullstack/infra/design/docs) · assignee · story` (the
As-a/I-want/So-that sentence) `· criteria` (a list of Given/When/Then lines) `· criteria_met ·
dependencies` (other story IDs) `· delivered` (date · sprint · PR · release) `· notes · reason`
(when paused/discarded)

**Bug:** `id · title · state · severity (critical/major/minor/trivial) · priority · estimate ·
reported_by · area · assignee · relates_to` (a story) `· symptom · steps` (numbered) `·
steps_confidence` (confirmed / unconfirmed) `· expected · actual · assessment ·
assessment_confidence · fixed · notes`

**Epic:** `id · title · state · target` (a version like `v2.0`) `· area · goal · history` (a list of
dated version lines) `· stories` (index entries) `· rollup` (`{stories_done, stories_total,
points_done, points_total}`)

**Sprint (current):** `name · goal · dates · capacity · last_sync` **(unused)** `· board`
(5 columns of items) `· blocked` (id, title, reason) `· sync_log` **(unused)**

**Closed sprint:** `name · title` (theme) `· start · end · goal · committed · completed · velocity ·
delivered` (ids) `· carried` (ids)

**Release:** `version · title · date · theme · stories · epics` — plus the Increment, a list of
done-but-unreleased lines.

**Definitions:** `config` (language, estimation scale, "Me") `· definition_of_ready` **(unused)** `·
definition_of_done` **(unused)** — the team's own checklists.

---

## 5. Current information architecture

A fixed top bar, a row of 10 tabs, one scrolling panel. **The tabs mirror the eight Markdown files.**
That is the central thing to interrogate: it is an IA inherited from the storage format, not
designed around what anyone is trying to do.

| Tab | Badge count | What it answers today |
|---|---|---|
| **Overview** | — | "How are we doing?" |
| **Board** | items on the board | "What's moving?" |
| **Inbox** | ideas + untriaged bugs | "What's waiting for me to sort?" |
| **Epics** | epic count | "How big is each theme and how far along?" |
| **Stories** | detailed stories | "What's in the backlog?" |
| **Bugs** | open bugs | "What's broken?" |
| **Sprints** | — | "How fast do we go?" |
| **Releases** | increment size | "What shipped, what's pending?" |
| **Files** | — | "Show me the raw Markdown" |
| **Commands** | — | "What can this thing do?" |

### 5.1 Overview

1. **KPI row** — 6 tiles: Ready to build (count + points waiting) · In this sprint (count + sprint
   name) · Blocked (count) · Open bugs (count + untriaged) · Unreleased (increment size) · Ideas
   waiting.
2. **Current sprint card** *(only when a sprint is open)* — name, dates, the goal as formatted
   prose, and a row of per-column count badges.
3. **Velocity chart** — a column chart of completed points per closed sprint. Short axis labels
   (`S01`…`S12`), thinning to every Nth when crowded; full name, theme, dates, velocity, committed
   and goal on hover.
4. **"<Person>'s sprint work"** *(only when the Person filter is set)* — a story table.

### 5.2 Board

Header: sprint name, goal · dates · capacity, **Plan sprint** and **Close sprint** buttons.

Five columns — To Do, In Progress, In Review, In PR, Done — each with a count and point total.
Cards show ID, title, assignee, points, and a 🚧 Blocked badge. **Cards drag between columns**;
dropping on Done opens a form asking for the PR and commit. Clicking a card opens the detail drawer.

Below: a **🚧 Blocked** list — one card per blocked item with the ID, title, and the reason under a
"Blocked by" label, plus an Unblock button.

Empty state when no sprint is open, pointing at "Plan sprint".

### 5.3 Inbox

Two stacked lists. **Ideas** — date, the text as formatted prose, and three actions: *→ Epic*,
*→ Story*, *Discard*. **Bug reports** — date, text, and *Triage*. Each has a capture button
(**New idea**, **Report bug**).

### 5.4 Epics

A card per epic: ID, derived state badge, target-version badge, area badge, title, goal as prose,
**two progress meters** (stories done/total, points done/total), then a table of its stories
(ID · Title · State · Pri · Pts · Assignee) where each row either *Opens* the detail or offers
*Detail* if it's still a Draft. A "History" list of dated version lines if present.

### 5.5 Stories

A **📝 Draft** section first (items that exist only as epic index lines, each with a *Detail*
button), then one section per lifecycle state — each with a count, a point total, and a table
(ID · Title · State · Pri · Pts · Epic · Assignee). Clicking a row opens the drawer.

### 5.6 Bugs

One section per bug state, each a table (ID · Title · Sev · Pri · Relates to · Assignee).

### 5.7 Sprints

Rolling-velocity figure, the velocity chart again, then a history table: Sprint (name + theme) ·
Start · End · Goal · Committed · Completed · Velocity · Delivered (ID chips) · Carried over (ID
chips).

### 5.8 Releases

The **Increment** (done, not yet released) as a list, with a **Cut release** button. Then version
history: version, date, title, theme, and the story/epic IDs included.

### 5.9 Files

A button per ledger file; clicking shows the raw Markdown in a `<pre>`. Plus **Run ledger check**,
an audit that reports drift (broken links, orphans, state mismatches) as a toast list.

### 5.10 Commands

All 35 commands in 7 phase groups, with a filter box. Each row: the command (click to copy), what
it does, which file it writes, and where it runs — **Do it here** (opens the matching form),
**Open tab** (jumps to the equivalent view), or **In Claude Code** with a one-line reason.

---

## 6. Global chrome and interaction patterns

**Top bar:** product name · **Project** select (switches repo) · **Person** select (filters every
view by assignee) · ledger path · **Commit ledger** button · theme toggle (auto/light/dark).

**Detail drawer** — slides from the right for a story or bug. Shows state/priority/epic badges, the
title, a key-value block, then prose sections (story, acceptance criteria, reason, notes; or
symptom, steps, expected, actual, assessment). Footer: **Edit**, **Copy branch name**, and a button
per state transition (`→ Ready`, `→ Delivered`, …). It is the **only** detail surface; there is no
per-item URL.

**Modal** — every create/edit form. Title, fields, a note line, Cancel/Save.

**Toasts** — bottom-right, three tones: success, warning (carries a list — e.g. unmet Definition of
Ready), error. Auto-dismiss.

**Banner** — persistent, above the view, when the ledger folder predates the current format.

**Live reload** — the page polls file modification times every 2.5s. If Claude edits the ledger in
the terminal, the page reloads itself and toasts "Ledger reloaded". This is a real and important
behaviour: **two agents edit the same files.**

**Markdown in prose** — bold, italic, `code`, ~~struck~~ render inline; an ID inside prose becomes
a button that opens that entry.

---

## 7. Write actions

Nineteen actions. Every one re-reads and returns the whole repo, so the UI always reflects disk.

| Action | Triggered from | Form fields |
|---|---|---|
| `add_idea` | Inbox · Commands | text |
| `add_bug` | Inbox · Bugs · Commands | text |
| `discard_idea` | Inbox | confirm only |
| `triage_idea_to_epic` | Inbox | title, goal, area, target |
| `triage_idea_to_story` | Inbox | title, parent epic, priority |
| `triage_bug` | Inbox | title, severity, priority, area, reported by, relates to |
| `detail_story` | Stories · Epics | title, story, criteria (multi-line), priority, estimate, layer, area, assignee, dependencies |
| `update_story` | Drawer | all story fields |
| `set_story_state` | Drawer | state (+ reason when pausing/discarding) |
| `update_bug` | Drawer | all bug fields |
| `set_bug_state` | Drawer | state |
| `plan_sprint` | Board | name, dates, capacity, goal, **multi-select of pullable items with a running point total** |
| `move_board_item` | Board (drag or drawer) | — |
| `set_blocked` | Board | reason |
| `complete_item` | Board (drop on Done) | PR, commit |
| `close_sprint` | Board | retro kept, retro try |
| `cut_release` | Releases | version, title, theme |
| `commit` | Top bar | message (shows the changed-file list) |
| `check` | Files · Commands | — (read-only audit) |

**Warnings, not blocks.** Definition-of-Ready gaps, unmet dependencies and missing acceptance
criteria are *reported* on the response and shown in a toast. The page never refuses the action.
This is deliberate — the human decides — and it deserves better design than a disappearing toast.

---

## 8. States and edge cases to design for

| State | When | Today |
|---|---|---|
| No sprint open | Between sprints | Empty panel + "Plan sprint" |
| Empty backlog | Fresh ledger | Per-section empty text |
| Draft with no detail | Very common | A list row with a *Detail* button |
| Blocked item | Dependency or external wait | Badge on the card + a list below the board |
| Pre-2.0 ledger | Old folder relocated | Persistent red-edged banner with the detected era and a copy-the-command button |
| Missing ledger files | Partial folder | Same banner, warning tone |
| Unregistered project folder | On disk, not in the registry | Listed, marked `unregistered` |
| No ledger found | First run | Server refuses to start, prints guidance |
| Ledger changed on disk | Claude edits while the page is open | Auto-reload + toast |
| Action rejected | Bad input, missing entry | Error toast with the server's message |
| Action warned | DoR/DoD gaps | Warning toast with a list |
| Not a git repo | Ledger not under git | Commit button reports it |
| Long lists | 40+ sprints, 100+ stories | Chart thins labels; tables just grow |

---

## 9. Verified gaps — data we hold and never show

These are parsed, available in the API, and displayed **nowhere**. Each is a design opportunity
that costs no new plumbing.

| Data | Where it comes from | Why it matters |
|---|---|---|
| **Definition of Done** and **Definition of Ready** | `Definitions.md`, fully parsed | The team's own checklists. A developer moving a story to Done should see the DoD; a PM detailing a story should see the DoR. Currently visible only as raw Markdown in the Files tab. |
| **Sprint sync log** and **last main sync** | `Sprint.md` | A record of what merged and when — the raw material for an activity feed. |
| **Story dependencies** | parsed into a list | Shown as a comma-separated line in the drawer. Never visualised, never used to show what a blocked item is waiting on, even though the data forms a graph. |
| **Epic target version** | parsed | A badge only. There is no roadmap view grouping epics by the version they're aimed at — despite `/roadmap` being an advertised command. |
| **Retro notes** | present in `Sprints-History.md` | **Not even parsed.** Would need a small parser change. |
| **Bug confidence flags** | `steps_confidence`, `assessment_confidence` | Whether a bug's reproduction is confirmed or still guesswork. Buried in a heading. |
| **Area** (a free-text grouping on stories, bugs and epics) | parsed | A badge only. No grouping, filtering or rollup by area. |

---

## 10. Assessment — where design effort pays, ranked

My honest read, having built it. Highest leverage first.

### 1. The IA is storage-shaped, not job-shaped *(biggest win)*
Ten tabs that mirror eight files. Nobody's job is "look at Epic-Backlog.md". The PM's real
questions — *what needs me today, what's at risk, is the next sprint ready* — are answered by
assembling three tabs by hand. The developer's question — *what's mine and what's next* — has only
a dropdown filter. **Propose an IA organised around decisions, not files.** The files can stay
reachable without being the navigation.

### 2. There is no personal view
A developer opens this to find their work and the detail needed to start: acceptance criteria, the
branch name, the dependency state, the DoD. All of that exists; none of it is assembled. The Person
filter is a single-select dropdown in a crowded top bar and is easy to miss entirely.

### 3. Warnings are ephemeral
The system does quality checks — Definition of Ready, unmet dependencies, drift — and shows them in
a toast that disappears in five seconds. There is no "what's wrong with my backlog" surface, even
though `check` produces a full audit on demand. A standing health view would make the whole product
feel trustworthy.

### 4. No search, no deep links
There's no way to find `US-014` without knowing which tab and scrolling. No per-item URL, so nothing
is linkable or shareable, and the browser back button does nothing useful. The detail drawer is the
only way in.

### 5. Density and scale are unconsidered
Tables are fixed-density and just grow. Fine at 20 stories, unusable at 300. No pagination, no
virtual scroll, no compact mode, no column choice, no sort, no multi-select, no bulk edit.

### 6. The board is thin
Drag-and-drop works, but: no swimlanes (by assignee or epic), no WIP-limit signal against the
sprint's capacity, blocked items sit in a separate list below rather than reading as blocked in
place, and there's no sense of *time* — no burndown, no days remaining, despite having the dates.

### 7. Relationships are invisible
Epic → stories → bugs-relating-to-them → dependencies form a real graph, and it is rendered as flat
lists and comma-separated IDs. The product's own pitch is "the join key travels through everything",
and the UI shows none of that travel.

### 8. Mobile is unproven
The board collapses to a single column; everything else was written desktop-first and never checked.

### 9. The visual system is competent, not characterful
Tokens, dark mode, accessible status pairing (colour + glyph + word) are all in place. But it looks
like a tool someone built for themselves, because it is. There is no identity, no sense of calm or
craft — and the product's whole argument is that a plain-text backlog can feel *better* than Jira.
The UI should make that argument.

### What to keep

- **State is never colour alone** — every status badge pairs a colour with the ledger's own glyph and word.
- **Derived numbers are honest** — rollups and totals are computed from entries, never stored.
- **Live reload** — the page follows the files.
- **Warnings over blocks** — the tool reports, the human decides.
- **The Commands sheet** — generated from the installed commands, so it can't go stale.
- **Progress meters on epics** — the clearest thing on the page today.

---

## 11. The API you have to work with

One JSON endpoint returns everything for a project; design freely against it.

```
GET  /api/workspace               ledger root, config, projects, git status, vocabulary
GET  /api/repo/<slug>             the full snapshot (see §4.3 for the field inventory)
GET  /api/repo/<slug>/revision    newest mtime — used for polling
GET  /api/repo/<slug>/file/<name> raw Markdown of one ledger file
GET  /api/commands                the command sheet, grouped
POST /api/repo/<slug>/action      {action, params} -> {message, warnings[], repo}
```

`/api/workspace` also returns the **vocabulary** — story states, bug states, board columns,
severities, layers, the Fibonacci scale, priorities — so the UI never hardcodes them. Any new view
can be built from the existing snapshot without server work; the gaps in §9 are the only exceptions
and all but retro notes are already in the payload.

---

## 12. Questions we'd like answered

1. **What should the home screen be?** Today it's a KPI row. Should it be a to-do list for the PM
   ("3 ideas to triage, 2 stories missing estimates, 1 blocked item")?
2. **Should the IA stay entity-based, become role-based (PM view / dev view), or workflow-based
   (capture → shape → plan → run → ship)?**
3. **How should the two-state model read?** A story is `In Sprint` *and* `In Review` at once. Today
   those live on separate screens.
4. **Where do quality warnings live** so they're actionable rather than ephemeral?
5. **How much of the graph should be drawn?** Dependencies and epic→story→bug links are real data.
   Worth visualising, or does that become decoration?
6. **What's the mobile story** — same IA responsively, or a cut-down read-only view?
7. **Does the Markdown stay visible?** The Files tab is a trust feature ("it really is just text").
   Keep it prominent, or tuck it away?

---

## 13. Running it

```
python3 plugins/agile-ledger-pro/dashboard/serve.py \
        --ledger plugins/agile-ledger-pro/dashboard/tests/fixture
```

Opens `http://127.0.0.1:4173/`. Front-end source is three files: `static/index.html`,
`static/style.css`, `static/app.js`.

The test fixture is small but exercises every shape: **2 epics · 4 detailed stories** (Ready, In
Sprint, Delivered) **plus one 📝 Draft** that exists only as an epic index line · **3 bugs**
(Triaged, Confirmed, Fixed) **plus one untriaged report** · **2 ideas** in the inbox · an **open
sprint** with items in To Do and In Progress · **2 closed sprints** with velocity · **1 release**.

It deliberately has **no blocked item and no Paused or Discarded story**, so if you want to see
those states, create them from the page: drag a card and use the Board's blocked action, or open a
story and use `→ Paused`. Likewise the Increment is empty until you move something to Done.
