# Changelog

All notable changes to this extension are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Adapters can carve a capability's answer out of a response it shares with a
  larger one: `result_paths` (candidate dotted paths, first hit wins) and `pick`
  (keep only these keys). Most design systems have no breakpoint command, so
  `breakpoints` is mapped onto the token call; without a slice it answered with
  the entire token payload, and every phase that asked for breakpoints paid for
  the tokens twice.
- Every capability result reports `bytes`, and `ds.sh context <phase>` reports
  `sizes` per section plus a total. A capability answering with 50 KB previously
  looked exactly like one answering with 50.
- `ds.sh context` notes an answer that came back unnarrowed — `breakpoints`
  answering with the same payload `tokens` just answered with, a mapped
  `result_path` that resolved to nothing, or a payload past 8 KB — naming the
  adapter keys that would narrow it. Reported, never trimmed: dropping half a
  token set would make the agent confidently wrong, which is worse than an
  expensive run.
- `ds.sh query <capability> --fields name,description`: the caller's own trim
  for surveying a large answer such as a full inventory, with
  `bytes_unprojected` reporting what the untrimmed answer would have cost. The
  full record stays one call away.
- `ds.sh gate --json` reports `LADDER_SUPPORT`: per rung of the reuse ladder,
  what backs it and whether the design system can be asked. `extend` and
  `report_gap` are the mappings most CLIs cannot provide, and a rung walked on
  documentation alone should be visible at gate time rather than inferred.

- `benchmarks/`: a suite for measuring whether the extension produces better
  work, rather than asserting it. The same RFC runs in three arms — the agent
  alone, the agent with Spec Kit, the agent with the extension — against trimmed
  inventories of shadcn/ui, Radix UI and MUI, and is scored on five
  deterministic, arm-neutral measures: inventory fidelity, ladder outcome, token
  discipline, guideline coverage and criteria traceability. Four cases, one per
  RFC kind, each with the code the RFC is about. No results are published yet;
  the suite ships the apparatus.
- Benchmark results in the three forms a claim actually takes: seven pass/fail
  checks per run, reported as `k/n` per arm; token, cost, turn and wall-clock
  accounting read from the agent's own output (or a `usage.json` any agent can
  write), printed beside the scores rather than omitted; and
  `benchmarks/harness/judge.py`, blind pairwise judging of two runs with the
  arms hidden, the tooling redacted, the sides swapped, and a tally that
  unblinds only at the end.
- `examples/setup-demo.sh --system shadcn|radix|mui [--case <id>]`: the demo
  project can now be wired to one of those inventories, with a benchmark case's
  RFC and starting code, instead of the Acme fixture.

### Fixed

- Prose or empty output from a CLI adapter written for JSON is now
  `available: false` / `found: false` instead of `found: true` with garbage, so
  a changed flag no longer passes the gate.
- A non-mapping inventory file, or `search` without a query, no longer crashes
  or dumps the whole inventory.
- Unexpected exceptions and refusals (`die`) now also emit JSON on stdout; a
  closed pipe no longer raises.
- Gate probe times out after 30s rather than 120s.
- `ledger record` accepts inline JSON; `rfc` warns when a path-like argument
  does not exist.

## [0.1.0] - 2026-09-20

First release.

### Added

- `/speckit.design.run <rfc>`: takes an RFC (a file, stdin or text) and carries
  it through clarify, specify, plan, implement, validate, fix and verify. It
  stops for exactly three things: an open question that changes what gets
  built, an unreachable design system, or findings that survive the round
  limit.
- Three phase commands that also fire as Spec Kit hooks: `context`
  (`after_specify`), `check` (`before_plan`, blocking) and `validate`
  (`after_implement`).
- Adapters, each a declarative map from the capability contract onto a CLI call
  or a file read: `shadcn`, `mui`, `antd`, `chakra`, `radix`,
  `ark-ui`, `static-json`, and an `example` template. The library adapters
  read a generated inventory file, since those libraries have no query CLI.
  `adapter: auto` picks one from the project.
- Capability contract: `search`, `component`, `pattern`, `tokens`,
  `breakpoints`, `guidelines`, `validate`, `extend`, `report_gap`, `describe`,
  `list_components`.
- Guidelines resolve from exactly one source, never merged: the design
  system's CLI, then static data it ships, then the small default set in
  `guidelines/default.yml` (14 rules, no colors, breakpoints or sizes).
- Focused context per phase via `ds.sh context <phase>`: only what applies,
  with `available_on_demand` and `retrieval` listing everything else still
  reachable.
- `ds.sh workflow status`: workflow position derived from the artifacts on
  disk, with no run-state file, so an interrupted run resumes by reading.
- `ds.sh rfc <path|->`: normalizes an RFC into sections, open questions and
  whether it bears UI.
- Bounded validate → fix → validate. Findings are appended to
  `design-system.md` as `## Validation round N` with `- [ ] DS-F-nnn` entries.
  A round whose findings were merely ticked off does not count as clean.
  `workflow.max_validation_rounds` defaults to 3.
- Decision ledger at `.specify/memory/design-decisions.yml`, keyed by UI
  capability and consulted before the ladder, with staleness detection via the
  recorded design system version.
- Companion preset that appends a Design System Requirements section to
  `spec-template`, a Design System Check gate to `plan-template`, and the
  Reuse → Compose → Extend → Create principle to `constitution-template`.
- Config layering: extension defaults, project config, gitignored local
  override, then `SPECKIT_DESIGN_*` environment variables.
- Rung-5 gaps are written as standalone `design-system-gap-<slug>.md` RFC files
  that can travel to another team or tracker unchanged.
- `templates/rfc-template.md`, `docs/{architecture,adapters,autonomous-workflow}.md`
  and a runnable demo (`examples/setup-demo.sh`) built on a fixture design
  system.

### Behaviour worth knowing

- **The gate fails closed.** It probes the design system rather than trusting
  the adapter file, so an unreachable CLI reports no capabilities and stops
  the gate.
- **A failed call is never reported as an empty result.** Only an error code
  the adapter explicitly declares as "not found" counts as an answer.
  Otherwise an outage would read as "the design system has nothing" and push
  the ladder toward Create.
- **Unknown staleness is not freshness.** Without a current design system
  version to compare against, lookups report `staleness_checked: false` and
  leave `stale` null.

### Deliberately not built

Issue import and export. The catalog already covers both directions
(`github-issues`, `issue` and `gh-triage` inbound; core
`speckit.taskstoissues` plus `jira`, `linear` and `azure-devops` outbound).
The ledger sits in `.specify/memory/` because `memory-loader` already loads
that directory into agent context.

[Unreleased]: https://github.com/artursopelnik/spec-kit-design-system/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/artursopelnik/spec-kit-design-system/releases/tag/v0.1.0
