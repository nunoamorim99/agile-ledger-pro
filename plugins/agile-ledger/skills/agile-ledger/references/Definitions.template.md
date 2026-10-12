# Definitions & Config

> The team's shared rules and the skill's per-project configuration. Edit to fit your team.

---

## Config

```
language: English          # language the ledger is written in
git_execution: off         # off = generate branch/commit/PR text only; on = allow gh/git on confirmation
estimation: fibonacci      # story-point scale: 1, 2, 3, 5, 8, 13, 21
Me:                        # your name, used by /my-work when no name is given
```

> `git_execution: off` is the safe default. Even when `on`, the skill **never auto-merges** and always
> confirms before any push or merge. This key covers git in **this project's code repo**; a value set
> here overrides the ledger-wide default in the ledger root's `Config.md`. Commits in the **ledger repo**
> are governed separately by `ledger_commit` / `ledger_push` in that `Config.md`.

---

## Definition of Ready (DoR) — gates Draft → ✅ Ready

A story is Ready when:
- [ ] It follows `As a <role>, I want <goal>, so that <benefit>` and is a **vertical slice**.
- [ ] Acceptance criteria are written in Given / When / Then and are testable.
- [ ] It has a Fibonacci estimate and a priority.
- [ ] Dependencies are identified (linked, e.g. `[US-xxx](User-Stories.md#us-xxx)`), parent epic set.
- [ ] It passes **INVEST** and is small enough to finish within one sprint.

## Definition of Done (DoD) — gates In PR → Done

A story is Done when:
- [ ] All acceptance criteria pass.
- [ ] Code reviewed and merged to `main`.
- [ ] Tests added/updated and green.
- [ ] Docs updated if needed.
- [ ] No known regressions.

## INVEST (story-quality checklist for `/refine`)

**I**ndependent · **N**egotiable · **V**aluable · **E**stimable · **S**mall · **T**estable.
A story that only makes sense as "the backend half" or "the UI half" fails Independent + Valuable —
split it **vertically** instead.

---

## Git / traceability conventions

| Artifact | Shape |
|---|---|
| Branch | `us-014-google-sso` — lowercase, no type prefix, ID + slug |
| Commit | `feat(auth): add Google SSO sign-in (US-014)` — Conventional Commits, type kept |
| PR title | `Google SSO sign-in [US-014]` — no type, ID in brackets |

- IDs are matched **case-insensitively** across the git boundary.
- FE/BE sub-branches (`us-014-fe`, `us-014-be`) merge **into the US branch only**, never into main.
- **Squash-merge note:** a squash subject inherits the type-less PR title and won't parse as a
  Conventional Commit. Harmless to Agile-Ledger (changelog is ledger-derived); if your team relies on
  GitHub-side conventional-commit automation, keep the type on the squash subject.

Commit types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `perf`, `build`, `ci`, `style`.
