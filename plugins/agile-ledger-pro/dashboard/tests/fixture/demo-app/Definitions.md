# Definitions & Config

> The team's shared rules and the skill's per-project configuration.

---

## Config

```
language: English
git_execution: off
estimation: fibonacci
Me: Nuno
```

---

## Definition of Ready (DoR) — gates Draft → ✅ Ready

A story is Ready when:
- [ ] It follows `As a <role>, I want <goal>, so that <benefit>` and is a **vertical slice**.
- [ ] Acceptance criteria are written in Given / When / Then and are testable.
- [ ] It has a Fibonacci estimate and a priority.
- [ ] Dependencies are identified, parent epic set.
- [ ] It passes **INVEST** and is small enough to finish within one sprint.

## Definition of Done (DoD) — gates In PR → Done

A story is Done when:
- [ ] All acceptance criteria pass.
- [ ] Code reviewed and merged to `main`.
- [ ] Tests added/updated and green.
- [ ] Docs updated if needed.
- [ ] No known regressions.
