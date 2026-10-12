# Bugs — report & track

> Bug reports for **demo-app**, grouped by state.

Next free ID — BUG: BUG-004

## Overview

🐛 Inbox 1 · 🔍 Triaged 1 · 🔬 Confirmed 1 · 🛠️ In Sprint 0 · ✅ Fixed 1 · ❄️ Deferred / 🚫 Won't fix 0

Open by priority: 🔴 2 · 🟡 1 · 🟢 0

_Every identified bug below, in section order; highest priority first within each group._

| ID | Title | State | Sev | Pri | Relates to | Assignee |
|---|---|---|---|---|---|---|
| [BUG-002](#bug-002) | Totals off by one cent | 🔍 Triaged | minor | 🟡 | — | — |
| [BUG-001](#bug-001) | Safari sign-in does nothing | 🔬 Confirmed | major | 🔴 | [US-002](User-Stories.md#us-002) | @leo |
| [BUG-003](#bug-003) | Avatar upload times out | ✅ Fixed | major | 🔴 | [US-001](User-Stories.md#us-001) | @rita |

---

## 🐛 Inbox

_Raw reports, newest first. No IDs. `/triage-bug` processes these._

- 2026-03-02 — the export button downloads an empty CSV when a filter is active

---

## 🔍 Triaged · 🔬 Confirmed

_Assessed bugs awaiting a sprint, highest priority first._

### BUG-001

**Safari sign-in does nothing** 🔬  ·  relates to [US-002](User-Stories.md#us-002)

- **Severity:** major
- **Priority:** 🔴
- **State:** Confirmed
- **Estimate:** 2
- **Reported by:** Nuno (2026-02-28)
- **Area:** auth
- **Assignee:** @leo

**Symptom** — (reporter's words) clicking "Sign in" on Safari does nothing.

**Steps to reproduce** _(confirmed)_

1. Open the login page in Safari 17.
2. Enter valid credentials and click "Sign in".

**Expected:** redirected to the dashboard.

**Actual:** button shows its pressed state, no request fires.

**Assessment** _(confirmed)_ — `onSubmit` is bound to a `<form>` Safari blocks; see `src/auth/LoginForm.tsx`.

**Notes:** —

### BUG-002

**Totals off by one cent** 🔍  ·  relates to —

- **Severity:** minor
- **Priority:** 🟡
- **State:** Triaged
- **Estimate:** —
- **Reported by:** Ana (2026-03-01)
- **Area:** billing
- **Assignee:** —

**Symptom** — (reporter's words) the invoice total is sometimes one cent off.

**Steps to reproduce** _(unconfirmed — needs input)_

**Expected:** —

**Actual:** —

**Assessment** _(pending /find-bug)_

**Notes:** —

---

## 🛠️ In Sprint

_Pulled onto the board. The live board column is in `Sprint.md`._

---

## ✅ Fixed

_Resolved. Kept forever with the fix line._

### BUG-003

**Avatar upload times out** ✅  ·  relates to [US-001](User-Stories.md#us-001)

- **Severity:** major
- **Priority:** 🔴
- **State:** Fixed
- **Estimate:** 3
- **Reported by:** Nuno (2026-01-30)
- **Area:** profile
- **Assignee:** @rita

**Symptom** — (reporter's words) uploading a photo spins forever.

**Steps to reproduce** _(confirmed)_

1. Open the profile page and upload a 4 MB JPEG.

**Expected:** the avatar updates within a few seconds.

**Actual:** the spinner never stops.

**Assessment** _(confirmed)_ — the upload handler had no timeout and retried forever.

**Fixed:** 2026-02-04 · sprint 2026-S02 · _(PR #31 · 9f8e7d6)_ · released in v1.0

**Notes:** —

---

## ❄️ Deferred / 🚫 Won't fix / Can't reproduce

_Kept with the reason._
