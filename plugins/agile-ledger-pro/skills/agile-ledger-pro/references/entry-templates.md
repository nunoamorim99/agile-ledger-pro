# Entry templates

Exact shapes the skill scaffolds. Copy and fill; do not re-derive. All ledger text in English, dates
absolute (`YYYY-MM-DD`), the human's voice preserved.

> **Readability rule.** Tuned for the rendered Markdown preview: every metadata field is its own
> **bulleted line**, and logical sections are separated by a **blank line** (a single line break is
> ignored by Markdown and collapses lines into one paragraph). Keep the blank lines — including the one
> before a bulleted list that follows a **bold:** label. Never rely on trailing-space breaks; they are
> lost when an entry is rewritten.

> **Linking & anchors (stable, rename-proof).** Each entry's heading is its **bare ID** — `### EPIC-005`,
> `#### US-014`, `### BUG-014` — so the preview auto-generates a stable lowercase anchor (`#epic-005`,
> `#us-014`, `#bug-014`) that does **not** change when the title changes. The human-readable **title goes
> on the line just below** the heading. Reference any item with a relative link to its file + anchor:
> `[US-014](User-Stories.md#us-014)`, `[EPIC-005](Epic-Backlog.md#epic-005)`, `[BUG-014](Bugs.md#bug-014)`.
> Anchor = the ID **lowercased** (hyphen kept). Story-index lines, `Parent`, `Dependencies`, bug
> `relates to`, and sprint-board entries all use these links so a click jumps straight to the detail.
> `/ledger-check` verifies every link resolves. (This works in GitHub and VS Code preview; custom
> `<a id>` anchors are avoided because they are unreliable across viewers.)

---

## Overview tables (top of each file)

**`Epic-Backlog.md` — epic dashboard** (the Epic cell links to the epic heading in the same file):

```markdown
| Epic | Title | Status | Stories (done/total) | Points (done/total) | Target |
|---|---|---|---|---|---|
| [EPIC-005](#epic-005) | User onboarding | 🔨 In Progress | 4/7 | 18/34 | v3.0 |
```

**`User-Stories.md` — roll-up line + story index.** The roll-up gives the numbers at a glance; the
index table below it lists **every** story so the reader can jump straight to any entry from the top of
the file. The ID cell links to the entry's anchor in the same file; the Epic cell links across to
`Epic-Backlog.md`.

```markdown
✅ Ready 8 (34 pts) · 🏃 In Sprint 5 (21 pts) · ✅ Delivered 30 (142 pts) · ❄️ Paused 1 (3 pts) · 🗑️ Discarded 2 (—)

| ID | Title | State | Pri | Pts | Epic | Assignee |
|---|---|---|---|---|---|---|
| [US-031](#us-031) | Magic-link login | ✅ Ready | 🟡 | 3 | [EPIC-005](Epic-Backlog.md#epic-005) | — |
| [US-014](#us-014) | Google SSO login | 🏃 In Sprint | 🔴 | 5 | [EPIC-005](Epic-Backlog.md#epic-005) | @rita |
| [US-012](#us-012) | Email signup | ✅ Delivered | 🔴 | 5 | [EPIC-005](Epic-Backlog.md#epic-005) | @rita |
```

**`Bugs.md` — roll-up line + bug index.** Same idea. Severity and priority are separate columns because
they are separate axes; `Relates to` links the story the bug came from (`—` when standalone).

```markdown
🐛 Inbox 2 · 🔍 Triaged 3 · 🔬 Confirmed 1 · 🛠️ In Sprint 2 · ✅ Fixed 14 · ❄️ Deferred / 🚫 Won't fix 1

Open by priority: 🔴 2 · 🟡 3 · 🟢 1

| ID | Title | State | Sev | Pri | Relates to | Assignee |
|---|---|---|---|---|---|---|
| [BUG-014](#bug-014) | Safari sign-in does nothing | 🔍 Triaged | major | 🔴 | [US-002](User-Stories.md#us-002) | — |
| [BUG-009](#bug-009) | Totals off by one cent | 🛠️ In Sprint | minor | 🟡 | — | @rita |
| [BUG-003](#bug-003) | Avatar upload times out | ✅ Fixed | major | 🔴 | [US-021](User-Stories.md#us-021) | @rita |
```

**Rules for both index tables** (and the epic dashboard):

- **Every item gets a row, forever** — Delivered / Fixed / Discarded rows are never dropped, so every
  anchor stays reachable from the top of the file. Nothing is ever deleted.
- **Row order follows the file's own section order** (active work first, done last):
  `Ready → In Sprint → Delivered → Paused → Discarded` for stories;
  `Inbox → Triaged → Confirmed → In Sprint → Fixed → Deferred/Won't fix` for bugs.
  Within a group, highest priority first, then ID ascending.
