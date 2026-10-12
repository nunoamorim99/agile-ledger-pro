# Reconstruction guide — git history → proposed backlog drafts

How to turn a repo's git history (or undocumented merges) into **proposals** in the Inbox. The output is
always Drafts for a human to `/triage` — never confirmed Epics/Stories, never Ready/Delivered.

## Hard guardrails (do not cross)

1. **Proposals only.** Everything lands in the target repo folder's `Ideas.md` **💡 Inbox**
   (`<ledger-root>/<repo-slug>/Ideas.md` — never inside the code repo), each line flagged `🔍 reconstructed from git (<commit/PR ref>) — needs review`.
2. **Never invent value or acceptance criteria.** Commit messages describe *implementation*, not user
   value. Do not fabricate a "so that…" or Given/When/Then. If the value is unclear, write
   `value: ?? (confirm at triage)` rather than guessing.
3. **No state beyond Draft.** Never write Ready, Delivered, estimates, or a `vN`. Even for already-merged
   work, propose a Draft tagged "delivered? confirm" — the human confirms at triage.
4. **Never overwrite human content.** If a commit/PR already maps to a registered `US-xxx`, skip it.
   Don't re-propose an item already drafted in a previous sync.
5. **Conservative over complete.** Better to under-propose than flood the Inbox. Skip noise.

## Clustering heuristics

**Prefer PRs over raw commits.** One merged PR ≈ one candidate User Story (it usually bundles a coherent
change). Use `gh pr list --state merged --json number,title,body,mergedAt,files …` where available; fall
back to merge commits in `git log`.

**Group into candidate Epics by theme/area:** cluster PRs by top-level directory or a shared subject
keyword (e.g. everything under `auth/`, or titles mentioning "billing"). A cluster of related stories
suggests a candidate Epic; propose it with `goal: ?? (confirm at triage)`.

**Signal vs. noise:**
- *Propose:* merged feature PRs; `feat:` commits; commits that add user-facing capability.
- *Usually skip:* `chore:`, `ci:`, `build:`, `style:`, dependency bumps, formatting, pure refactors with
  no behavior change — unless they cluster into something a PM would track.

**Brand-new repo (`--from-git`):** summarize the major areas into a few candidate Epics, and the notable
feature PRs/commits into candidate Stories under them. Aim for a readable starting backlog (roughly
3–8 epics, a handful of stories each), not a 1:1 dump of every commit.

**Ongoing sync (undocumented work):** for each merge to `main` since last sync with **no `[US-xxx]`**,
propose one Draft linked to that commit/PR, tagged "delivered, undocumented — confirm".

## Proposed-draft shape (in the Inbox)

```
- 2026-06-25 — 🔍 reconstructed from git (PR #142, commit a1b2c3d) — "Add Google SSO sign-in"
  area: auth · value: ?? (confirm) · likely status: delivered? · suggested parent epic: EPIC-?? (auth)
```

At `/triage` the human decides the four outcomes (exact / improved / related / new), assigns the real
typed ID, writes the value and AC in their own voice, and moves it to its proper state.
