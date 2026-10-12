# Agile-Ledger Pro — Skill Specification (v1, design-complete)

> **What this document is.** A complete, self-contained description of the **Agile-Ledger Pro** skill as
> designed — the decisions are locked, the build has not yet started. It is the direct successor to
> **Idea-Ledger v1**: it keeps that skill's hard-won invariants and layers a professional Scrum
> lifecycle on top. Paste or upload it into a fresh conversation to seed the build.
>
> Agile-Ledger Pro is an installable **Claude Code skill** (`SKILL.md` + reference templates + slash
> commands). Like its predecessor it is intentionally plain Markdown: no database, no dependencies.
> That simplicity is the whole reason a distributed team without Jira can adopt and share it. Defend it.
>
> **The two-layer model.** The team uses **GitHub for code** (branches, commits, PRs, merges) and
> **Agile-Ledger Pro for the product-management layer** (backlog, stories, sprints, the board, releases).
> The two are stitched together by one join key — the **User Story ID** — which travels through every
> branch, commit, and PR so the ledger and the codebase always agree.
>
> **Superseded on placement (v2.0).** This document describes the ledger as a folder inside the host
> project, which is how v1 shipped. Since v2.0 the ledger lives in a **separate ledger repository** with
> one folder per code repo. Every rule below still holds; only the path changes
> (`Agile-Ledger/X.md` → `<ledger-root>/<repo-slug>/X.md`). See **Addendum — v2.0** at the end.

---

## 1. Purpose & core concept

A product-management system made of plain-Markdown files living in a dedicated `Agile-Ledger/`
folder, applying the Scrum framework so a Product Manager can run the full product lifecycle —
backlog → sprint → increment → release — entirely from the command line, and share the result with
developers who don't need to learn a new tool.

The driving constraint: the team is **geographically scattered and on different schedules**. The
synchronous Scrum ceremonies (especially the Daily Scrum) break down across time zones. So the
highest-value thing this skill does is turn the live state of the work into **shareable, plain-text
snapshots anyone can read on their own clock** — the async board, the roadmap, the per-developer
work view. The skill is the *material* the ceremonies run on, not a replacement for the human
conversations.

Two responsibilities, always in this order of priority:
1. **Bookkeeping is the job** — keep the backlog, sprint, board, and release record true.
2. **Execution is optional** — git/branch/PR automation is opt-in; the developer can build however
   they like, and the ledger still stays accurate.

---

## 2. What carries forward from Idea-Ledger (the foundation)

These invariants are methodology-agnostic and survive **unchanged**. They are not up for
re-litigation in the build:

- **Plain Markdown, no database, known folder.** The reason a no-Jira team can use and share it.
- **Never delete.** Everything is kept with its reason; discarded work keeps *why* it was rejected.
- **State = physical position, moved only by a command.** A status change is a move between sections
  (or board columns), never a silent marker swap. This is also the user's explicit requirement that
  items "only change position on some actions."
- **Recompute IDs, never reuse.** A `Next free ID` hint exists per type, but every registration scans
  the max existing ID of that type and uses max + 1, reconciling the hint. Survives manual edits.
- **Absolute dates only** — resolve "today" to a real `YYYY-MM-DD` before writing.
- **The human's voice, English ledger** (configurable) — translate raw captures at triage.
- **Inbox-first capture split from triage** — friction-free capture; rigor applied later.
- **Enforced dependency gate** — building is blocked (with a warning) on unshipped dependencies.
- **Four-outcome duplicate detection** — exact / improved / related-distinct / new.
- **Thin commands delegating to one `SKILL.md` brain.** Broad, assertive trigger `description`
  (skills under-trigger, so the description is pushy on purpose).
- **Re-read immediately before writing** (makes multi-session capture safe).
- **Session start:** read state first, load silently, give at most a one-line orientation.

> **The one principle that bends — by design.** Idea-Ledger deliberately kept **one** flat lifelong
> ID and warned against "reintroduc[ing] a second id space casually." Scrum needs a hierarchy, so
> Agile-Ledger Pro reintroduces multiple ID spaces — but **explicitly and deliberately** (see §3), which
> is exactly the condition v1 set for doing it.

> **The philosophical resolution — capture stays dumb, rigor lives downstream.** v1 excluded
> acceptance criteria and effort estimates because "they'd erode fast capture," and ruled that any
> future rigor "must not slow down `/idea`." Agile-Ledger Pro embraces all that rigor — AC, estimates,
> INVEST, Definition of Ready — but confines it to the **detail / refine** stage. `/idea` stays
> instant, dumb, and append-only. The hard-won insight is honored, not overturned.

---

## 3. The ID system (typed hierarchy)

Three ID types, each **sequential within its own type**, never reused, recomputed on every
registration:

| Type | Shape | Parent |
|---|---|---|
| Epic | `EPIC-001` | — (top level) |
| User Story | `US-014` | `Parent: EPIC-001` |
| Task | `TASK-031` | `Parent: US-014` |

- **Parent pointers, not nested numbers.** A story records `Parent: EPIC-001`; a task records
  `Parent: US-014`. We do **not** use nested IDs like `US-014.3`, because nested numbers renumber on
  reorder and break the never-reuse / stable-cross-link invariant. Typed flat IDs + a `Parent:` field
  keep every reference stable forever.
- **Cross-links** between distinct items use `[[EPIC-xxx]]` / `[[US-xxx]]`, exactly as v1 used
  `[[IDEA-xxx]]`.