- 🐛 **Inbox bugs have no ID yet** — they are counted in the roll-up but have no table row until
  `/triage-bug` assigns an ID.
- 📝 **Draft stories are not in `User-Stories.md`** at all, so they get no row here; they appear only as
  an index line under their epic in `Epic-Backlog.md`.
- Unknown / not-yet-set cells are `—`, never invented or left blank.
- The table is **derived, never hand-typed** — it is rebuilt from the entries below it whenever a
  command changes an item's state, priority, estimate, assignee, or title. `/ledger-check` flags any
  row that disagrees with its entry, plus missing or orphaned rows.

---

## Epic (in `Epic-Backlog.md`)

Heading is the bare ID; title on the next line. Story-index lines link each `US-id` to its detail.

```markdown
### EPIC-005

**User onboarding** 🔨  ·  target v3.0 · 4/7 stories · 18/34 pts

**Goal:** get a new user from signup to first value in under 2 minutes.

**Area:** onboarding

**History:**

- v1 (2026-02-10) — initial onboarding — US-012, US-013, US-014 — released in v1.4
- v2 (2026-04-22) — social login added — US-031 — released in v1.7

**Stories:**

- [US-012](User-Stories.md#us-012) · Email signup · ✅ Delivered · 🔴 · 5 pts · @rita
- [US-014](User-Stories.md#us-014) · Google SSO login · 🏃 In Sprint · 🔴 · 5 pts · @rita
- [US-031](User-Stories.md#us-031) · Magic-link login · ✅ Ready · 🟡 · 3 pts
- [US-048](User-Stories.md#us-048) · Guided setup checklist · 📝 Draft · 🟢
```

- Status emoji is **derived from children**: 💡 Proposed · 🔨 In Progress · ✅ Done · ❄️ Paused · 🗑️ Discarded.
- Rollup recomputed, never hand-typed. New `vN` appended each time the epic returns to Done after Done.
- A reconstructed epic adds, as its own block: `🔍 _Reconstructed from git — confirm at triage._`
- 📝 Draft stories live **only** as an index line here (no detail yet). Index-line state is coarse
  (`Draft · Ready · In Sprint · Delivered · Paused · Discarded`); the live board column is in `Sprint.md`.

---

## User Story — full entry (in `User-Stories.md`)

Grouped under a `## ✅ Ready` / `## 🏃 In Sprint` / `## ✅ Delivered` / `## ❄️ Paused` / `## 🗑️ Discarded`
heading. Bare-ID heading, title below, `Parent` and `Dependencies` are links.

### open (Ready)

```markdown
#### US-014

**Google SSO login** 💡  ·  Parent: [EPIC-005](Epic-Backlog.md#epic-005)

- **Priority:** 🔴
- **Estimate:** 5
- **Area:** auth
- **Layer:** fullstack
- **Assignee:** —

**Story** — As a new user, I want to sign in with my Google account, so that I don't have to create
another password.

**Acceptance criteria** _(Given / When / Then)_

- Given a valid Google account, when I tap "Sign in with Google", then I land on the dashboard authenticated.
- Given a cancelled Google prompt, when I return, then I see the login screen with no error state.

**Dependencies:** [US-009](User-Stories.md#us-009) (auth service)

**Notes:** —
```

### delivered

```markdown
#### US-014

**Google SSO login** ✅  ·  Parent: [EPIC-005](Epic-Backlog.md#epic-005)

- **Priority:** 🔴
- **Estimate:** 5
- **Area:** auth
- **Layer:** fullstack
- **Assignee:** rita

**Story** — As a new user, I want to sign in with my Google account, so that I don't have to create another password.

**Acceptance criteria:** all met ✓

**Dependencies:** [US-009](User-Stories.md#us-009)

**Ready:** 2026-06-02

**Started:** 2026-06-10

**Delivered:** 2026-06-18 · sprint 2026-S12 · _(PR #142 · a1b2c3d)_ · released in v2.1

**Notes:** —
```

> **The flow dates.** `Ready:` is written by `/detail-us` (Draft → Ready), `Started:` by `/start-us`
> the first time a story enters In Progress, `Delivered:` by `/done-us`. They sit in that order, just
> above Delivered, and each is written only when it happens — an entry from before they existed
> stays exactly as it is. Ready → Delivered is **lead time**; Started → Delivered is **cycle time**.
> Bugs carry the same idea as `Triaged:` (`/triage-bug`), `Started:` (`/start-bug`) and `Fixed:`.
> Epics carry `**Created:**` (written by `/triage`, after `Area`). On the board, an item pulled in
> after planning ends `· pulled 2026-06-20`, and a 🚧 Blocked line ends `· since 2026-06-20` — that
> date never moves when the reason is edited, because blocked time is counted from the first flag.

