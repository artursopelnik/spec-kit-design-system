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
- `scripts/python/design.py` (single ~1400-line file; `scripts/bash/ds.sh` is a shim that finds an interpreter and forwards): all mechanism. Subcommands: `gate`, `query`, `guidelines`, `context`, `workflow`, `rfc`, `ledger`. Each emits exactly **one compact JSON object on stdout**; failures are JSON describing why, not non-zero exits, so command bodies can degrade instead of crash.
- `adapters/*.yml`: declarative maps from capability names (`search`, `component`, `tokens`, `guidelines`, ...) to a subprocess invocation or file read. Adapters may only map, never hold rules or component knowledge (enforced by `test_adapters_only_map_and_never_model`).

Hooks wired in `extension.yml`, not in the run command: `after_specify` → `design.context`, `before_plan` → `design.check` (blocking, `optional: false`), `after_implement` → `design.validate`. `design.run` drives Spec Kit's own commands and lets the hooks fire; do not reimplement phases inside it.

The preset exists because extensions can only *replace* templates while presets can *append*; `preset/templates/*-addendum.md` compose design sections into spec/plan/constitution without forking them.

## Benchmarks

`benchmarks/` measures whether the extension improves outcomes: the same RFC in three arms (`unaided`, `speckit`, `extension`) against trimmed inventories of shadcn/Radix/MUI, scored by `benchmarks/harness/score.py` on five metrics. Two rules hold the suite up, both covered by `tests/test_benchmarks.py`:

- **Every arm gets the design system**, in the same path, described by the same `AGENTS.md`. Changing one arm's setup without the others voids the run.
- **Every metric is arm-neutral**: none may look for an artifact only the extension produces, or it measures which arm ran. Extension-only observations (design doc, gap records, ledger, validation rounds) are reported unscored.

Cases (`benchmarks/cases/<id>/case.yml`) say what a good answer looks like per surface; `satisfied_by` names must exist in the system's inventory and cited guideline ids must exist in whatever source is in force for that system (house file, or the default set for Radix). Never publish numbers this repo has not produced: no results are committed yet, and the READMEs say so.

## Invariants to preserve

- **A failure to ask is never "the design system has nothing."** Missing binary, outage, changed flag → `available: false`. Only an error code the adapter explicitly declares as not-found becomes `found: false`. `probe_adapter` spends a real call at gate time; the gate fails closed when unreachable.
- **Guidelines resolve from exactly one source, never merged:** adapter CLI → shipped data file (`guidelines.source` or adapter file mapping) → `guidelines/default.yml`. Default set carries no colors/breakpoints/sizes.
- **Context is focused, never restricted.** `build_context(phase)` must not push unasked components, but they must stay retrievable via `available_on_demand`/`retrieval`. Two tests hold this line; don't pass one by breaking the other.
- **Workflow position is derived from artifacts, no state file** (`workflow_status`): `[NEEDS CLARIFICATION]` in spec.md, `tasks.md` unticked boxes, `## Validation round N` headings and `- [ ] DS-F-nnn` finding checkboxes in `design-system.md`. Those formats are a load-bearing contract with `commands/speckit.design.validate.md`. A round with ticked-off findings is not "clean". Rounds bounded by `max_validation_rounds` (3).
- Ledger (committed, keyed by UI capability) records ladder decisions: Reuse → Compose → Extend → Create.

## Testing notes

`tests/conftest.py` loads `design.py` via `importlib` as the `design` fixture and builds a minimal on-disk Spec Kit layout (`.specify/extensions/design/`, `.specify/feature.json`, `specs/<feature>/`). Tests are per-concern (`test_config`, `test_context`, `test_dispatch`, `test_guidelines`, `test_ledger`, `test_rfc`, `test_workflow`).

Project config lives at `.specify/extensions/design/design-config.yml` in the consuming project (template: `config-template.yml`); `adapter: auto` detects one.