- **Tasks are optional and off by default.** The default hierarchy is **Epic → User Story**. A task
  is created only when a story needs an explicit sub-unit — unplanned/harder work, or a true FE/BE
  two-developer split (see §7, §13). Most projects never need them.
- **The Inbox is type-agnostic.** A raw `/idea` has no type; `/triage` decides whether it becomes an
  epic or a story and mints the appropriate ID.

> **Decision & rationale.** Typed-with-parent is the cleanest fit for how PMs already think (epics
> contain stories contain optional tasks) and the only scheme that keeps links stable under reorder.
> This is the deliberate, designed reintroduction of multiple ID spaces that v1 said must be explicit.

> **Case rule (a v1 scar healed).** The ledger stores the **canonical uppercase** ID (`US-014`).
> Everything in git-land — branches especially — is **lowercase** (`us-014`). All ID matching during
> git reconciliation is **case-insensitive**. (v1 had real pain from uppercase branch names; this
> closes that hole.)

---

## 4. The work hierarchy: Epics, User Stories, Tasks

- **Epic** — a large body of work delivering significant value, spanning **multiple sprints**. A
  strategic capability, not just a big story. Epics **never go on the board** (they're bigger than a
  sprint); they are followed up via the roadmap (§6, §9).
- **User Story** — a small, testable, **vertically sliced** unit of value completable **within one
  sprint**. Written `As a <role>, I want <goal>, so that <benefit>` with Gherkin acceptance criteria.
  The unit that flows across the board and the unit of estimation.
- **Task** *(optional)* — a sub-unit of a story when the work must be divided (e.g. one FE, one BE).
  A task is **not** a unit of user value; it's a work split.

**Vertical slicing is enforced as a guardrail, not just documented.** A story must cut across
architectural layers to deliver value; splitting into a "frontend story" and a "backend story" is the
classic anti-pattern (no value ships until both integrate, dependencies are baked in, the backlog
fills with developer-only tech stories). `/refine` actively flags stories that look horizontally
sliced and suggests vertical splits instead (by workflow step, data variation, CRUD operation, or
happy-path-then-edge-cases).

**INVEST** is the story-quality checklist applied at refinement: Independent, Negotiable, Valuable,
Estimable, Small, Testable.

---

## 5. The two state machines (the spine)

Scrum separates the **product backlog** from the **sprint**, and Agile-Ledger Pro mirrors that with two
distinct status sets in two files. Conflating them is what makes these tools sprawl.

