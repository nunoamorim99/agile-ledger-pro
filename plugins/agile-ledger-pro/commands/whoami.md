---
description: (Ledger) Say who you are on this ledger — the one thing each person sets up for themselves
argument-hint: [name|@handle]
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---
Using the **Agile-Ledger Pro Workspace** skill, record who the person at *this clone* is, in `Me.local.md` at the ledger root.

This is the whole of a joiner's setup. A Product Manager creates the ledger and writes the team into `Config.md`; everyone else clones it and runs this. **Do not re-run `/init-ledger`'s questions for them** — the placement, the org, the roster and the rules are already decided, and asking again invites a second answer to a question the team has settled.

## Why this is a separate file

`Me:` in a project's `Definitions.md` is committed with every other line in that file. One person's name written there reaches everybody who clones the ledger, and the next person to fix it overwrites the first — and if the team has put `Definitions.md` under `CODEOWNERS`, a developer cannot land the correction at all. `Me.local.md` sits at the ledger root, holds one person, and is ignored by git, so every clone answers for itself.

## 1. Resolve, then check whether this is already answered

Resolve the ledger root first (see **Where the ledger lives**). Then:

- **No ledger root** → this person has nothing to join. Say so and offer `/init-ledger`.
- **`Me.local.md` already names someone** → say who, in one line (`You are Rita Soares (@rita) on this machine — Me.local.md`), and stop. Re-run with an argument to change it.
- **`$ARGUMENTS` given** → take it as the answer, match it against the roster, and skip to step 3. A bare `@handle` and a display name are both fine.

## 2. Work out who they are, then ask

Read the `## Team` roster from the ledger root's `Config.md` and try, in this order:

1. `gh api user --jq .login` → match against the roster's GitHub column. This is the strong one: `gh` is authenticated as them, so the handle is theirs and not a guess.
2. `git config user.name` → match against the Name column, exactly, then case-insensitively.
3. `git config user.email` → match the part before the `@` against the GitHub column.

**Exactly one match → propose it and wait for a yes.** Never record an identity the person has not confirmed: steps 2 and 3 read self-declared git settings, a shared machine gives the wrong answer, and a wrong `Me` quietly shows somebody else's sprint. Say which signal matched, so they can see why you think so (`Your gh login is @rita, which is Rita Soares on the roster — is that you?`).

**No match, or more than one → list the roster** (name · role · handle) and ask which one they are. Offer *not on the roster* as a real answer. Without `gh` or a shell, skip straight to this; say the list is from `Config.md` rather than pretending you detected anything.

**No roster at all** (a solo ledger, or one written before the `## Team` section existed) → just ask for their name. Offer to start a roster only if they say they have a team.

## 3. Write it

Write `Me.local.md` at the **ledger root** — one per ledger, not one per project — from the `agile-ledger-pro` skill's `references/Me.local.template.md`, filling `name` and `handle`. A handle alone is enough when the roster supplies the name, and the reverse too; write both when you know both.

Then **make sure git ignores it.** Append `Me.local.md` to `<ledger-root>/.gitignore`, creating the file if it is not there. The ledger root is the right place in both placements: git honours a `.gitignore` in a subdirectory, so a flat ledger inside its project never needs the project's own file touched. Skip this only if an existing pattern already covers it. **Never commit `Me.local.md`** — if `ledger_commit` is `auto`, exclude it from the commit and say you did.

Report in one line what was written and that it stays on this machine.

## 4. When they are not on the roster

Record the local identity anyway — `/my-work` should work for somebody nobody has listed yet — and then say plainly what is missing: until they have a row in `## Team`, they are not offered as an assignee and nobody can assign them work from the dashboard.

Adding that row is an edit to `Config.md`, which is the file a team most often puts under `CODEOWNERS`. So offer the two honest routes and let them choose:

- **Ask the `PO`/`PM` to add the row** — one line, and it is their file.
- **Open a PR against the ledger** adding the row themselves, for the owner to approve.

Do not write the row and claim it is done if the ledger's branch is protected; the push will be refused and the person will think they are on the team when they are not. If you do add it locally, say it still has to land.

## 5. Stop conditions

Never write `Me.local.md` anywhere but the resolved ledger root. Never write a name into a project's `Definitions.md` as part of this command — that is the shared file this exists to stop people fighting over. Never state that a role carries a permission: the roster is a label, and `CODEOWNERS` plus branch protection is the only thing that enforces anything (see **Roles are a roster, not permissions**).
