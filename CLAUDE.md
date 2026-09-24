A Spec Kit **extension** (`extension.yml`) plus a **preset** (`preset/`). Given an RFC, `/speckit.design.run` drives the Spec Kit workflow (clarify → specify → plan → implement → validate → fix) using the user's own design system as the source of truth. This repo holds no component knowledge; it asks the design system through adapters. Requires Spec Kit `>=1.0.0,<2.0.0`.

## Commands

```bash
pip install pytest pyyaml          # only test deps; Python 3.11 in CI
python -m pytest                   # all tests (pytest.ini: testpaths=tests, -q, --strict-markers)
python -m pytest tests/test_ledger.py::test_name   # single test
for f in scripts/bash/*.sh examples/*.sh; do bash -n "$f"; done   # shell syntax check (CI)
examples/setup-demo.sh /tmp/demo   # builds a demo project with the example "acme" design system
```

CI (`.github/workflows/ci.yml`) also has an `integration` job that installs `specify-cli`, runs `specify extension add --dev` and `specify preset add --dev` against a throwaway project, and asserts hooks are registered (`before_plan` must be non-optional), preset append-composition works, and the gate fails closed. Manifest or hook changes should be checked against that.

## Architecture

Three layers (details in `docs/architecture.md`):

- `commands/*.md`: agent-facing prose (judgement: when a ladder rung may be rejected, what counts as a finding). Edits here need no code.
- `scripts/python/design.py` (single ~2300-line file; `scripts/bash/ds.sh` is a shim that finds an interpreter and forwards): all mechanism. Inside it, `DesignSystem` carries the resolved `(root, config, adapter)` and caches the probe — build it with `DesignSystem.resolve()` and pass it, never the tuple. Dispatch splits on two axes: a **Transport** (`FileTransport`, `ProcessTransport`, `McpTransport`) says where bytes come from and whether they arrived; a **Strategy** (`KeyFieldLookup`, `WeightedSearch`, `SliceOnly`) says what they answer. A new way of asking is a class plus one entry in `TRANSPORTS` — never a branch in `run_capability`, which routes and nothing else. Every response is built by `Answer.unavailable` or `Answer.answered`, which is where the fail-closed rule is enforced rather than remembered. Subcommands: `gate`, `query`, `principles`, `context`, `workflow`, `rfc`, `ledger`, `cache`. Each emits exactly **one compact JSON object on stdout**; failures are JSON describing why, not non-zero exits, so command bodies can degrade instead of crash.
- `adapters/*.yml`: declarative maps from capability names (`search`, `component`, `tokens`, `principles`, ...) to a subprocess invocation or file read. Adapters may only map, never hold rules or component knowledge (enforced by `test_adapters_only_map_and_never_model`).

Hooks wired in `extension.yml`, not in the run command: `before_plan` → `design.check` (blocking, `optional: false`), `after_implement` → `design.validate`. There is deliberately no `after_specify` hook: the gate is the one place the design system is consulted before planning, and it also writes the spec's `## Design System Requirements`. `design.run` drives Spec Kit's own commands and lets the hooks fire; do not reimplement phases inside it.

The preset exists because extensions can only *replace* templates while presets can *append*; `preset/templates/*-addendum.md` compose design sections into spec/plan/constitution without forking them.

## Benchmarks

`benchmarks/` measures whether the extension improves outcomes: the same RFC in three arms (`unaided`, `speckit`, `extension`) against trimmed inventories of shadcn/Radix/MUI, scored by `benchmarks/harness/score.py` on five metrics. Two rules hold the suite up, both covered by `tests/test_benchmarks.py`:

- **Every arm gets the design system**, in the same path, described by the same `AGENTS.md`. Changing one arm's setup without the others voids the run.
- **Every metric is arm-neutral**: none may look for an artifact only the extension produces, or it measures which arm ran. Extension-only observations (design doc, gap records, ledger, validation rounds) are reported unscored.

Three output forms, so a claim can be stated: continuous metrics (scoring), pass/fail `checks` per run (`k/n` rates in the report), and `benchmarks/harness/judge.py` for blind pairwise preference. Judging is only worth anything blinded — implementation files only, tooling redacted, sides swapped, key outside the judge's directory — and a test fails on any giveaway in a bundle. Token and cost accounting is recorded per run and printed next to the scores; never report a win without it.

Cases (`benchmarks/cases/<id>/case.yml`) say what a good answer looks like per surface; `satisfied_by` names must exist in the system's inventory and cited principle ids must exist in whatever source is in force for that system (house file, or the default set for Radix). Never publish numbers this repo has not produced: no results are committed yet, and the READMEs say so.

