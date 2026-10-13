# Converting a pre-2.0 ledger to the eight files

`/migrate-ledger` does two jobs, and they are not the same job:

1. **Relocation** — the in-repo `Agile-Ledger/` folder moves into the ledger repo. Placement only.
2. **Conversion** — a ledger written against an older file layout is reshaped into the eight files.

v2.0 changed only *where* the ledger lives, so a team already on v1.4+ needs step 1 and nothing
else. A team on an earlier v1 needs both, because the file layout itself changed during v1. Copying
such a ledger verbatim leaves a folder the skill cannot read: a `Backlog.md` sitting where
`Epic-Backlog.md`, `User-Stories.md`, `Ideas.md` and `Bugs.md` are expected.

## Step 1 — detect the era before doing anything

Decide from the files actually present, not from what the team says they run.

| Files in `Agile-Ledger/` | Era | Conversion needed |
|---|---|---|
| `Ideas.md` · `Epic-Backlog.md` · `User-Stories.md` · `Bugs.md` (+ the other four) | v1.4 – v1.7 | **None.** Relocate verbatim. |
| `Backlog.md` · `User-Stories.md` · `Bugs.md`, no `Ideas.md` | v1.3 | Rename + lift the Inbox out |
| `Backlog.md` · `User-Stories.md`, no `Bugs.md` | v1.2 | …and scaffold `Bugs.md` |
| `Backlog.md` alone, story detail nested inside it | v1.0 – v1.1 | …and split the story detail out |

Then confirm by content, because a folder can be half-upgraded by hand: open `Backlog.md` and check
whether stories under an epic are **full entries** (story sentence, acceptance criteria, estimate) or
**one-line index entries**. Full entries mean the v1.0 split is still pending, whatever the filenames
suggest.

State the detected era and the per-file plan, then **wait for confirmation**. Never convert silently.

## Step 2 — the rules that govern every conversion

1. **Copy first, convert second, remove last.** The verbatim copy into `<ledger-root>/<slug>/` and its
   verification both finish before any reshaping. The code repo's folder is removed only after the
   conversion is done and checked — and only on a branch, on confirmation, as always.
2. **Relocate text; never rewrite it.** Conversion moves blocks of Markdown between files. The words,
   dates, IDs, estimates, assignees and the author's voice stay exactly as the team wrote them. Never
   re-number an ID, never re-date an entry, never tidy a story sentence, never translate.
3. **Nothing is dropped.** Every non-empty line of a converted file lands somewhere. Anything that
   cannot be classified goes under a final `## ❓ Unsorted from migration` heading in the file it came
   from — visible, kept, and obvious at the next `/ledger-check`. Losing a line is worse than leaving
   it unsorted.
4. **Derived data is rebuilt, never carried.** Overview tables, the roll-up lines and epic rollups are
   regenerated from the entries once the split is done. A v1.0 file may not have had them at all; an
   old one is almost certainly stale after a split.
5. **Invent nothing.** A missing estimate, priority, severity or acceptance criterion stays missing —
   write `—`. `/ledger-check` and `/refine` will surface the gaps afterwards, which is the honest
   outcome. A migration that fills blanks is a migration that fabricates history.
6. **One confirmation per destructive-looking step**, and a report at the end saying what moved where.

## Step 3 — splitting `Backlog.md`

Work section by section, top to bottom.

- **`## 📥 Inbox`** (raw captures, no IDs) → the `## 💡 Inbox` section of `Ideas.md`, lines verbatim.
  Keep their order and their dates. If a line has no date, leave it undated rather than guessing one.
- **Each epic block** → stays in `Epic-Backlog.md`, keeping its goal, area and history.
- **Story detail nested under an epic** → moves to `User-Stories.md`, under the `##` group matching
  its state, and the epic keeps a **one-line index entry** pointing at it:
  `- [US-014](User-Stories.md#us-014) · Google SSO login · ✅ Ready · 🔴 · 5 pts · @rita`
  Fill the index line only from what the entry actually says; omit a field it does not have.
- **A story with no detail** (a title and a state, nothing more) is a 📝 Draft: it gets an index line
  under its epic and **no entry** in `User-Stories.md`. That is the v2 model, not a loss.

Map the v1 shaping state onto the v2 section:

| v1 state | `User-Stories.md` section |
|---|---|
| 📝 Draft | *(none — index line only)* |
| ✅ Ready | `## ✅ Ready` |
| 🏃 In Sprint | `## 🏃 In Sprint` |
| ✅ Delivered / Done | `## ✅ Delivered` |
| ❄️ Paused | `## ❄️ Paused` |
| 🗑️ Discarded | `## 🗑️ Discarded` |

If a story's state is unreadable, put it in `## ✅ Ready` only when it plainly has acceptance criteria
and an estimate; otherwise leave it a Draft index line and say so in the report. Do not infer a state
from a sprint it is no longer in.

## Step 4 — headings and links

v1.5 introduced the **bare-ID heading** that makes anchors survive a rename. Older entries look like
`### EPIC-005 — User onboarding`. Convert those to the v2 shape:

```markdown
### EPIC-005

**User onboarding** 🔨  ·  target v3.0 · 4/7 stories · 18/34 pts
```

This is the **one** rewrite migration performs on a heading line, and it is required — without it the
`#epic-005` anchor does not exist and every cross-link breaks. Say so in the report.

Then fix the link targets the rename invalidated: `Backlog.md#us-014` → `User-Stories.md#us-014`,
`Backlog.md#epic-005` → `Epic-Backlog.md#epic-005`. Those are mechanical and safe. Any other broken
link is **reported, not repaired** — a link pointing somewhere that never existed is information.

## Step 5 — the files that did not exist yet

- **`Ideas.md`** (new in v1.4) — scaffold from the template, then fill it from the old `## 📥 Inbox`.
- **`Bugs.md`** (new in v1.3) — scaffold from the template, empty.
  If the team tracked bugs inside `Backlog.md` — an epic called "Bugs", a list of defects — **do not
  convert them automatically.** A v1 bug line has no severity and no priority, and rule 5 forbids
  inventing them. Report what you found, leave it where it is, and tell the user `/triage-bug` will
  register each one properly with the two axes it needs.
- **`Templates/`** (retired in v2.0) — the entry shapes now live in the skill's `references/`. Carry
  the folder across so nothing is lost, and say in the report that it is inert and can be deleted
  whenever the team is ready. Do not delete it for them.

## Step 6 — verify, then report

Run the `/ledger-check` audit over the converted folder and include its findings in the report. Expect
old Drafts with no estimate and stories with no acceptance criteria — those are real gaps in the old
ledger that the split has merely made visible. Report them; fix nothing without being asked.

The report says, at minimum: the era detected, which files were created, how many ideas, epics,
stories and bugs landed where, anything left in `## ❓ Unsorted from migration`, every heading
rewritten to a bare ID, and what `/ledger-check` still flags.

## Re-running

Safe to re-run. If the target folder already holds files, stop and report the conflict per file as
usual — never merge two ledgers silently. A conversion that was confirmed and completed does not need
repeating; a half-finished one is resumed by resolving the reported conflicts first.