### paused / discarded

```markdown
#### US-021

**Magic-link login** ❄️  ·  Parent: [EPIC-005](Epic-Backlog.md#epic-005)

- **Status:** Paused (2026-05-03)
- **Reason:** waiting on the new email provider decision.

**Story** — As a … I want … so that …
```

### reconstructed from git (proposal)

Same shape; source flagged as its own block; unknowns left explicit (never invented):

```markdown
#### US-002

**Portal staff auth (dual-JWT, refresh, RBAC)** 💡  ·  Parent: [EPIC-002](Epic-Backlog.md#epic-002)

- **Priority:** 🔴
- **Estimate:** —
- **Area:** auth
- **Layer:** backend
- **Assignee:** —

🔍 _Reconstructed from git — confirm at triage._

**Story** — value: ?? (confirm at triage)

**What shipped** — `/auth/login|refresh|logout|me|change-password`; JwtAuthGuard + RolesGuard.

**Delivered:** ~2026-04 (reconstructed) · src/modules/core/ (auth) · confirm at triage

**Notes:** —
```

---

## Bug (in `Bugs.md`)

Severity = impact (`critical / major / minor / trivial`); priority = when to fix (🔴🟡🟢). `/find-bug`
fills the investigation fields **only** when confirmed from code (`confirmed`) or supplied by the reporter
(`reported`); otherwise `unconfirmed — needs input`. States: 🐛 Inbox · 🔍 Triaged · 🔬 Confirmed · 🛠️ In
Sprint · ✅ Fixed · ❄️ Deferred · 🚫 Won't fix.

```markdown
### BUG-014

**Login button unresponsive on Safari** 🔬  ·  relates to [US-002](User-Stories.md#us-002)

- **Severity:** major
- **Priority:** 🔴
- **State:** Confirmed
- **Estimate:** 2
- **Reported by:** Nuno (2026-06-28)
- **Area:** auth
- **Assignee:** —

**Symptom** — (reporter's words) clicking "Sign in" on Safari does nothing.

**Steps to reproduce** _(confirmed)_

1. Open the login page in Safari 17, enter valid credentials, click "Sign in".

**Expected:** redirected to the dashboard.

**Actual:** button shows pressed state, no request fires.

**Assessment** _(confirmed)_ — suspected root cause: `onSubmit` bound to a `<form>` Safari blocks; see `src/auth/LoginForm.tsx`.

**Notes:** —
```

Fixed: header emoji ✅ and add `**Fixed:** 2026-07-02 · sprint 2026-S13 · _(PR #151 · 9f8e7d6)_ · released in v2.2`.

---

## Task (optional)

```markdown
- **TASK-031** — Wire OAuth callback endpoint · _Parent:_ [US-014](User-Stories.md#us-014) · _Layer:_ backend · _Assignee:_ leo
```

A work split, not a unit of value. Used only for FE/BE two-developer splits or unplanned sub-work.

---

## Acceptance criteria — Gherkin (the only format)

```markdown
- Given <context>, when <action>, then <observable outcome>.
- Given <edge context>, when <action>, then <safe outcome / no error>.
```

Behaviour, not implementation. Binary pass/fail so a developer can self-verify "done" async.

---

## PR body (generated by `/pr`)

```markdown
## Google SSO sign-in [US-014]

**Story** (US-014 · EPIC-005 User onboarding):
As a new user, I want to sign in with my Google account, so that I don't have to create another password.

### Acceptance criteria
- [ ] Given a valid Google account, when I tap "Sign in with Google", then I land on the dashboard authenticated.
- [ ] Given a cancelled Google prompt, when I return, then I see the login screen with no error state.

### How to test
1. …

### Definition of Done
- [ ] Acceptance criteria all pass
- [ ] Code reviewed
- [ ] Tests added/updated and green
- [ ] Docs updated if needed

Closes US-014.
```

PR **title**: `Google SSO sign-in [US-014]` (no type prefix). Branch: `us-014-google-sso` (lowercase).
For a bug: title `Fix Safari login [BUG-014]`, body `Fixes BUG-014`, branch `bug-014-safari-login`.

---

## Commit (Conventional Commits — type kept)

```
feat(auth): add Google SSO sign-in (US-014)
fix(auth): bind submit handler for Safari (BUG-014)
```

`type(scope): subject (ID)` — types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `perf`, `build`,
`ci`, `style`. The `(ID)` suffix is the traceability join key.

---

## Delivery note (the GitHub-PR equivalent captured in the ledger)

```markdown
US-014 delivered 2026-06-18 — sprint 2026-S12

- **What changed:** Google sign-in via OAuth; new /auth/google callback; login screen button.
- **How to test:** see PR #142.
- **AC:** all checked.   **DoD:** met.   **PR #142 · commit a1b2c3d.**
```
