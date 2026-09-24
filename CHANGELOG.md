# Changelog

All notable changes to this extension are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Answer cache.** The design system's CLI or MCP answers are remembered per
  feature (`.specify/extensions/design/.cache/`, gitignored), so a run asks
  each question once instead of once per phase, task and validation round.
  Failures are never remembered, the gate's reachability probe is always a real
  call, and `extend`, `validate` and `report_gap` are never replayed.
  Configured under `cache` (`enabled`, `ttl_minutes`); overridable with
  `SPECKIT_DESIGN_CACHE_ENABLED` and `SPECKIT_DESIGN_CACHE_TTL_MINUTES`.
- **A short path through the ladder.** A surface that an earlier decision
  answers (Recall), or that one search and one look at a component covers
  (Reuse), is resolved there, recorded in a short form without a candidate
  table. The full walk, with candidate tables, a final search and a gap
  record, is reserved for Compose, Extend and Create: strict about what goes
  in, light on how things are used, after the contribution process of Meta's
  [Astryx](https://github.com/facebook/astryx/wiki/Contributing).
- **Lab components.** What Create builds is a lab component: in the project,
  from the system's tokens and primitives, scoped to the feature, and marked
  as not part of the design system with a pointer to its gap record. Whether
  it joins the design system is for the system's owners to decide.
- **`ds.sh scan`.** The mechanical half of validation: literal colours,
  lengths and font stacks in the implementation (with file and line), token
  names the contract or spec asks for that the design system does not have,
  and contract tokens written nowhere in the code. Files that define the tokens
  are exempt through the new `validation.theme_globs`. Every validation round
  starts from it, so the review spends its attention on what needs a reader.
- **A place for the design brief in the RFC.** An optional
  `## Design guidelines` section in the RFC template, free text, for what a
  team pastes from its guidelines: light or dark, which variant, which tokens.
  `ds.sh rfc` returns it as `sections.design` under the usual headings,
  German ones included (Design-Vorgaben, Gestaltung, Styleguide). The run
  saves the RFC as `rfc.md` next to the spec (`FEATURE_RFC` in the gate), the
  gate turns each instruction into a `DS-` requirement with the token that
  delivers it, and `ds.sh scan` checks its token names too.
- **Call count.** `ds.sh cache stats` reports how often the design system was
  actually asked and how often memory answered instead, per capability, kept
  whether or not caching is on. `ds.sh cache clear` starts the feature over.

### Removed

- **`/speckit.design.context` and its `after_specify` hook.** The design
  system is now consulted once before planning, by the gate: it resolves the
  principles, tokens and breakpoints, walks the ladder, and writes the spec's
  `## Design System Requirements` in one pass. Before, the context hook
  searched every surface and the gate searched it again. Anyone driving Spec
  Kit by hand gets the same spec section before planning starts, one step
  later than before. The spec addendum's candidates table is gone with it:
  resolutions live in `design-system.md` only.

### Changed

- The gate checks every token name the spec or its RFC asks for against the
  design system's token list, and marks a name it does not have as
  `[NEEDS CLARIFICATION]` rather than substituting the nearest one.
- **Validation is one full review and one fix round.** `max_validation_rounds`
  defaults to 2, down from 3. Round 1 reviews the whole change; round 2 checks
  only the fixes, what they touched, the scan and the tests. When the last
  allowed round's findings have been ticked off, `workflow status` now says
  `stop` rather than asking for a round the bound refuses.
- **Verify is part of the clean round.** The round with no findings checks the
  change against the RFC's acceptance criteria and writes `## Verification` in
  the same pass, instead of a separate phase that re-read everything. `next:
  verify` remains only for a clean round that omitted the section.
- `gate.min_candidates_considered` applies only where a surface lands on
  Extend or Create. Reuse and Compose use what exists and need no quota; the
  quota used to pad candidate tables for components used exactly as documented.
- For a Reuse surface, the constraints carried into the plan refer to the
  component's own documentation instead of copying it, and spell out only what
  the feature adds.

## [0.1.0] - 2026-09-23

First release. It carries the first cut (2026-09-20, at the end of this
section), the review that followed it, and the packaging for the Spec Kit
community catalog.

### Packaging for the community catalog

#### Added

- `.extensionignore`: `specify extension add` no longer copies `tests/`,
  `benchmarks/` and repository tooling into the consuming project. Everything
  a run reads or executes still ships, which `tests/test_packaging.py` checks.
- `requires.tools` in `extension.yml` names what every run executes: `python3`
  (>=3.9, with PyYAML) and `bash`. The design system CLI is still deliberately
  not declared.
- A release workflow: pushing a `vX.Y.Z` tag checks that the tag, both
  manifests and this changelog agree, runs the tests, and publishes the GitHub
  release with this file's section as its notes.
- `docs/publishing.md`: the release checklist and the prepared Extension
  Submission for the Spec Kit community catalog.

#### Changed

- The README installs from the release archive instead of a clone, and gains
  Troubleshooting, Contributing and Support sections.

### Fixed — from the pre-1.0 review

- **A principle may apply to more than one kind.** `applies_to: [interactive,
  layout]` raised `unhashable type: 'list'`. The gate resolves principles
  without kinds, so it never hit the branch: it went on reporting the
  principles as present and authoritative while the phase that writes them into
  the spec got an error envelope carrying no `principles_source` at all. Every
  command stops on `REACHABLE` or `principles_source`, so an envelope with
  neither slipped past both guards. `applies_to` now takes a scalar or a list,
  and a refusal — from `die` or from an unexpected error — is shaped for
  whoever is about to read it, so the existing guards fire.

- **One active ledger decision per capability, one spelling per rung.**
  Following the two command bodies produced two contradicting active decisions
  for one surface: `check.md` recorded when the gate walked it and `run.md`
  recorded it again at verify, under a different vocabulary
  (`compose-components` against `compose`, `decided_in` against `feature`).
  `resolution` is now validated and normalized, the feature field has one name,
  a second active decision is refused unless it supersedes, and the gate is the
  only writer.

- **Recall works for the phrasing the ladder insists on.** Overlap was measured
  against the union of the token sets, so a capability phrase — the style the
  method requires — scored 0.167 against a 0.34 threshold while the
  component-shaped name it forbids scored 1.0. Rung 0 never fired for anyone
  following the documentation. Overlap is now measured against the shorter
  phrase; unrelated surfaces still score 0.

- **`verify` is a phase rather than a restatement of `validate`.** It was
  derived from the same condition, so it reported itself done the moment
  validation passed and `next` went straight to `done` — and the run command
  tells the agent to follow `next`. Verify now records a `## Verification`
  section in `design-system.md` and the phase is derived from it.

- **`context.includes` names only keys the response carries.** It advertised
  `rfc`, `spec` and `plan`, which this command never inlines, and
  `named_components` for a section delivered as `components`. The artifacts a
  phase reads for itself are reported as `read_from_artifacts`.

- **Settings that did nothing are named.** `gate.enforce`,
  `gate.min_candidates_considered`, `ledger.enabled` and
  `validation.forbid_raw_values` are enforced by the command bodies rather than
  the script, which is now stated in `docs/architecture.md` instead of implied
  by the phrase "a gate that blocks".

- **One vocabulary across the artifacts.** Recall was missing from the
  manifests and from the constitution addendum; three command bodies used gate
  keys they never told the agent to parse; the state list dropped `empty` in one
  of four places; the README taught a second gap-record format, titled by
  component name under the rule against exactly that. `config-template.yml` now
  documents the `ledger.*`, `gate.*` and `validation.*` keys the README already
  claimed it held.

- **The unreachability diagnostic points somewhere useful.** The troubleshooting
  table sent the reader to `ds.sh query describe`, which six of the eight
  shipped adapters do not map — including the one `adapter: auto` falls back to.

### Changed — architecture

- **Capability dispatch splits into transports and strategies.**
  `run_capability` was one function with five jobs in it — routing, two
  transports, three query strategies and envelope construction — at 234 lines
  and cyclomatic complexity 63. It is now 38 lines of routing at complexity 7.
  A **transport** (`FileTransport`, `ProcessTransport`, `McpTransport`) says
  where the bytes come from and whether they arrived; a **strategy**
  (`KeyFieldLookup`, `WeightedSearch`, `SliceOnly`) says what they answer.

- **An MCP transport, which the README has promised from the start.** It could
  not be written while dispatch was one function, because there was no seam to
  add it at. The call is delegated to a client command the adapter names — this
  extension ships no MCP client and should not grow one — and everything
  downstream is identical to a CLI mapping, including the failure semantics.

- **`DesignSystem` replaces the `(root, config, adapter)` tuple** that was
  threaded through nine functions and rebuilt at the top of every subcommand.
  It caches the probe, so a phase transition no longer pays for two identical
  round-trips.

- **`Answer.unavailable` / `Answer.answered`** replace thirteen hand-built
  result dicts whose shape had already drifted: six failure paths carried no
  `bytes`, the file-backed paths no `result_path_missed`.

- **A `Capability` registry** replaces a name list, a positional-argument map
  in `cmd_query`, a probe-parameter dict and a ladder map that could drift
  apart; the last three are derived from it.

- **`workflow_status` decides by an ordered rule table** rather than a nine-arm
  `elif` chain that mixed what each phase means with which one wins.

- `Answer.cost_note` moved onto the class that owns the fields it reads, and
  the repeated tokens/breakpoints fetch in `build_context` became one helper.
  The breakpoints-answered-with-the-token-payload report, which the cost
  accounting depends on, had no test and now has two.

- Named constants for the timeouts, result caps and truncation lengths that
  were inline numbers, and adapter detection now reports a `package.json` it
  could not read (`DETECTION_NOTES` in the gate) instead of silently falling
  through to `static-json`.

### Removed

- **The config carry-forward for a version that was never released.**
  `migrate_config` mapped `rules.*` and `audit.*` onto the current keys so an
  existing project would survive an upgrade — from a "pre-0.2" that does not
  exist at version 0.1.0, for projects that cannot exist because nothing has
  ever been released. It also contradicted the policy this changelog states
  three paragraphs down for the `guidelines:` rename. One rule now: a key this
  extension does not document is a key it does not read, and a retired key is
  left untouched rather than quietly reinterpreted.

- `ledger.revalidate_when_stale` and the unused `PHASES` constant.

### Added

- `tests/test_docs_consistency.py`: the command bodies are a layer a model acts
  on and nothing executes, which is where every defect above actually lived. It
  parses the shipped prose and checks it against the script.

### Changed — BREAKING

- **Guidelines are now Principles, everywhere.** A design system states
  principles; holding it to a word it does not use made the extension read like
  a second opinion rather than a reader of its rules. The rename is mechanical
  but it is not cosmetic: the vocabulary is what every generated spec, plan and
  validation round carries.

  | Was                                     | Is now                                     |
  | --------------------------------------- | ------------------------------------------ |
  | `guidelines/default.yml`, `example.yml` | `principles/default.yml`, `example.yml`     |
  | adapter capability `guidelines`         | `principles`                                |
  | config block `guidelines:`              | `principles:`                               |
  | `ds.sh guidelines`                      | `ds.sh principles`                          |
  | `GUIDELINES_*` in the gate              | `PRINCIPLES_*`                              |
  | payload `source` / `rules` / `rule_count` | `principles_source` / `principles` / `principle_count` |
  | source `adapter` / `none`               | `docs` / `unavailable`                      |
  | default ids `GL-*`                      | `PRIN-*`                                    |

  No alias, no carry-forward: a config that still says `guidelines:` is simply
  not read. Nothing has been released against the old vocabulary, so keeping it
  alive would cost more than it could ever save.

### Added

- **Optional Definition of Done.** A team that keeps one writes it as a plain
  markdown list in `.specify/extensions/design/definition-of-done.md`; validation
  checks each item against what was built and raises unmet ones as ordinary
  `DS-F-nnn` findings, so they run through the existing fix loop rather than a
  mechanism of their own. Surfaced as `DOD_ITEMS` and `DOD_SOURCE` in the gate.

  Three decisions worth stating, because each is the opposite of how principles
  work: **nothing ships as a default**, and nothing ever will — the default
  principles are defensible because they cite WCAG, and there is no comparable
  authority for what a team calls done, so a shipped set would raise findings
  against rules nobody at that project agreed to. **The design system is never
  asked** — no capability, no adapter mapping; a DoD is what a team decided
  among themselves. **No file is the normal case**, not a degraded one: absent,
  the step is skipped in silence rather than gating, warning or nagging. A
  `dod.source` that is configured and does not resolve is the one case that is
  reported (`DOD_ERROR`), because silence there would leave a team believing
  their rules were being enforced.

  It lives next to the config rather than in `.specify/memory/`, where the
  ledger sits, because it is authored rather than derived. The ledger can be
  rebuilt from the design system, so clearing that directory is a reasonable
  thing to do; a DoD cannot be rebuilt from anything, and must not be collateral.
- Each principle reports `enforceable`: it states a MUST or SHOULD **and**
  carries a `verify` step — specific, testable, mapped to a verification.
  Anything else comes back under `unenforceable` and is never dropped, because
  what it needs is a `verify` step rather than deletion. Specs cite only what
  can be checked; the rest is named as a gap in the principles themselves.
- `principles_version` carries the revision the source states, and `null` where
  it states none. An invented version would make a citation taken against last
  quarter's principles look like one that was checked.
- `principles_source: unavailable` says outright that nothing answered and the
  fallback is switched off, so a gate that requires principles fails closed
  rather than passing on an empty set.
- Each principle may carry a `title`; the default set now does.
- `DESIGN_DOC` records **Principles that apply** per surface, which is what the
  validate phase reads back: a principle that applies and appears nowhere is a
  finding, and so is the missing line.

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
- A capability can name its own `bin`. `extend` and `report_gap` are the two
  most design system CLIs do not have, because they are usually another tool's
  job — a gap is filed in an issue tracker, a component is ejected by a codegen
  tool — and mapping them previously meant writing a wrapper script, which is
  how rungs 4 and 5 stay unmapped on systems that could support them. A
  file-backed adapter can map them too, giving a static inventory a write side.
  Such a capability is invoked on its own terms: the adapter's `global_args` and
  `envelope` belong to the design system's CLI and are not applied to it.
- `ds.sh gate --json` reports `LADDER_SUPPORT`: per rung of the reuse ladder,
  what backs it and whether the design system can be asked. `extend` and
  `report_gap` are the mappings most CLIs cannot provide, and a rung walked on
  documentation alone should be visible at gate time rather than inferred.

- `benchmarks/`: a suite for measuring whether the extension produces better
  work, rather than asserting it. The same RFC runs in three arms — the agent
  alone, the agent with Spec Kit, the agent with the extension — against trimmed
  inventories of shadcn/ui, Radix UI and MUI, and is scored on five
  deterministic, arm-neutral measures: inventory fidelity, ladder outcome, token
  discipline, principle coverage and criteria traceability. Four cases, one per
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

- `.gitattributes` pins every tracked file to LF. Git for Windows converts on
  checkout by default, and a converted `ds.sh` is not executable on Linux at
  all: the shebang resolves to `bash\r`, so the loader reports a missing
  interpreter rather than a converted file. The extension installs by copying
  this repository into a project, so the conversion travelled with it. A test
  now fails on CRLF in the index; an existing checkout is refreshed with
  `git rm --cached -r . && git reset --hard`.
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

### First cut — 2026-09-20

What the extension does, as first written down.

#### Added

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
  `breakpoints`, `principles`, `validate`, `extend`, `report_gap`, `describe`,
  `list_components`.
- Principles resolve from exactly one source, never merged: the design
  system's CLI, then static data it ships, then the small default set in
  `principles/default.yml` (14 rules, no colors, breakpoints or sizes).
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

#### Behaviour worth knowing

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

#### Deliberately not built

Issue import and export. The catalog already covers both directions
(`github-issues`, `issue` and `gh-triage` inbound; core
`speckit.taskstoissues` plus `jira`, `linear` and `azure-devops` outbound).
The ledger sits in `.specify/memory/` because `memory-loader` already loads
that directory into agent context.

[Unreleased]: https://github.com/artursopelnik/spec-kit-design-system/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/artursopelnik/spec-kit-design-system/releases/tag/v0.1.0
