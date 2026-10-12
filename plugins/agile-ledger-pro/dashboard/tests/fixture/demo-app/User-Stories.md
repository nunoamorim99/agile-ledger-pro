# User Stories — detail

> Full detail for **Ready and beyond** stories, grouped by state.

## Overview

✅ Ready 2 (11 pts) · 🏃 In Sprint 1 (5 pts) · ✅ Delivered 1 (5 pts) · ❄️ Paused 0 (—) · 🗑️ Discarded 0 (—)

_Every story below, in section order; highest priority first within each group._

| ID | Title | State | Pri | Pts | Epic | Assignee |
|---|---|---|---|---|---|---|
| [US-005](#us-005) | Card checkout | ✅ Ready | 🟡 | 8 | [EPIC-002](Epic-Backlog.md#epic-002) | — |
| [US-003](#us-003) | Magic-link login | ✅ Ready | 🟡 | 3 | [EPIC-001](Epic-Backlog.md#epic-001) | — |
| [US-002](#us-002) | Google SSO login | 🏃 In Sprint | 🔴 | 5 | [EPIC-001](Epic-Backlog.md#epic-001) | @rita |
| [US-001](#us-001) | Email signup | ✅ Delivered | 🔴 | 5 | [EPIC-001](Epic-Backlog.md#epic-001) | @rita |

---

## ✅ Ready

_Detailed, Definition of Ready met, pullable into a sprint._

#### US-003

**Magic-link login** 💡  ·  Parent: [EPIC-001](Epic-Backlog.md#epic-001)

- **Priority:** 🟡
- **Estimate:** 3
- **Area:** auth
- **Layer:** fullstack
- **Assignee:** —

**Story** — As a returning user, I want a sign-in link by email, so that I don't have to remember a password.

**Acceptance criteria** _(Given / When / Then)_

- Given a registered email, when I request a link, then I receive one within 60 seconds.
- Given an expired link, when I open it, then I see a clear "link expired" screen with a resend button.

**Dependencies:** [US-001](User-Stories.md#us-001)

**Notes:** —

#### US-005

**Card checkout** 💡  ·  Parent: [EPIC-002](Epic-Backlog.md#epic-002)

- **Priority:** 🟡
- **Estimate:** 8
- **Area:** billing
- **Layer:** fullstack
- **Assignee:** —

**Story** — As a team admin, I want to pay by card, so that I can start without contacting sales.

**Acceptance criteria** _(Given / When / Then)_

- Given a valid card, when I submit checkout, then the subscription activates immediately.

**Dependencies:** —

**Notes:** —

---

## 🏃 In Sprint

_Pulled into the current sprint. The live board column is in `Sprint.md`._

#### US-002

**Google SSO login** 🏃  ·  Parent: [EPIC-001](Epic-Backlog.md#epic-001)

- **Priority:** 🔴
- **Estimate:** 5
- **Area:** auth
- **Layer:** fullstack
- **Assignee:** @rita

**Story** — As a new user, I want to sign in with my Google account, so that I don't have to create another password.

**Acceptance criteria** _(Given / When / Then)_

- Given a valid Google account, when I tap "Sign in with Google", then I land on the dashboard authenticated.
- Given a cancelled Google prompt, when I return, then I see the login screen with no error state.

**Dependencies:** [US-001](User-Stories.md#us-001)

**Notes:** —

---

## ✅ Delivered

_Shipped. Kept forever with the delivery line._

#### US-001

**Email signup** ✅  ·  Parent: [EPIC-001](Epic-Backlog.md#epic-001)

- **Priority:** 🔴
- **Estimate:** 5
- **Area:** auth
- **Layer:** fullstack
- **Assignee:** @rita

**Story** — As a visitor, I want to sign up with an email and password, so that I can start using the product.

**Acceptance criteria:** all met ✓

**Dependencies:** —

**Delivered:** 2026-01-20 · sprint 2026-S01 · _(PR #12 · a1b2c3d)_ · released in v1.0

**Notes:** —

---

## ❄️ Paused / 🗑️ Discarded

_Deferred or rejected, kept with their reason._
