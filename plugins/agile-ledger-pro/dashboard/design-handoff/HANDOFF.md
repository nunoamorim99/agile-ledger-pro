# Agile-Ledger Pro dashboard — design handoff

For: Claude Code, implementing the redesign in `plugins/agile-ledger-pro/dashboard/static/`
(`index.html`, `style.css`, `app.js`). This pack is self-contained: the design canvas is a
private link Claude Code can't open, so everything needed is in these files.

```
HANDOFF.md            this spec
tokens.css            colour, type and spacing tokens, light + dark
favicon.svg           the AL mark, switches with the colour scheme
reference/*.dc.html   the mockups, one per screen (see “Reading the reference files”)
```

---

## 0. Ground rules (unchanged from the product)

- Vanilla HTML/CSS/JS served by the stdlib Python server. **No npm, no build, no framework,
  no CDN, no webfonts.** Everything must work offline.
- Ledger prose is user text: render with `textContent` / DOM nodes, never `innerHTML`.
- The files are the product. **Add no new storage in the ledger.** Everything below is derived
  from `GET /api/repo/<slug>` and `/api/workspace` on read. Per-viewer conveniences
  (theme, density, lanes, “Viewing as”, acknowledged warnings) go in `localStorage`, wrapped in
  `try/catch`.
- Vocabulary (states, columns, severities, priorities, scale) comes from `/api/workspace`;
  never hardcode it.
- Warnings never block an action. The human decides.
- Keep the existing test suite green after every phase. Commit per phase.

## 1. Phasing — do these in order, one PR/commit each

| Phase | Scope | Changes the IA? |
|---|---|---|
| **1. Skin** | `tokens.css`, favicon, brand row, state glyphs, buttons/pills/rows restyled on the existing tabs | No |
| **2. Shell** | Left rail with the new destinations, hash routing, item pages `#/US-031`, drawer kept as peek, ⌘K palette, trust line | Yes |
| **3. Today + Health** | PM “Needs you” + developer “My work” lenses; standing Health view | — |
| **4. Run + Shape** | Board lanes, blocked in place, capacity, burndown; Backlog outline with Drafts, filters, group-by, density, bulk | — |
| **5. Ship + phone** | Roadmap by target, Increment, velocity, releases; 390 px pass on every view | — |

Phase 1 is safe to ship alone and gives the new look immediately.

---

## 2. Visual system — “Ruled Ledger”

Calm by default; colour only where a decision lives. Hairline rules instead of heavy boxes.

- **Tokens:** use `tokens.css` as-is (light default, dark via `prefers-color-scheme` and
  `[data-theme="dark"]`; wire the existing auto/light/dark toggle to `data-theme` on `<html>`).
- **Type:** three system stacks. `--serif` for page titles only (34 px; 52 px on hero
  boards). `--sans` for all UI (15/14/13/12, 11 px caps labels with .07em tracking; weights
  450/550/650). `--mono` for IDs, points, dates, versions, branches, paths.
- **Accent:** turquoise `#0B7A75` light / `#3FD4C6` dark. Means “in motion”: links, primary
  buttons, In Sprint glyphs, charts (single series).
- **Status tones** (good / warn / serious / crit) are reserved — never a chart series, always
  with a glyph and the ledger's word.
- **Shapes:** cards 12 px radius, controls 8 px, pills fully rounded. No left-border accent
  stripes, no gradients, no emoji as UI icons (icons are inline 16 px stroke SVG, 1.5 px).
- **Rows:** comfortable 10 px vertical padding, compact 4 px. Touch targets ≥ 44 px on
  phone.
- **Contrast:** all text ≥ 4.5:1 in both themes (already true for the token pairs).

### 2.1 Brand mark

`favicon.svg` → `static/favicon.svg`, and in `index.html`:

```html
<link rel="icon" href="favicon.svg" type="image/svg+xml">
```

Check the stdlib server serves it with `image/svg+xml`.

Rail brand row (top-left), theme-aware:

```html
<a class="brand" href="#/today" aria-label="Agile Ledger Pro — Today">
  <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" style="fill: var(--accent)"/>
    <path d="M5.5 24 12.5 8V24M8.35 17.5H12.5M17.5 8V24H26.5" fill="none"
          style="stroke: var(--on-accent)" stroke-width="3"
          stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
  <span class="brand-name">Agile Ledger</span><span class="brand-pro">Pro</span>
</a>
```

`.brand-name` 15 px / 700 / −0.01em. `.brand-pro` 10.5 px / 700 / uppercase / .06em,
padding 2px 6px, radius 5px, `background: var(--accent-soft); color: var(--accent)`.
The project switcher sits directly below as its own button (folder icon, project slug,
`ledger 2.0 · <branch>` in mono).

Document title follows the route: `Today · Agile Ledger Pro`, `US-031 · Agile Ledger Pro`.

### 2.2 State glyphs (replace emoji in the UI)

Shape = entity, fill = progress, mark = exception. 14 px, `viewBox="0 0 14 14"`,
`color` set per state, `aria-hidden="true"` with the visible state word beside it.
**Every glyph gets `title` = the ledger's own token** (e.g. `✅ Ready`), so the file
vocabulary is one hover away. This also disambiguates `✅ Ready` vs `✅ Delivered`.

Outer shapes:

```
story circle   <circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
bug diamond    <path d="M7 1.25 12.75 7 7 12.75 1.25 7Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
epic square    <rect x="1.75" y="1.75" width="10.5" height="10.5" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
dashed (Draft / Inbox / Proposed): add stroke-dasharray="2.6 1.9"
```

Inner fills (`fill="currentColor"`) — the ring's fill is the **board column**:

| Column | Story (circle) | Bug (diamond) |
|---|---|---|
| To Do | `M7 5.5a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3Z` | same |
| In Progress | `M7 7V3.25A3.75 3.75 0 0 1 10.75 7Z` | `M7 4 10 7H7Z` |
| In Review | `M7 7V3.25A3.75 3.75 0 0 1 7 10.75Z` | `M7 4 10 7 7 10Z` |
| In PR | `M7 7V3.25A3.75 3.75 0 1 1 3.25 7Z` | `M7 4 10 7 7 10 4 7 7 7Z` |
| Done | `M7 3.25a3.75 3.75 0 1 1 0 7.5a3.75 3.75 0 1 1 0-7.5Z` | `M7 4 10 7 7 10 4 7Z` |

State → glyph and colour:

| Entity | State | Glyph | Colour |
|---|---|---|---|
| Story | Draft | dashed circle | `--ink3` |
| | Ready | circle | `--accent` |
| | In Sprint | circle + column fill | `--accent` |
| | Delivered | filled circle (r 6.25) + check `M4.4 7.2 6.2 9 9.7 5.2` stroked in `--surface` | `--good` |
| | Paused | circle + bars `M5 4.75h1.4v4.5H5ZM7.6 4.75H9v4.5H7.6Z` | `--warn` |
| | Discarded | circle + slash `M3.2 10.8 10.8 3.2` (stroke) | `--ink3` |
| Bug | Inbox | dashed diamond | `--ink3` |
| | Triaged | diamond | `--ink2` |
| | Confirmed | diamond + centre dot r 1.6 | `--serious` |
| | In Sprint | diamond + column fill | `--accent` |
| | Fixed | filled diamond `M7 .5 13.5 7 7 13.5 .5 7Z` + check | `--good` |
| | Deferred | diamond + bars | `--warn` |
| | Won't fix | diamond + slash `M4.6 9.4 9.4 4.6` | `--ink3` |
| Epic | Proposed | dashed square | `--ink3` |
| | In Progress | square + bottom bar whose height = points done % | `--accent` |
| | Done | filled square (rx 3) + check | `--good` |
| | Paused / Discarded | square + bars / slash | `--warn` / `--ink3` |