## Invariants to preserve

- **Transports differ on whether the adapter is guessing.** `Fetched.shape_is_guessed` is true for a CLI (a shipped adapter guesses at the envelope, so a mapping that resolves to nothing hands back the whole payload) and false for a file (the adapter knows the file's shape, so the same miss means the section is genuinely absent). Collapsing the two turns "no principles in this inventory" into "here is the entire inventory".
- **A failure to ask is never "the design system has nothing."** Missing binary, outage, changed flag → `available: false`. Only an error code the adapter explicitly declares as not-found becomes `found: false`. `probe_adapter` spends a real call at gate time; the gate fails closed when unreachable.
- **The answer cache never changes what an answer means.** It lives in `DesignSystem.ask` (not `run_capability`), stores only `available: true` answers, never serves the probe (`fresh=True`), never replays a capability with `cacheable=False` (`extend`, `validate`, `report_gap`), and skips file-backed mappings. Scoped per feature, keyed on the whole adapter plus `cwd` and `design_system_version`. Call counts are kept even with caching off.
- **Principles resolve from exactly one source, never merged:** adapter CLI → shipped data file (`principles.source` or adapter file mapping) → `principles/default.yml`. `principles_source` names which (`cli` | `docs` | `default` | `unavailable`); `unavailable` means nothing answered and the fallback is off, which gating must fail closed on. Default set carries no colors/breakpoints/sizes.
- **A principle is enforceable only if it is normative and checkable** (MUST/SHOULD plus a `verify` step). Unenforceable ones are reported under `unenforceable`, never filtered out: the fix is a `verify` step at the source, not a quiet deletion.
- The vocabulary is Principles throughout, with no alias for the old one anywhere.
- **The Definition of Done is optional, authored, and never defaulted.** `resolve_dod` reads one project file (`definition-of-done.md` next to the config, or `dod.source`), never the design system, and no default set ships — that is what `test_no_dod_ships_in_this_repository` guards. Absent file means the validate step is skipped silently; only a *configured* path that does not resolve is reported (`DOD_ERROR`). It stays out of `.specify/memory/` because that directory is derived state that may be cleared and rebuilt, and a DoD cannot be rebuilt.
- **Context is focused, never restricted.** `build_context(phase)` must not push unasked components, but they must stay retrievable via `available_on_demand`/`retrieval`. Two tests hold this line; don't pass one by breaking the other.
- **Workflow position is derived from artifacts, no state file** (`workflow_status`): `[NEEDS CLARIFICATION]` in spec.md, `tasks.md` unticked boxes, `## Validation round N` headings, `- [ ] DS-F-nnn` finding checkboxes and a `## Verification` section in `design-system.md`. Every phase needs an artifact — `verify` was derived from the validate row instead, so it reported itself done and `next` skipped it. Those formats are a load-bearing contract with `commands/speckit.design.validate.md`. A round with ticked-off findings is not "clean". Rounds bounded by `max_validation_rounds` (3).
- **Ledger: one active decision per capability, one spelling per rung.** Committed, keyed by UI capability, recording the ladder's outcome: Reuse → Compose → Extend → Create (Recall is rung 0, which *reads* the ledger, so it is never a stored outcome). `resolution` is validated against `RESOLUTIONS` and normalized on the way in; a second active decision for a capability is refused unless it carries `supersedes`. The gate is the only writer — `run.md` verifies, it does not record — because the gate is the only place still holding the candidates and the reasoning.
- **Recall is scored by containment, not Jaccard.** Surfaces are named by capability, so lookups arrive as long descriptive phrases; measuring overlap against the union punished exactly that phrasing and Recall never fired for anyone following the docs. `score` divides by the shorter side.

## Testing notes

`tests/conftest.py` loads `design.py` via `importlib` as the `design` fixture and builds a minimal on-disk Spec Kit layout (`.specify/extensions/design/`, `.specify/feature.json`, `specs/<feature>/`). Tests are per-concern (`test_config`, `test_context`, `test_dispatch`, `test_principles`, `test_ledger`, `test_rfc`, `test_workflow`, `test_dod`, `test_cache`, `test_packaging`, `test_benchmarks`).

`tests/test_docs_consistency.py` is the odd one: it reads the shipped prose and checks it against the script — ledger examples name a real rung and survive validation, every gate key a command uses is one it declared and one the gate emits, the ladder and the state list are spelled the same way everywhere, one gap-record format. The command bodies are a layer a model acts on and nothing executes, which is where every defect found in review actually lived.

Project config lives at `.specify/extensions/design/design-config.yml` in the consuming project (template: `config-template.yml`); `adapter: auto` detects one.