**`Backlog.md` — shaping states** (a story's life *before* it reaches a sprint):

```
📥 Inbox      raw capture, no ID yet
📝 Draft      triaged: has ID, parent, priority — not yet detailed
✅ Ready      detailed: story sentence + AC + estimate, Definition of Ready met (pullable)
❄️ Paused     deferred, kept
🗑️ Discarded  rejected, kept WITH the reason
```

**`Sprint.md` — board / execution states** (only once a story is pulled into a sprint):

```
To Do  →  In Progress  →  In Review  →  In PR  →  Done
```

plus a **🚧 Blocked flag** that can sit on a story in *any* column (a flag, not a column — so a
blocked story never loses track of which real column it belongs to; this is also where the dependency
gate surfaces).

> **The structural spine — confirmed.** A story's **full entry lives permanently under its epic in
> `Backlog.md`** (single source of truth; parent and children always co-located). While the story is
> in a sprint, the **board in `Sprint.md` tracks only its column, by ID reference**. The board is a
> *view*, not a second copy. `/ledger-check` keeps the two consistent. The rejected alternative —
> physically moving each story's full text between files as it progresses — would scatter an epic's
> children across three files and make epic follow-up painful.

**The handoffs** (all command-gated):
- `/plan-sprint` — a **Ready** story in `Backlog.md` is referenced into **To Do** in `Sprint.md`.
- `/start-us` → In Progress (offers the branch) · `/review` → In Review · `/pr` → In PR ·
  `/done-us` → Done.
- `/close-sprint` — **Done** stories flow onward to the Increment (§8); anything unfinished is sent
  **back to Ready** in `Backlog.md`.

The five board columns map to the §15 git flow. If a team ever finds five columns too many, In Review
and In PR can collapse into one — but for a GitHub flow, keeping them separate is the right default
(it stops PRs from churning during testing).

---

## 6. Epic follow-up & epic version control

Because epics never appear on the board, they get their own follow-up — and their own version
history, which is the signature mechanic of Idea-Ledger lifted one level up.

**Epic = permanent home.** Each epic is a top-level block in `Backlog.md`; its stories nest beneath
it, grouped by state. The epic is never deleted and accumulates the full delivered history of its
stories in place.

**Epic status is derived from its children**, never set by hand:

```
💡 Proposed → 🔨 In Progress (≥1 story active or done) → ✅ Done (all stories delivered)
              ↘ ❄️ Paused   ↘ 🗑️ Discarded
```

**Epic version control — the "how many times did we increment this?" metric.** In v1, an idea's `vN`
history counted how many times *that idea* shipped. Here, an epic's `History` counts how many rounds
of value *that capability* has received:

```
### EPIC-005 — User onboarding ✅   (target v3.0 · 6/6 stories · 29 pts)
Goal: get a new user from signup to first value in under 2 minutes.
Area: onboarding

History:
- v1 (2026-02-10) — initial onboarding — US-012, US-013, US-014 — released in v1.4
- v2 (2026-04-22) — social login added — US-031 — released in v1.7
- v3 (2026-06-18) — guided setup checklist — US-048, US-049 — released in v2.1
```

Three `v` lines = delivered once, improved twice. The count is readable at a glance.

> **Version-close trigger (locked default).** The **first** time an epic reaches Done = **v1**. Each
> time it **returns to Done after having previously been Done** = the next version (v2, v3…). The
> boundary is the Done transition, so a round bundles whatever stories shipped before the epic went
> green again — one or several.

**Adding work to a Done epic re-opens it automatically.** Because status is derived, dropping a new
story under a Done epic flips it ✅ → 🔨; the story flows through the normal board; on ship the epic
returns to ✅, closing a new version.

> **The triage rule — increment vs. new epic (the four-outcome check, lifted to the epic level).**
> At `/triage`, the question is: *does this idea serve the same user goal as an existing epic, or a
> new goal?*
> - **Same goal** (extend / improve an existing capability) → **new User Story under that epic**;
>   on ship it bumps the epic's version. *(This is the common "improve something already built" case.)*
> - **New goal** (a distinct capability that merely touches the epic) → **new `EPIC-xxx`**,
>   cross-linked `[[EPIC-xxx]]`.
>
> It is never "edit the epic directly," because an epic can only be improved *by delivering a story* —
> the story is the unit of value.

**Cross-check with the release axis (§8):** an epic *increment* typically lands as a **Minor**
product bump; a brand-new epic typically lands as a **Major** — the same `Major.Minor` semantics as
v1.

---

## 7. Estimation, priority & velocity (two distinct axes)

These are different things, owned by different people, and must not be collapsed:

- **Priority** — value-based, PM-owned: 🔴 high · 🟡 medium · 🟢 low, plus backlog **order**.
  Descriptive, not a strict queue (carried from v1). Capture the *rationale*.
- **Estimate** — size/effort, developer-owned: **story points on the Fibonacci series**
  (1, 2, 3, 5, 8, 13…). Set at the detail stage.

Keeping them separate is what lets you reason about "high value / high effort" vs "low value / low
effort."

**Velocity** — sum of completed story points per sprint, recorded in `Sprints-History.md` and used to
inform `/plan-sprint` capacity. Tracked at the **team** level.

**Assignee** *(optional)* — a developer name set at `/plan-sprint`. Surfaces **workload and
blockers**, not a productivity leaderboard.

> **Decision & rationale.** Individual point tallies can quietly become a scoreboard that discourages
> helping, pairing, and taking on the hard stories. The healthy framing (the user's own) is *spotting
> overload and understanding why something slipped* — so `/my-work` and `/status` present assignee
> data as workload + blockers, never as a ranking.

---

## 8. Sprints, the Increment & releases (three cadences, kept distinct)

| Concept | What it is | Cadence | File |
|---|---|---|---|
| **Sprint** | A time-box with one Sprint Goal and a Sprint Backlog | The heartbeat | `Sprint.md` (active), `Sprints-History.md` (closed) |
| **Increment** | Everything that meets the Definition of Done, not yet released | Grows each sprint | `Releases.md` (top section) |
| **Release / version** | The *decision* to ship — `Major.Minor` | Independent of sprints | `Releases.md` (history) |

> **Clean lineage from v1.** Idea-Ledger's "🚧 Unreleased" section **is** the Increment, renamed to
> its Scrum-correct identity: Done work awaiting a release decision. `/release` still cuts the numbered
> `Major.Minor` version from it, planned or ad-hoc, exactly as in v1.

- **Major** (1.0 → 2.0) = a group of new capabilities / typically a new epic.
- **Minor** (2.0 → 2.1) = an increment to existing functionality / typically an epic increment.
- `/close-sprint` records the Increment; `/release` mints the version number; the two are decoupled
  (you can release every sprint or batch several).

---

## 9. Scrum ceremonies — what the skill does and doesn't do

Be honest about the boundary. A Markdown skill can own the **artifacts and state**; it cannot *run*
the **events** — those are human conversations. The skill's role is to **produce the material the
ceremonies need**.

| Scrum element | Agile-Ledger Pro's role |
|---|---|
| Product Backlog (+ Product Goal) | **Owns** — `Backlog.md`, epics carry the goal |
| Sprint Backlog (+ Sprint Goal) | **Owns** — `Sprint.md`, goal pinned at top |
| Increment (+ Definition of Done) | **Owns** — `Releases.md`, DoD in `Definitions.md` |
| Sprint Planning | **Supports** — `/plan-sprint` proposes goal + pulls ready stories; humans decide |
| Daily Scrum | **Supports** — `/board` / `/standup` give the async snapshot (the killer feature) |
| Sprint Review | **Supports** — `/close-sprint` summarizes Done vs. carried-over |
| Retrospective | **Captures** notes if asked; does **not** facilitate |
| Backlog Refinement | **Supports** — `/refine` runs the INVEST / DoR / vertical-slice checks |

**Three lenses** for three audiences:
- **`/board`** — one sprint, story columns. The daily async snapshot.
- **`/roadmap`** — epics across sprints, grouped by target version, with rollups. The strategic
  follow-up (this also recovers the forward-planning role that sprints took over from v1's
  `/plan-version`: the roadmap is where epics map to versions).
- **`/status`** — the whole picture: counts by state, velocity, blocked, unreleased, latest version.

---

## 10. Duplicate detection & the triage decision

Before registering anything, scan **every** section across all files — Inbox, Backlog (all states),
Sprint, delivered history, and Paused/Discarded (re-raising a discarded item is valuable *because*
its recorded reason is right there). Resolve to one of four outcomes and say which:

1. **Exact match** → surface the existing entry; don't duplicate.
2. **Same thing, improved** → a new story under the relevant epic (which increments the epic version
   on ship) — not a duplicate.
3. **Related but distinct** → register new, cross-linked with `[[…]]`.
4. **Genuinely new** → register fresh.

This runs at both levels: epic-vs-epic (the §6 increment-vs-new-epic rule) and story-vs-story.

---

## 11. Capture vs. triage vs. detail (the deliberate friction split)

Three stages, escalating in rigor, so that the moment of capture stays frictionless:

- **`/idea` = capture.** Instant, dumb, append-only: raw text + absolute date into the **Inbox** at
  the top of `Backlog.md`. No id, no dedup, no rewriting, any language. Safe mid-work.
- **`/triage` = classify + register.** Dedup check; decide **epic or story**; assign typed ID; set
  parent, priority, area; rewrite in English in the user's voice; move to Draft. *No AC, no estimate
  yet.*
- **`/detail-us` / `/detail-epic` = add rigor.** Write the `As a / I want / So that`, the Gherkin
  acceptance criteria, the estimate, the layer, dependencies; apply INVEST; move Draft → Ready when
  the Definition of Ready is met.

All the heavy PM rigor lives in stage three. Stage one never changes.

---

## 12. Templates (the shapes the skill scaffolds)

Bundled as reference files so they're never re-derived. Summarized here; exact text in `references/`.

**Epic** — `### EPIC-00X — <title> <status-emoji>` with `Goal`, `Area`, target version, derived
rollup (`stories done/total · points done/total`), `History` (vN lines), then nested stories grouped
by state.

**User Story (Ready):**
```
### US-014 — Google SSO login 💡   (Parent: EPIC-005)
Priority: 🔴   Estimate: 5   Area: auth   Layer: fullstack
Assignee: —

As a new user, I want to sign in with my Google account,
so that I don't have to create another password.

Acceptance criteria (Given / When / Then):
- Given a valid Google account, when I tap "Sign in with Google",
  then I land on the dashboard authenticated.
- Given a cancelled Google prompt, when I return,
  then I see the login screen with no error state.

Dependencies: [[US-009]] (auth service)
```

**Task (optional):** `### TASK-031 — <title>` with `Parent: US-014`, `Layer`, `Assignee`. A work
split, not a value unit.

**Acceptance criteria** — **Gherkin only** (Given / When / Then). Binary, behavior-focused
(describes *what* the system does, not *how*) — so a developer in another time zone can self-verify
"done."

**Definition of Ready (DoR)** and **Definition of Done (DoD)** — checklists in `Definitions.md`. DoR
gates Draft → Ready; DoD gates In PR → Done.

**PR body** — generated by `/pr` from the ledger: linked story + parent epic, the story sentence, the
**AC rendered as a reviewer checklist**, how-to-test, the DoD checklist. Title `<title> [US-014]`.

**Commit template** — Conventional Commits: `type(scope): subject (US-014)`.

**Delivery note** — the change-handoff block (what changed, how to test, AC + DoD checked) — the
GitHub-PR equivalent captured in the ledger for the manager/PM audience.

---

## 13. Git & traceability conventions

The **US ID is the join key** through the entire chain. Strip it and reconciliation becomes guesswork.

| Artifact | Shape | Notes |
|---|---|---|
| **Branch** | `us-014-google-sso` | lowercase, **no type prefix** (a branch carries many kinds of change), ID + slug |
| **Commit** | `feat(auth): add Google SSO sign-in (US-014)` | Conventional Commits — type **kept** (each commit is one type) |
| **PR title** | `Google SSO sign-in [US-014]` | **no type** (clear, not misleading), ID in brackets |

- **Case-insensitive matching** ties `US-014` (ledger) ↔ `us-014` (branch) ↔ `[US-014]` (PR) ↔
  `(US-014)` (commit).
- **Squash-merge heads-up** (documented in `Definitions.md`): a squash subject inherits the
  type-less PR title, so it won't parse as a Conventional Commit. This **does not affect Agile-Ledger Pro**
  (its `/changelog` is derived from the ledger's released stories, never from parsing git history — as
  in v1), but teams relying on GitHub-side conventional-commit automation should keep the type on the
  squash subject.

**FE/BE sub-branches (optional, only for a genuine two-developer split):**
```
main
 └─ us-014-google-sso        ← the US branch (off main)
     ├─ us-014-fe            ← FE dev; merges back INTO the US branch
     └─ us-014-be            ← BE dev; merges back INTO the US branch
                               then ONE PR: us-014-google-sso → main
```
Sub-branches **only ever merge into the US branch, never into main** — so traceability stays
**1 US → 1 PR → main** (only the US branch carries `[US-014]` to main). Sub-branches are ephemeral
(deleted after merging up), lowercase, suffixed by layer (`-fe`, `-be`) or task ID. If coordinating
two devs on one US gets painful, that's the signal the story was too big and should have been split
vertically into two stories.

**`/sync-main`** — the "what shipped while I was out" command, for a remote PM. Read-only by default:
fetches main, lists merges since the last sync cursor, maps each commit back to its US via the ID, and
flags two cases —
1. **Merged but ledger not Done** → propose reconciling (mark Done, fill the Increment).
2. **Merged with no US ID** → the off-plan surprise (someone approved + merged without a story); it
   surfaces *precisely because* it can't be traced, so you back-fill a US or go ask.

The sync cursor is stored **visibly in Markdown**: a `Last main sync: 2026-06-25 @ a1b2c3d` line in
`Sprint.md`, plus a short append-only sync log (nothing hidden).

> **Git execution policy (v1's "never presumptuous," extended).** The skill **generates** branch
> names, commit messages, and PR bodies, and **reports** on main — but actual git execution is
> **opt-in per project via one config line** in `Definitions.md`. Default: *generate text, don't
> execute*. The skill **never auto-merges** (merges happen on GitHub via PR approval anyway; the skill
> reconciles *after*). Merge/push always require an explicit yes.

---

## 14. The commands (twenty-one)

Thin entry points; `SKILL.md` is the single source of truth they delegate to. Also triggers from
natural language ("new story", "let's plan the sprint", "what merged to main").

**Shape the backlog (PM / Product Owner)**

| Command | Does |
|---|---|
| `/idea <text>` | Instant Inbox capture. Append-only, any language, safe mid-work. |
| `/triage` | Classify Inbox items as **epic or story**, assign typed ID + parent, set priority/area, rewrite in voice/English → Draft. |
| `/create-us <EPIC-ID>` | Generate the user-story skeletons under a chosen epic. |
| `/detail-us <US-ID>` | Fill one story: `As a/I want/So that` + Gherkin AC + estimate + layer + deps; apply INVEST → Ready. |
| `/detail-epic <EPIC-ID>` | Batch-detail **all** of an epic's stories. |
| `/create-task <US-ID>` | *(optional)* Add an FE/BE or sub-unit task under a story. |
| `/refine` | Backlog refinement: surface under-detailed top items, oversized/horizontally-sliced stories, dangling deps (INVEST + DoR pass). |

**Run the sprint**

| Command | Does |
|---|---|
| `/plan-sprint` | Propose a Sprint Goal, pull top-ordered **Ready** stories that fit velocity, set assignees, build the board. |
| `/board` *(alias `/standup`)* | Print the async sprint snapshot — the five columns + blockers. |
| `/my-work <name>` | One developer's slice: their current-sprint stories, status, AC, branch, blockers. |
| `/start-us <US-ID>` | Dependency-gate, To Do → In Progress, offer the branch. |
| `/review <US-ID>` | In Progress → In Review (code-complete, **on branch, no PR yet**); generate the AC/DoD verification checklist. |
| `/pr <US-ID>` | In Review → In PR; generate/open the PR from the ledger (only on verified work). |
| `/done-us <US-ID>` | In PR → Done, gated by DoD + all AC checked; record into the Increment. |
| `/close-sprint` | Summarize Done vs. carried-over, push unfinished → Ready, record the Increment + velocity, prompt for retro notes. |
| `/sync-main` | Read-only reconcile of main vs. the ledger; flag merged-not-Done and merged-no-ID. |

**Release & communicate**

| Command | Does |
|---|---|
| `/release [version]` | Cut a `Major.Minor` version from the Increment (planned or ad-hoc). |
| `/changelog` | Export user-facing release notes from the version history (derived; never edits the ledger). |
| `/status` | The whole picture: counts by state, velocity, blocked, unreleased, latest version. |
| `/roadmap` | Epics grouped by target version, with rollups — the strategic follow-up. |
| `/ledger-check` | Audit all files for drift (duplicate/typed-id clashes, dangling parents, childless epics, board ↔ backlog mismatch, orphan Increment lines, stale `Next free ID`); report; fix only on request. |

> **Naming note.** Verb-object names (`/detail-us`, `/create-us`) are deliberate: developers who don't
> live in the skill have to use it, so explicit beats terse. Namespacing (e.g. `/al:release`) is the
> escape hatch if a host project collides.

---

## 15. The story lifecycle, end to end

```
Inbox → /triage → Draft → /detail-us → Ready
   → /plan-sprint → To Do
       → /start-us  → In Progress   (branch us-014-google-sso offered)
       → /review    → In Review     (code-complete on branch; AC/DoD verified — "is it really done?")
       → /pr        → In PR         (verified work only; PR opened, AC checklist pre-ticked)
       →  …PR approved + merged on GitHub…
       → /done-us   → Done          (DoD met; recorded into the Increment)
   → /close-sprint  (Done → Increment; unfinished → Ready)
   → /release       (Major.Minor cut from the Increment)
```

`/sync-main` runs alongside whenever the PM has been away, catching anything that merged without the
ledger keeping up. The split of `/review` (verify on branch) from `/pr` (open on verified work) is
what stops PRs from churning during testing — they open clean and approve fast.

---

## 16. Behavioral invariants (always)

- **Write the ledger in English** (configurable); translate raw captures at triage.
- **Absolute dates only.**
- **The human's voice** — preserve meaning, reasoning, emphasis; don't flatten into PM-speak.
- **Never delete** any entry; paused/discarded keep their reason.
- **State changes are command-gated physical moves** (sections / columns), never silent.
- **Epic status and rollups are derived from children**, never hand-set.
- **Recompute typed IDs; never reuse.**
- **Case-insensitive ID matching** across the git boundary.
- **Bookkeeping first; git execution opt-in; confirm before any merge/push.**
- **Re-read immediately before writing.**
- **Board references stories by ID; full entries live under their epic** — keep the two consistent.
- **Session start:** read all files, load silently, one-line orientation max.

---

## 17. File & folder structure

**Runtime (v1 — inside a host project; superseded by the v2.0 addendum, which moves this tree into
`<ledger-root>/<repo-slug>/`):**
```
Agile-Ledger/
├── Backlog.md           # 📥 Inbox + epics, each with its nested stories (shaping states + epic History)
├── Sprint.md            # current sprint: goal, board (To Do→In PR→Done), assignees, blocked flags, sync cursor
├── Sprints-History.md   # closed sprints + velocity (never-delete)
├── Releases.md          # 🚧 Increment (Done, unreleased) at top, then Major.Minor history (newest first)
├── Definitions.md       # DoD, DoR, INVEST, branch/commit/PR conventions, config (git opt-in, language)
└── Templates/           # epic · user-story · acceptance-criteria · task · pr-body · commit · delivery-note
```

**The installable skill (the repo you ship):**
```
agile-ledger-pro/
├── SKILL.md             # the rules "brain" (single source of truth)
├── README.md            # install guide
├── commands/            # 21 slash-command entry points
└── references/
    ├── Backlog.template.md
    ├── Sprint.template.md
    ├── Sprints-History.template.md
    ├── Releases.template.md
    ├── Definitions.template.md
    └── entry-templates.md   # epic / US / task / AC / pr-body / commit / delivery-note shapes
```

**Scaling:** the file split is the scaling strategy from day one (the §5 separation). If `Backlog.md`
grows large, the never-delete delivered history can spill into a `Delivered.md` per the v1 precedent.

---

## 18. Installation & distribution

- **Claude Code (primary):** drop `agile-ledger-pro/` into `.claude/skills/` (per project) or
  `~/.claude/skills/` (all projects); copy `commands/*` into `.claude/commands/`.
- **Claude.ai web/desktop:** upload a ZIP of the skill folder via Customize → Skills (`.skill` = that
  ZIP renamed).
- **One-command install:** a GitHub repo suffices for manual install; turn it into a **plugin
  marketplace** (`.claude-plugin/`) for `/plugin install`, which also ships the slash commands.
  Defer until test-driven, per the v1 plan.

---

## 19. Deliberately NOT included (and why)

- **Versioning at the story level.** Versioning lives **only at the epic level**. Delivered stories
  are one-and-done (never deleted, but not re-versioned); to change what a story did, write a *new*
  story under the epic, which rolls into the epic's version count. One clean versioning axis. *(Door
  left open if story-level history is ever wanted.)*
- **Tasks by default.** Off unless a story genuinely needs a sub-unit (§3).
- **The skill facilitating ceremonies.** It produces the material; humans run the conversation (§9).
- **Heavy metrics dashboards.** Velocity + the epic `vN` count are the two metrics that matter; resist
  burndown-chart sprawl. If rigor is added later, it must stay opt-in and never slow `/idea`.
- **Hard-coded provider/stack.** Detect or ask; pure-record mode (no git at all) stays valid.

---

## 20. Acceptance criteria (to validate the build)

- Fresh project → scaffolds all files with `Next free ID` per type and all sections/columns.
- `/idea` captures instantly in any language; `/triage` classifies epic-vs-story, assigns a typed ID
  + parent, rewrites in voice/English.
- `/detail-us` produces a Ready story with `As a/I want/So that`, Gherkin AC, Fibonacci estimate,
  layer, deps; INVEST + vertical-slice checks fire.
- `/plan-sprint` builds a sprint from Ready stories within velocity; `/board`, `/my-work`, and
  `/roadmap` render correctly.
- The lifecycle runs To Do → In Progress → In Review → In PR → Done with the right gates; `/close-sprint`
  records the Increment + velocity and returns unfinished stories to Ready.
- Branch/commit/PR follow the conventions; ID matching is case-insensitive; `/sync-main` flags
  merged-not-Done and merged-no-ID.
- An epic increment adds a new story, re-opens the epic, and closes a new `vN` on return to Done; the
  increment-vs-new-epic triage rule resolves correctly.
- `/release` cuts a `Major.Minor` from the Increment; `/changelog` derives notes; `/ledger-check`
  catches drift across the typed hierarchy.
- Nothing deleted; paused/discarded keep reasons; dates absolute; voice preserved; git execution
  opt-in and confirm-gated for merges.

---

## 21. Foundation / extension points

Agile-Ledger Pro is itself a base layer. The safe places to extend, keeping every invariant:
- **The typed ID hierarchy** — add a tier (e.g. `INITIATIVE-xxx` above epics) the same way: a new
  type with a parent pointer, never nested numbers.
- **The state machines** — new states stay *physical, command-gated moves*; never-delete holds.
- **The board** — a sixth column (e.g. QA) drops in if In Review/In PR prove overloaded.
- **The lenses** — new read-only views (`/velocity-chart`, `/epic <ID>`) as thin delegators.
- **Story-level versioning** — the one deliberate omission, addable without disturbing the epic axis.

Whatever the next idea is, the move is the same as v1's: **keep the invariants** — never-delete,
recompute IDs, absolute dates, the human's voice, confirm-before-push, derived epic status, the
bookkeeping-is-the-job / execution-is-optional split — and build on top of them, not around them.

---

## Addendum — v1.2: Backlog / User-Stories split (scaling)

As a project grows, a single `Backlog.md` holding every epic **and** every story's full Gherkin becomes
hard to read. v1.2 splits story detail out of the backlog. This **revises** the earlier decision that a
story's full entry lives co-located under its epic (right for small projects; replaced at scale).

- **`Backlog.md`** is now the **epic file**: epics + a one-line **index** of each story
  (`US-id · title · state · priority · pts · assignee`) + an **epic dashboard table** on top. It answers
  "what's being done or not" at a glance.
- **`User-Stories.md`** (new) holds the **full story detail**, grouped by state
  (`✅ Ready · 🏃 In Sprint · ✅ Delivered · ❄️ Paused · 🗑️ Discarded`) + a **state-summary table** on top.
- **📝 Draft** stories (triaged, not yet detailed) live **only** as an index line in `Backlog.md`.
  `/detail-us` writes the full entry into `User-Stories.md` and flips the index line to **Ready**.
- **Source of truth:** for Ready-and-beyond, the story detail and its lifecycle grouping live in
  `User-Stories.md`; the epic index line is a derived **mirror**; `Sprint.md` holds the fine board column
  while In Sprint; the epic index keeps the **coarse** state (`In Sprint`). `/ledger-check` reconciles
  index ↔ detail ↔ board and flags stale overview tables.
- **Files are now six** (added `User-Stories.md`). New scaffold template: `User-Stories.template.md`.

Commands that move a story's state (`/detail-us`, `/detail-epic`, `/plan-sprint`, `/done-us`,
`/close-sprint`) update the `User-Stories.md` grouping, mirror the epic index line, and refresh the
overview tables. The never-delete, recompute-IDs, human's-voice, and physical-move-equals-state
invariants all hold — the moves just happen in `User-Stories.md` for Ready-and-beyond.

---

## Addendum — v1.3: Bug tracking

Bugs don't behave like stories, so they get their own track — but they share the sprint board.

- **New file `Bugs.md`** + `Bugs.template.md`: bug reports grouped by state, with a dashboard table on
  top (state counts + open-by-priority). **New typed ID `BUG-001`** (recompute, never reuse). A bug
  *relates to* a story/epic (`[[US-xxx]]`), it is not a child of one.
- **Two axes:** **severity** (impact: critical/major/minor/trivial) and **priority** (when to fix). Bug
  **points are optional** (count toward velocity if set).
- **Bug states:** 🐛 Inbox → 🔍 Triaged → 🔬 Confirmed → 🛠️ In Sprint → ✅ Fixed (+ ❄️ Deferred, 🚫 Won't
  fix / Can't reproduce — kept with reason).
- **Commands (5 new):** `/bug` (capture), `/triage-bug` (id + severity + priority — kept separate from
  `/triage` so an empty bug Inbox costs no tokens), `/find-bug` (read-only investigation), `/start-bug`,
  `/done-bug`. `/review` and `/pr` accept a `BUG-ID` too.
- **`/find-bug` honesty guardrail:** fills steps-to-reproduce / expected / actual / assessment **only**
  when confirmed from code (`confirmed`) or supplied by the reporter (`reported`); otherwise
  `unconfirmed — needs input`, and it asks. Never invents a repro or root cause. Never edits code
  (read-only — the skill is for the PM).
- **Unified board (Option A):** `/plan-sprint` pulls Ready stories **and** triaged/confirmed bugs,
  highest priority first (a critical bug sits above stories); a critical bug is flagged pull-now (may
  interrupt the sprint). Bugs flow through the same columns with a `bug-xxx` branch and a `fix(...)
  (BUG-xxx)` commit.
- **Communication:** `/done-bug` feeds the Increment tagged **Fixed**; `/changelog` groups output into
  **Added/Changed** (stories) and **Fixed** (bugs); `/status` shows open bugs by severity/priority;
  `/sync-main` and `/ledger-check` are bug-aware.

Files are now **seven**. All other invariants hold.

---

## Addendum — v1.4: Ideas file + Epic-Backlog rename + command ergonomics

- **`Ideas.md` (new)** holds the 💡 idea inbox — `/idea` writes here. `/triage` reads `Ideas.md`,
  promotes each idea into `Epic-Backlog.md` (epic or story-index), and clears the line. Keeping raw
  ideas out of the backlog keeps the epic view clean.
- **`Backlog.md` → `Epic-Backlog.md`** (and `Backlog.template.md` → `Epic-Backlog.template.md`). It now
  holds only epics + the story index + the epic dashboard — no inbox.
- **"One command, one place"** — a phase → command → file map now sits in `SKILL.md` (and is printable
  via the new **`/guide`** command), so it's always clear where each command writes.
- **`argument-hint` placeholders** are set on every argument-taking command (e.g. `/detail-us <US-ID>`,
  `/bug <text>`), so Claude Code shows ghost-text for the expected input as you type the command.
- Files are now **eight**. Bug inbox stays inside `Bugs.md` (a dedicated file already).

---

## Addendum — v1.5: ID anchors & cross-file links (preview navigation)

The file split made detail live away from the index; v1.5 makes the IDs **clickable** so you navigate in
the Markdown preview without searching.

- **Bare-ID headings.** Each registered entry's heading is its **ID only** (`### EPIC-005`, `#### US-014`,
  `### BUG-014`); the title sits on the line just below. This yields a **stable lowercase anchor**
  (`#epic-005`, `#us-014`, `#bug-014`) that the preview generates automatically and that **survives a
  title rename**. (Verified: this works in GitHub and VS Code preview. Custom `<a id>` anchors were
  rejected — GitHub rewrites/lowercases them and VS Code's built-in preview often ignores them.)
- **Links everywhere the join key lives.** Story-index lines, a story's `Parent`, **`Dependencies`**, a
  bug's `relates to`, and sprint-board entries are written as relative links
  (`[US-014](User-Stories.md#us-014)`) so one click jumps to the full entry. Same-file refs may shorten
  to `[EPIC-005](#epic-005)`.
- **`/ledger-check` link audit.** Now also verifies every entry heading is a bare ID and every ID link
  resolves to an existing anchor in the named file — broken navigation is flagged like any other drift.
- The old `[[US-xxx]]` wiki notation is replaced by real Markdown links throughout the skill, commands,
  and templates.

Reading stays in the preview (click to navigate); changes stay in chat + commands.

---

## Addendum — v1.6: command-name cleanup

- **`/sweep` → `/workspace-sync`.** The cross-repo "what changed while I was away" command is now named
  for what it does; the old `/sweep` name is retired.
- **`/create-us` removed.** Stories are born at `/triage`: when an idea becomes a new epic, `/triage`
  now also proposes a few suggested 📝 Draft story-index lines under it (confirm-first); when an idea
  maps to an existing epic, it's added as a single Draft story. `/detail-us` (and `/detail-epic`) then
  give those stories their detail. Adding a story to an existing epic later goes through `/idea` →
  `/triage`. One entry path, one fewer command.

Command count: 31 commands + 1 alias (`/standup`).

---

## Addendum — v1.7: docs refresh + read-only command guards

- **Docs refreshed** to the current design: repo README and plugin README rewritten (eight files, the
  full current command set, ID-link navigation, `/workspace-sync`, no `/create-us`), Mermaid flow and
  file diagrams updated, and the one-page command cheat sheet regenerated and color-coded by group.
- **`allowed-tools` guards.** Read-only commands declare a tool whitelist so they physically cannot
  modify files: `/board`, `/standup`, `/status`, `/roadmap`, `/guide`, `/my-work`, `/changelog` →
  `Read, Grep, Glob`. `/find-bug` → `Read, Grep, Glob, Edit` (reads code, writes only the bug entry, no
  shell execution). `/sync-main` → read tools + ledger `Edit` + **only read-only git** subcommands
  (`git fetch/log/diff/status/branch/show`) — so it can never push, merge, or run arbitrary shell.
  Note: `allowed-tools` can't say "edit Markdown but not code", so `/find-bug`'s no-code-edit rule stays
  prompt-enforced; the guard it adds is the removal of shell execution.

---

## Addendum — v2.0: the ledger moves to its own repository

The one structural change since v1: **the ledger is no longer a folder inside the code repo.** It lives
in a dedicated **ledger repository** holding one folder per code repo.

```
<workspace-root>/
├── agile-ledger/                 # THE LEDGER REPO — its own git repo
│   ├── Registry.md               # marker + map: repo slug ↔ code path ↔ remote ↔ sync state
│   ├── Config.md                 # org, clone target, filters, commit/push policy, default repo
│   ├── repo-a/                   # the eight ledger files for repo-a
│   └── repo-b/
└── repo-a/ · repo-b/             # the code repos — no ledger files in them
```

**Why.** Two reasons, both from running v1 for months:

1. **A PM edit shouldn't reach a developer's branch.** With the ledger inside the code repo, every
   triage, board move, and release note is a commit on the branch the team is building on — so
   developers pull or rebase to receive bookkeeping that has nothing to do with their change, and PM
   commits interleave with code history.
2. **One place to look.** Ledger files for every project sit side by side in one repo you clone once.
   `/workspace-status` becomes a portfolio view that needs no code checked out at all, and the ledger
   repo's history is a clean record of PM decisions (`ledger(repo-a): US-014 → Done (sprint 7)`).

**Locked decisions**

| # | Decision | Choice |
|---|---|---|
| 1 | Placement | **Central ledger repo replaces** the in-repo folder. One model, not a configurable pair |
| 2 | Identifying a ledger root | A `Registry.md` whose first heading is `# Agile-Ledger Registry` — **never** the folder name |
| 3 | Finding the ledger from a code repo | **Walk up** from the cwd, checking each level *and its children*; stop at `$HOME`. Nothing is written into the code repo — no marker file, no config |
| 4 | Identifying the code repo | Normalized **git remote** matched against `Registry.md` (path and folder name are fallbacks only) |
| 5 | Scoping | `--repo <slug>` on any command; `default_repo` in `Config.md` when run from the ledger root |
| 6 | Ledger commits | `ledger_commit: confirm` (default) · `auto` · `off`; message `ledger(<slug>): <what changed>`; **`ledger_push: off`** by default and every push confirmed |
| 7 | Upgrade path | `/migrate-ledger` copies an in-repo folder across **verbatim**, verifies it, then offers to `git rm` it on a branch — never pushing |
| 8 | Cross-repo scope | Each repo folder keeps its own backlog, sprint, and velocity. Cross-repo references are links (`../repo-b/User-Stories.md#us-021`); there is no shared sprint |

**Commands.** `+/init-ledger`, `+/register-repo`, `+/migrate-ledger`, `+/ledger-commit`;
`/init-workspace` and `/bootstrap-repo` are retired (replaced by the first two). `/sync-main` and
`/workspace-sync` now read git in the **code** repo and write only in the **ledger** folder. Count: 33
commands + 1 alias (`/standup`).

**What did not change.** The ID system, the two state machines, the two-file story model, the overview
tables, anchors and links, duplicate detection, epic version control, estimation/velocity, vertical
slicing, the git/traceability conventions for code, and every never-delete / confirm-first invariant.
In-folder links between ledger files are unchanged, because the eight files are still siblings.

**Safety added.** Two new hard rules: **never write a ledger file into a code repo** (if a command is
about to, the resolution was wrong — stop and resolve again), and **migration copies and verifies before
anything is removed**, with per-file conflict reporting instead of a silent merge when both copies exist.
