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
  `report_gap`, `describe`, `list_components`) with adapters for Astryx,
  shadcn/ui and a static JSON inventory.
- Decision ledger at `.specify/memory/design-decisions.yml`, consulted as
  rung 0 of the ladder and written after each walk. Alias-based matching so
  differently-worded lookups still hit; staleness detection via the recorded
  design system version.
- Companion preset composing a Design System Requirements section into
  `spec-template`, a Design System Check gate into `plan-template`, and the
  Reuse → Compose → Extend → Create principle into `constitution-template`.
- Config layering: extension defaults → project config → local override →
  `SPECKIT_DESIGNSYS_*` environment variables.

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
