# Ledger Config

> Ledger-wide configuration, sitting beside `Registry.md` at the root of the ledger repo. Per-project
> rules (Definition of Done / Ready, estimation scale, your name) stay in each repo folder's
> `Definitions.md` — this file is only about the ledger itself and the repos it manages.

```
default_repo:   <repo-slug>                # which folder commands act on when run from the ledger root
org:            <github-org-or-owner>      # the GitHub org/owner scanned via `gh repo list`
clone_target:   ../                        # where new repos are cloned, relative to this ledger root
include:        []                         # optional repo-name globs to include (empty = all)
exclude:        [archived, forks]          # skipped from register proposals (still listed, marked)
ledger_commit:  confirm                    # confirm (default) | auto | off — commits in THIS repo
ledger_push:    off                        # off (default) | confirm — pushing is never automatic
ledger_branch:  main                       # the branch ledger commits land on
git_execution:  off                        # off = branch/commit/PR text only, on = allow git in CODE repos
setup_branch:   agile-ledger-setup         # branch used in a code repo to remove a migrated ledger folder
```

## Notes

- **`ledger_commit`** governs commits **in this ledger repo**: `confirm` offers one commit per command
  (`ledger(repo-a): US-014 → Done (sprint 7)`), `auto` commits without asking, `off` leaves the working
  tree dirty for you to commit yourself with `/ledger-commit`.
- **`ledger_push`** is separate on purpose. Even at `confirm`, every push is confirmed at the moment it
  happens; the skill never force-pushes and never rewrites ledger history.
- **`git_execution`** is the older, code-repo switch: branches, commits, and `gh pr create` in the
  **project** repo. It stays `off` by default and never merges.
- **Clone target.** `../` puts clones beside the ledger repo, which is the layout the resolver expects:
  one workspace root holding the ledger repo and the code repos as siblings.
- **Authentication.** Discovery uses your existing `gh` CLI session (`gh auth status`). The skill never
  asks for, stores, or handles tokens.
- **`exclude`** only reduces noise in proposals. Because registering is always propose-then-confirm,
  excluded repos are still listed (marked) so you can opt one in.