**The two-state model** reads as one chip: glyph, lifecycle word, a hairline divider, the
board column — `◔ In Sprint │ In Review`. Outside a sprint the second word is absent. Same
chip on the board, backlog rows, item page and palette.

Other marks:
- **Priority** — three ascending bars (12 px); high = all solid, medium = 2, low = 1, the
  rest at 22% opacity. Word in `aria-label` and forms; ledger emoji in `title`.
- **Severity** — word pills: Critical (`crit-soft`/`crit`), Major (`serious-soft`/`serious`),
  Minor (`sunken`/`ink2`), Trivial (outline).
- **Blocked** — no-entry icon + “Blocked · <reason>” in `crit-soft`/`crit`; the card border
  goes dashed `--crit`.
- **Warning** — triangle + text in `warn-soft`/`warn`.
- **Dependency chip** — `needs US-029` mono + ✓ in `--good` when done.

---

## 3. Information architecture

From ten file-shaped tabs to five jobs. Files stay one click away.

| New destination | Route | Absorbs | Answers |
|---|---|---|---|
| Today | `#/today` | Overview, Inbox counts, Blocked list, Person filter | What needs me right now? |
| Inbox | `#/inbox` | Inbox | What's waiting to be sorted? |
| Backlog | `#/backlog` | Epics, Stories, Bugs | Is the next sprint ready? |
| Sprint | `#/sprint` | Board | Are we going to make it? |
| Ship | `#/ship` | Releases, Sprints | What shipped, what's next? |
| *Ledger:* Health | `#/health` | Run ledger check | What's wrong with my backlog? |
| *Ledger:* Files | `#/files`, `#/files/<name>` | Files | Show me the raw Markdown |
| *Ledger:* Commands | `#/commands` | Commands | What can this do? |
| Item | `#/<ID>` (US-, BUG-, EPIC-) | the drawer | Everything about one item |

- **Routing:** `hashchange` + a small route table. Back/forward must work; lanes, filters
  and scroll are restored when returning to a view. Unknown ID → “Not in this ledger” + search.
  Live reload keeps the current route.
- **Drawer stays** as a quick peek from lists (`Shift+Enter` / click); `Enter` or ↗ opens the
  full item page.
- **Rail** (left, 232 px): brand row, project switcher, the five destinations with counts
  (Today = Needs-you count, Inbox = ideas + untriaged bugs, Sprint = items on board,
  Ship = increment size), a “Ledger” label, Health (count in `--warn`), Files, Commands.
  Footer: “Viewing as” (replaces the Person dropdown; defaults to config “Me”), the
  **trust line**, theme segmented control (Auto / Light / Dark).
- **Trust line:** `● 8 files · synced 4s ago` and `3 uncommitted · Commit…`. Replace the
  “Ledger reloaded” toast with a quiet pulse here plus a brief highlight on changed rows.
- **⌘K palette:** one input, results grouped *Items* (ID prefix and title match, with the
  state chip), *Do it here* (form commands from `/api/commands`), *In Claude Code*
  (copy-to-clipboard + one-line reason). Keys: ↑↓, Enter = open page, Shift+Enter = peek,
  Tab = actions on the item, Esc = close.
- **Phone (≤ 760 px):** rail becomes a bottom tab bar — Today, Inbox, Backlog, Sprint, More
  (More = Ship + Ledger). Board becomes a column pager (chips with counts). Read + light actions
  (move, unblock, capture, triage); Plan sprint and Cut release stay desktop.

---

## 4. Screens

Reference file for each is in `reference/`. Data fields refer to the snapshot (§4.3 of the brief).

### 4.1 Today — PM lens (`Today.dc.html`)
Serif greeting, one line of context (date, sprint, day N of M, how many things need you).

**Needs you** — an ordered list; each row is a *rule over the snapshot* and disappears when the
rule is no longer true. Row = tinted icon tile, one-line title with mono IDs, one-line detail,
one primary action. Rules, in order:

