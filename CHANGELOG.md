# Changelog

All notable changes to this extension are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial extension scaffold: `designsys` extension with four commands
  (`sync`, `check`, `audit`, `gap`) and three hooks (`after_specify`,
  `before_plan` blocking, `after_implement`).
- Capability contract (`search`, `component`, `pattern`, `tokens`, `extend`,
  `report_gap`, `describe`, `list_components`), with a worked Astryx adapter and
  a static JSON fallback for design systems with no CLI.
- Decision ledger at `.specify/memory/design-decisions.yml`, consulted as
  rung 0 of the ladder and written after each walk. Alias-based matching so
  differently-worded lookups still hit; staleness detection via the recorded
  design system version.
- Companion preset composing a Design System Requirements section into
  `spec-template`, a Design System Check gate into `plan-template`, and the
  Reuse → Compose → Extend → Create principle into `constitution-template`.
- Config layering: extension defaults → project config → local override →
  `SPECKIT_DESIGNSYS_*` environment variables.
- Rung-5 gaps are written as standalone `design-system-gap-<slug>.md` RFC files
  so they can travel to another team or tracker unchanged, rather than living
  as a section inside the feature's design doc.

### Verified

- Installs via `specify extension add --dev` and `specify preset add --dev`
  against Spec Kit `1.0.9.dev0`, with config materialization and hook
  registration confirmed in `.specify/extensions.yml`.
- `strategy: append` composes all three templates without losing core content.
- `pytest` suite over the Python module, plus a CI job that repeats the real
  install on every push and weekly on a schedule.

### Removed before first release

- Every adapter for a named design system, `shadcn` and then `astryx`. Neither
  was ever run against the real CLI, so both were guesses written from vendor
  documentation. A stale guess in `adapters/` looks authoritative while being
  wrong, and when it breaks it looks like a defect in this extension. What ships
  instead is `static-json`, which needs no CLI and is fully tested, and
  `example.yml`, a template with a placeholder binary and invented flags so it
  cannot be mistaken for something that runs. The capability contract is the
  product; the default adapter is now `static-json`.
- The `--refresh` flag, which was documented in two commands and implemented in
  none. The `describe` capability it was meant to drive is real and still
  reachable; nothing rewrites an adapter automatically, because silently editing
  committed repository content would hide a breaking upstream change rather than
  surface it.

### Deliberately not built

Issue import and export. The catalog already covers both directions:
`github-issues`, `issue` and `gh-triage` inbound; core `speckit.taskstoissues`
plus `jira`, `linear` and `azure-devops` outbound, so the gap RFC is shaped to
be carried by whichever of those a project already runs. The ledger sits in
`.specify/memory/` for the same reason: `memory-loader` already loads that
directory into agent context.

### Behaviour worth knowing

- **The gate fails closed.** `check-design-gate.sh` probes the design system
  rather than trusting the adapter file, so an unreachable CLI reports no
  capabilities and stops the gate. A gate that passes when it cannot check
  anything would be worse than no gate.
- **A failed call is never reported as an empty result.** Only an error code the
  adapter explicitly declares as "not found" counts as an answer; anything else
  is a failure to ask. Otherwise a registry outage would read as "the design
  system has nothing" and push the ladder toward Create.
- **Unknown staleness is not freshness.** Without a current design system
  version to compare against, lookups report `staleness_checked: false` and
  leave `stale` null rather than implying a prior decision was verified.

[Unreleased]: https://github.com/artursopelnik/spec-kit-design-system
