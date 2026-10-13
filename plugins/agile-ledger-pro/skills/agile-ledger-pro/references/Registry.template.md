# Agile-Ledger Registry

> **This heading is the marker that identifies a ledger root** — the skill finds the ledger by looking
> for a `Registry.md` that starts with `# Agile-Ledger Registry`, never by folder name. Keep it as is.
>
> The repositories this ledger manages. One row per code repo, one folder per row. Written by
> `/register-repo`, `/discover-repos`, and `/workspace-sync`. **Never delete rows** — mark a repo
> `archived` or `gone` instead.

| Repo (folder) | Code path | Remote | Status | Last sync (SHA) | Last swept | Notes |
|---------------|-----------|--------|--------|-----------------|------------|-------|
<!-- | repo-a | ../repo-a | git@github.com:acme/repo-a.git | active | a1b2c3d | 2026-06-20 | | -->

**Columns**

- **Repo (folder)** — the folder in this ledger repo holding that project's eight ledger files. The slug
  is lowercase-hyphenated; it normally matches the repo name but does not have to.
  In a **flat** ledger (`layout: flat` — one that lives inside its own project), the eight files sit
  beside this file rather than in a subfolder, so the single row's folder is `.` and the project is
  named by the repo the ledger sits in.
- **Code path** — where the code is checked out, relative to this ledger root (`../repo-a`) or absolute.
  A convenience, refreshed when it goes stale; it is **not** the identity of the repo.
- **Remote** — the identity key. Matched normalized (no scheme, no credentials, no trailing `.git`,
  case-insensitive), so renaming or re-cloning a folder never loses the mapping.
- **Status** — `active` · `new` (registered, not yet in use) · `archived` · `gone` (remote no longer
  listed) · `local-only` (checked out but absent from the org scan).
- **Last sync (SHA)** — the `main` commit `/sync-main` last reconciled for that repo.
- **Last swept** — the date `/workspace-sync` last covered it.

**Default repo:** set `default_repo` in `Config.md` to decide which folder commands act on when they are
run from the ledger root itself.