1. Blocked items (`sprint.blocked`) → “US-035 is blocked” + reason + “what it waits on” if the
   reason names an ID; action “Pull US-038 in” when that ID is Ready and fits capacity, else “Board”.
2. Ideas + untriaged bugs → inline triage list (→ Epic / → Story / Discard; Triage…).
3. Ready stories failing Definition of Ready → names the missing field(s); action “Fix”.
4. In-sprint items started before a dependency is Done → “US-032 started before its dependency”.
5. Increment non-empty → “N delivered items aren't in a release”; “Cut release…”.
6. Ledger check drift → count + first two findings; “Review” → Health.
7. Uncommitted ledger files (workspace git status) → list; “Commit…”.

Right column: **Sprint pulse** (goal, burndown — see §6 gap 1 — behind/ahead sentence,
points per column with glyphs, committed vs capacity), **Next sprint readiness** (Ready points
vs rolling velocity, meter, Draft count), **Activity** (from `sync_log` / `last_sync`, plus
“<file> changed outside the dashboard”).

### 4.2 Today — developer lens (`MyWork.dc.html`)
Shown when “Viewing as” is someone without the PM role (or toggle explicitly). **Now** card:
the in-progress item with state chip, points, epic, layer; title; story sentence with *As a /
I want / So that* in italics; branch name + Copy; dependency chips; acceptance criteria as a
checklist with `n / m met` and GIVEN / WHEN / THEN keywords in 11 px mono caps; Definition of
Done from `definitions.definition_of_done`; transition buttons (next column primary).
Side: **With review** (In Review / In PR items), **Up next** (To Do, blocked shown inline),
“Your last sprint”.

### 4.3 Item page (`Item.dc.html`)
Breadcrumb (Backlog / epic / ID), URL + Copy link. Header chips (state, priority, points,
assignee), serif title with mono ID. **Lifecycle track:** Draft → Ready → In Sprint (expanded,
tinted, five column segments, current one bold) → Delivered. Main: story sentence (serif
19 px), criteria checklist, notes, **ledger source** block (file + lines, raw Markdown in a
`<pre>`, “Open in Files”). Side: Move it (transitions, branch, epic / layer / sprint),
**Connections — one hop** (epic above; *Needs* = `dependencies` left; *Needed by* = reverse
lookup right; *Bugs* = bugs whose `relates_to` is this item, below; a warn-coloured edge when
an item started before its dependency was done), **Before Done** (DoD checklist).
Bugs use the same page with symptom / steps (show `steps_confidence`) / expected / actual /
assessment (show `assessment_confidence`).

### 4.4 Sprint (`Sprint.dc.html`)
Header: sprint name + dates + day N of M, serif goal title, capacity meter (`committed of
capacity · done`), blocked and started-early counts, burndown card. Toolbar: Lanes = None /
Assignee / Epic (persist per viewer). Board: header row with glyph, column name, `count · pts`;
one row per lane (label + `n items · pts`), cells on `--sunken`. Cards: glyph, mono ID, points,
title, blocked / warning flag in place, avatar initial + name, mono meta (epic, AC n/m, PR).
Drag stays; dropping on Done still opens the PR/commit form. Keyboard: 1–5 moves the focused
card. The separate Blocked list below the board is removed.

### 4.5 Backlog (`Backlog.dc.html`)
Header with “Ready vs rolling velocity” meter and DoR failure count. Filters as dashed chips
(Type, State, Area, Assignee, Priority), Group = Epic / State / Area, Density = Comfortable /
Compact. Selection bar (dark) when rows are checked: Priority…, Assign…, Move to epic…, Pull
into sprint — each runs the existing action per item and one toast summarises the warnings.
One card per epic: chevron, epic glyph, ID, title, state, target pill, area pill, two meters
(stories, points). Rows: checkbox, glyph, ID, title + flag pill, state chip, priority bars,
points, assignee, “Write up” for Drafts (opens `detail_story`). Delivered stories collapse to a
footer line. Bugs are their own group (“parallel track · no epic”). Done epics collapse.
Large lists: render the first ~100 rows per group with “Show all”.

