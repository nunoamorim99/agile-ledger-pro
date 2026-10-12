# Contributing

## Repository layout — one source of truth

**Everything lives in `plugins/agile-ledger-pro/`. Edit only there.**

That single directory feeds all three install paths:

| Install path | How it gets the files |
|---|---|
| Marketplace (`/plugin install agile-ledger-pro@nunoamorim99-pro`) | Served directly from `plugins/agile-ledger-pro/` |
| Manual `.claude/` drop-in | `agile-ledger-pro-<version>.zip`, built from it on release |
| Claude.ai web/desktop | `agile-ledger-pro-skill-<version>.zip`, built from it on release |

A marketplace plugin's root is a hard boundary — paths above `plugins/agile-ledger-pro/` are not copied
into the plugin cache on install — so the files must physically live inside the plugin. The manual
bundles are therefore *built* from it rather than kept as a second committed copy.

### Building the bundles

```sh
python3 scripts/build_bundles.py           # writes dist/*.zip
python3 scripts/build_bundles.py --check   # build, then assert the contents (this is what CI runs)
```

`dist/` is gitignored — the zips are release artifacts, never committed. The full bundle nests
commands one level deeper than the plugin does (`commands/agile-ledger-pro/idea.md`), because a manual
install namespaces commands by directory while a plugin namespaces them by plugin name. Both end up
as `/agile-ledger-pro:idea`.

## Cutting a release

1. Bump `version` in **both** manifests (see [Versioning](#versioning) below).
2. Commit and push to `main`.
3. Tag and push:

   ```sh
   git tag v1.0.1 && git push origin v1.0.1
   ```

The `release` workflow verifies the tag matches `plugin.json`, builds both bundles, and attaches them
to a GitHub Release. A mismatched tag fails the build rather than publishing a misleading version.

## Versioning

The version appears in two manifests and must match in both:

- `.claude-plugin/marketplace.json` — `metadata.version` and the plugin entry's `version`
- `plugins/agile-ledger-pro/.claude-plugin/plugin.json` — `version`

CI verifies that the marketplace entry and `plugin.json` agree on both `name` and `version`.

## CI

[`.github/workflows/validate.yml`](.github/workflows/validate.yml) runs on every push and pull
request:

1. Both plugin manifests parse as JSON.
2. The marketplace entry resolves to a real plugin directory, names and versions agree, and the
   required `commands/` and `skills/agile-ledger-pro/SKILL.md` are present.
3. Both install bundles build and contain the files each one is supposed to ship.

[`.github/workflows/release.yml`](.github/workflows/release.yml) runs on a `v*` tag and publishes the
bundles to GitHub Releases.

## Ledger file conventions

The shapes the skill scaffolds and maintains are specified in
[`entry-templates.md`](plugins/agile-ledger-pro/skills/agile-ledger-pro/references/entry-templates.md).
Two rules are easy to miss when adding a command:

- **Overview tables are derived, never hand-typed.** Any command that changes an item's state,
  priority, estimate, assignee, or title must rebuild the roll-up counts **and** that item's row in
  the index table at the top of the file.
- **Nothing is ever deleted.** Delivered, Fixed, and Discarded items keep their entry and their
  overview row forever, so every anchor stays reachable.