### 4.6 Health (`Health.dc.html`)
Summary tiles (DoR failures, drift, saved-with-warning, uncommitted — the last not counted).
Groups, each finding with what's wrong, a `file : line` source chip and a fix action:
**Fails Definition of Ready**, **Ledger drift** (from `check`), **Saved with a warning**,
**Resolved this sprint** (collapsed `<details>`). Side: the Definition of Ready checklist
with which items are failing; uncommitted files + Commit.

### 4.7 Ship (`Ship.dc.html`)
Roadmap columns by epic `target` (current target tinted; a “No target” column catches the
rest), each epic with glyph, ID, title, points meter. **Increment** with Cut release.
**Velocity** — column chart, one accent series, 4 px rounded tops, dashed rolling-average
line labelled at the right, only the last value labelled, hover `title` = sprint name ·
completed of committed; “View as table”. **Releases** — version + date in mono, serif title,
theme line, ID pills. “Copy as release notes” (Markdown to clipboard).

### 4.8 Palette and phone — see `Palette.dc.html`, `MobileToday.dc.html`, `MobileSprint.dc.html`.

---

## 5. Interaction rules

- **Warnings persist.** After an action returns `warnings[]`, the toast reads
  “Saved · N warnings — View” (link to the item or Health). Prefer warnings that are
  *re-derivable* (unmet dependency, DoR gap) so Health shows them live from the snapshot;
  only “Acknowledge” is stored (localStorage, keyed by project + finding).
- **Live reload:** keep the 2.5 s poll. Treat a revision bump that didn't follow one of the
  page's own actions as an external edit → trust-line pulse + row highlight, no toast.
- **Empty and edge states** from §8 of the brief keep their behaviour; restyle with the new
  tokens (banner: `warn-soft` / `crit-soft` with icon, never colour alone).

---

## 6. Data gaps — confirm before building these parts

| # | Needed for | Status | Suggested v1 |
|---|---|---|---|
| 1 | Burndown **curve** | Snapshot has current state only, no per-day history | Show today's remaining vs the ideal line as a single point + sentence; draw the curve only if Done dates exist per item |
| 2 | Item **source lines** (`file : line`) | Not in the snapshot | Fetch the raw file and locate the entry by its heading ID; add line ranges to the parser later |
| 3 | **Blocked since** (“2 days”) | Not stored | Omit the age unless the reason line carries a date |
| 4 | **Retro notes** on Ship | Not parsed (known) | Small parser change, or hide the section |
| 5 | DoR evaluation for the standing view | Server reports DoR gaps only on action responses | Evaluate the basic checks client-side (story, criteria, estimate, priority) or run `check` on load and after reload |
| 6 | “Changed outside the dashboard” | Inferred client-side (see §5) | — |

Sample data in the mockups (names, IDs, figures, the DoR/DoD items, the Markdown excerpt) is
illustrative; always render the real ledger content.

## 7. Acceptance checks per phase

- No external requests (DevTools network tab: only `127.0.0.1`).
- Both themes checked on every touched view; the Auto/Light/Dark toggle works.
- Every status shows glyph + word; nothing relies on colour alone.
- Every view usable at 390 px wide with no horizontal page scroll (wide tables scroll inside
  their own box).
- All ledger text goes through `textContent`.
- Existing tests pass; add tests for routing (deep link, back) and for each Needs-you rule.

## 8. Reading the reference files

`reference/*.dc.html` are mockups from a design tool. The markup uses that tool's template
syntax (`{{hole}}`, `<sc-for>`, `<sc-if>`, `<x-dc>`, a `DCLogic` class) and won't run
standalone. Use them for **structure, copy, spacing, sizes and colours**; take values from the
inline styles and the `<helmet><style>` blocks. `renderVals()` in Sprint, Backlog and
MobileSprint shows how the data maps to cards and rows.
