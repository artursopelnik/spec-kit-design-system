# Spec Kit — Design System Requirements Extension

[![Spec Kit](https://img.shields.io/badge/spec--kit-extension-blue?logo=github)](https://github.com/github/spec-kit)
[![Version](https://img.shields.io/badge/version-0.1.0-green)](https://github.com/artursopelnik/spec-kit-design-system/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Make the existing design system an active constraint and knowledge source throughout spec-driven development.

Spec Kit takes you from `/speckit.specify` to `/speckit.plan` to `/speckit.implement`. What it does not do is ask whether the interface you are about to build already exists. So the agent builds something locally reasonable, it works, it passes review — and the design system quietly grows a second date picker, a third button variant, and an accessibility fix that now has to be made in five places.

This extension closes that loop. Design requirements enter at `/speckit.specify`, the reuse ladder gates `/speckit.plan`, and the implementation is audited against what was actually decided.

**It does not model your design system. It asks yours.**

```text
Spec Kit Extension
        │
        ▼
 Design System CLI          ← single source of truth
        │
        ├── search
        ├── components
        ├── patterns
        ├── tokens
        └── gap intake
```

## Features

- **Design requirements up front**: `DS-` requirements land in the spec at `/speckit.specify`, not in a review comment three days later
- **A real gate**: `/speckit.plan` is blocked until every UI surface has a documented resolution
- **Reuse ladder**: Recall → Reuse → Compose → Extend → Create, with rejection reasons required at each rung
- **Decision memory**: a committed ledger so the second feature to need a date range does not re-run the first one's search
- **CLI-agnostic**: a capability contract with adapters for Astryx, shadcn/ui and static JSON inventories
- **Constitutional**: ships the ladder as a `NON-NEGOTIABLE` principle, so `/speckit.analyze` treats violations as CRITICAL
- **Degrades honestly**: an unreachable CLI fails the gate rather than falling back on a remembered inventory

## The ladder

The central rule, and the one worth arguing about:

> **Recall → Reuse → Compose → Extend → Create**

Before a new component is proposed or built:

| Rung | Question |
|---|---|
| 0. **Recall** | Has another feature already decided this? |
| 1. **Reuse** | Does an existing component cover it? |
| 2. **Compose (pattern)** | Does an existing pattern cover the arrangement? |
| 3. **Compose (components)** | Can existing components be combined? |
| 4. **Extend** | Can a component be extended through a sanctioned mechanism? |
| 5. **Create** | Only when 1–4 are *documented* as insufficient. |

A rung may not be rejected on a hunch. Rejecting one requires naming the candidates searched and why each is insufficient — "doesn't fit" is not a reason.

And surfaces are described by **capability**, not by component name: *"a control for picking a start and end date"*, never *"a DateRangePicker"*. Naming the component you have in mind pre-decides the ladder and defeats the exercise.

When the answer genuinely is Create, that is a legitimate outcome — it just has to be visible:

```markdown
### Gap: DateRangePicker

**Surface**: selection of a start and end date
**Existing alternatives searched**:
| Candidate | Source | Why insufficient |
|---|---|---|
| DatePicker | component | Single date only; no range semantics |
| Calendar | component | Display-only; no input affordance |
| Select | component | Wrong interaction model; enumerable options only |
| Popover | component | Container primitive; solves placement, not the control |

**Composition attempted**: Calendar in Popover with two DatePickers — rejected because range
validation has to live above both fields, which the composition cannot express without
reaching into DatePicker internals.

**Decision**: New component required.
**Design system impact**: new component proposal, routed to its owning package.
```

This is not paperwork. It is the mechanism that distinguishes a real gap the design system should close from a search that was not thorough enough.

## The lifecycle

```text
                    USER REQUIREMENT
                           │
                           ▼
                    /speckit.specify
                           │
                           ▼
            after_specify → designsys.sync          design requirements
                           │                        enter the spec
                           ▼
                  ledger  +  Design System CLI
                           │
                           ▼
            before_plan  → designsys.check          the gate:
                           │                        recall → reuse → compose
                           │                        → extend → create
                    ┌──────┴──────┐
                    │             │
                  pass          fail ──→ planning does not start
                    │
                    ▼
                    /speckit.plan → /speckit.tasks
                           │
                           ▼
                   /speckit.implement
                           │
                           ▼
           after_implement → designsys.audit
                           │
                 ┌─────────┴─────────┐
                 │                   │
             compliant           violations
                 │                   │
                 ▼                   ▼
                DONE            fix / iterate
```

## Installation

### Prerequisites

1. **Spec Kit** 0.6.0 or higher (the preset uses `strategy: append`, which requires ≥ 0.6.0)
2. **Python 3** with PyYAML, which ships as a Spec Kit dependency
3. **A design system CLI** — or a static JSON inventory, if yours has no CLI

### Install

```bash
# From within a spec-kit project
specify extension add https://github.com/artursopelnik/spec-kit-design-system
specify preset add https://github.com/artursopelnik/spec-kit-design-system --path preset

# Or from a local development directory
specify extension add --dev /path/to/spec-kit-design-system
```

The extension and the preset ship together on purpose. Extensions can only *replace* templates, which would fork your `spec-template` and strand you on whatever version it was copied from. Presets can `append`, which is how the design sections get composed in without forking anything.

### Configure

Point it at your design system in `.specify/extensions/designsys/designsys-config.yml`:

```yaml
adapter: astryx
bin: "npx astryx"
```

Verify it can reach the CLI:

```bash
.specify/extensions/designsys/scripts/bash/ds-query.sh --json search "button"
```

### Adopt the principle

```bash
/speckit.constitution
```

The preset appends the ladder to your `constitution-template` as a `NON-NEGOTIABLE` principle with MUST statements. `/speckit.analyze` reads the constitution's normative statements as a rule set and classifies conflicts as **CRITICAL**, requiring the spec, plan or tasks to change rather than the principle to be reinterpreted. That is what makes the rule enforceable at analysis time and not just at the plan gate.

## Usage

Once installed, the hooks run on their own — the normal Spec Kit flow is the usage:

```bash
> /speckit.specify   # after_specify  → designsys.sync fills in DS- requirements
> /speckit.plan      # before_plan    → designsys.check gates on the ladder
> /speckit.tasks
> /speckit.implement # after_implement → designsys.audit validates the result
```

You only invoke a command directly to re-run one, or to scope it:

```bash
> /speckit.designsys.check --refresh          # re-derive the CLI mapping first
> /speckit.designsys.audit src/features/booking
```

## Commands

### `/speckit.designsys.sync`

Resolve design system context for the current spec and write it in as explicit requirements.

**Runs as**: `after_specify` (automatic, non-optional)

**Arguments**

- `--refresh` (optional): re-derive the capability mapping from the CLI's own self-description before querying

**Prerequisites**

- A spec exists for the active feature
- The design system CLI is reachable

**Output**

- `## Design System Requirements` populated in `spec.md` with `DS-` IDs
- Measurable design entries under `## Success Criteria`
- `[NEEDS CLARIFICATION: ...]` markers where the system's answer is genuinely ambiguous

### `/speckit.designsys.check`

Walk the reuse ladder and gate planning on the outcome.

**Runs as**: `before_plan` (automatic, **blocking**, priority 5)

**Arguments**

- `<surface>` (optional): re-check one named surface instead of all
- `--refresh` (optional): re-derive the capability mapping first

**Prerequisites**

- A spec exists for the active feature
- The design system CLI is reachable — an unreachable CLI fails the gate rather than passing it

**Output**

- `design-system.md` in the feature directory, one section per surface with resolution, candidates searched, and rejection reasons
- New decisions appended to `.specify/memory/design-decisions.yml`
- A `## Design System Check` summary in `plan.md`
- An explicit pass/fail verdict

### `/speckit.designsys.audit`

Validate the implementation against what was decided.

**Runs as**: `after_implement` (automatic)

**Arguments**

- `<paths>` (optional): scope the audit to specific paths

**Prerequisites**

- `design-system.md` exists — the audit needs a contract to check against, and will not improvise one after the fact

**Output**

- An `## Audit` table in `design-system.md`, findings classified as violation / warning / note
- Small, unambiguous fixes applied in place (a raw value with an obvious token, a missing accessible name)
- An explicit compliance verdict

### `/speckit.designsys.gap`

Record a justified gap and route it to the design system's owners.

**Runs as**: invoked by `check` when a surface reaches rung 5

**Arguments**

- `<surface>` (optional): the surface that reached rung 5

**Prerequisites**

- The surface already appears in `design-system.md` with rungs 1–4 documented as insufficient

**Output**

- A `### Gap:` record with the alternatives searched and why each is insufficient
- The gap filed with the design system's intake, where the adapter maps `report_gap`
- A recorded interim approach and a constraint on what the local build may become

## Decision memory

Every ladder walk produces a decision. Without somewhere to put it, that decision lives in one feature directory and the next feature re-derives it from scratch — often differently.

The ledger is a plain YAML file at `.specify/memory/design-decisions.yml`, committed with your repository:

```yaml
decisions:
  - id: dd-001
    capability: "selection of a date range"
    aliases: ["date range picker", "from-to date selection", "period filter"]
    resolution: compose-components
    decision: "Calendar inside Popover, range state lifted to the form"
    components: [Calendar, Popover]
    rejected:
      - {candidate: DatePicker, reason: "single date only; no range semantics"}
    design_system: astryx
    design_system_version: "1.4.2"
    decided_in: "003-booking-filters"
    status: active
```

Two fields carry the weight:

- **`aliases`** — every wording that was actually searched, *including the ones that missed*. These are what make a later lookup hit when the next author phrases the same need differently. A decision with no aliases will be re-derived.
- **`design_system_version`** — so a later lookup can tell the system has moved on. A cached decision against a stale inventory is worse than no decision, because it looks authoritative. Stale hits are re-walked, not adopted.

Contradicting decisions supersede rather than accumulate. Two active decisions for one capability is exactly the drift this extension exists to prevent.

Inspect it directly:

```bash
DS=.specify/extensions/designsys/scripts/bash
$DS/ds-ledger.sh --json list
$DS/ds-ledger.sh --json lookup "period filter"
```

The ledger is deliberately **not** an ADR system. These decisions are numerous, cheap, and keyed by UI capability rather than by file path. If your team already runs a decision-record process, rungs 4 and 5 — the ones that carry design system impact — are the ones worth escalating into it.

## Adapters

The extension is written against a **capability contract**, never against one CLI's flags:

| Capability | What it answers | Required |
|---|---|---|
| `search` | what do we have for this use case? | ✅ |
| `component` | props, variants, states, accessibility for one component | ✅ |
| `describe` | what can this CLI do? (self-description) | |
| `list_components` | what exists at all? | |
| `pattern` | an existing composed arrangement | |
| `tokens` | the token vocabulary | |
| `extend` | the sanctioned way to extend a component | |
| `report_gap` | route a genuine gap to its owner | |

Anything unmapped is reported as unavailable, and the commands degrade deliberately rather than failing — or worse, inventing an inventory from memory.

### Shipped adapters

| Adapter | Design system | Notes |
|---|---|---|
| `astryx` | [Meta Astryx](https://github.com/facebook/astryx) | Self-describing via `astryx manifest --json`. Its `gap-report` command means rung 5 routes into the design system's own intake instead of dead-ending in a document. |
| `shadcn` | shadcn/ui | `search` / `view` against one or more registries. No self-description and no gap intake, so those capabilities are unmapped. |
| `static-json` | *any* | Point it at a generated inventory file and the gate still works. Most teams can produce one from Storybook or their token pipeline in a few lines of build script. |

### Writing your own

An adapter is a YAML file in `adapters/`:

```yaml
id: mydesignsystem
name: "My Design System"
bin: "npx mydesignsystem"
global_args: ["--json"]

envelope:
  type_key: "type"
  data_key: "data"
  error_code_key: "code"

capabilities:
  search:
    args: ["search", "{query}"]
    result_path: "data.results"
  component:
    args: ["show", "{name}"]
    result_path: "data"
    not_found_codes: ["ERR_NOT_FOUND"]
```

Placeholders in `args` are expanded from the call; an argument whose placeholder has no value is dropped rather than passed as a literal brace. `result_path` is a dotted path into the parsed response.

## Configuration Reference

```yaml
# .specify/extensions/designsys/designsys-config.yml

# Which adapter from adapters/. Use "custom" to define capabilities inline.
adapter: astryx

# Override the binary the adapter invokes. Empty = adapter default.
bin: ""

# Working directory for CLI invocations, relative to repo root. Empty = repo root.
cwd: ""

# Override individual capabilities from the chosen adapter (optional)
# capabilities:
#   search:
#     args: ["search", "{query}", "--json", "--detail", "compact"]
#     result_path: "data.results"

ledger:
  enabled: true
  # Minimum token-overlap score for a prior decision to be surfaced. Lower
  # surfaces more and risks false matches; higher misses differently-worded
  # lookups. Aliases recorded at decision time matter more than this number.
  match_threshold: 0.34
  # Re-validate a prior decision when the design system version has changed.
  revalidate_when_stale: true

gate:
  # false = the ladder still runs and records findings, but no longer blocks
  # /speckit.plan. Useful while adopting.
  enforce: true
  require_gap_report: true
  min_candidates_considered: 3

audit:
  forbid_raw_values: true
  required_dimensions:
    - states
    - responsive
    - accessibility
    - tokens
    - interaction
  # Empty = infer from the plan's Project Structure section
  source_globs: []
```

### Environment Variable Overrides

```bash
export SPECKIT_DESIGNSYS_ADAPTER="shadcn"
export SPECKIT_DESIGNSYS_BIN="npx shadcn@latest"
export SPECKIT_DESIGNSYS_CWD="packages/web"

export SPECKIT_DESIGNSYS_GATE_ENFORCE="false"
export SPECKIT_DESIGNSYS_REQUIRE_GAP_REPORT="false"
export SPECKIT_DESIGNSYS_MIN_CANDIDATES="3"

export SPECKIT_DESIGNSYS_LEDGER_ENABLED="true"
export SPECKIT_DESIGNSYS_MATCH_THRESHOLD="0.34"
export SPECKIT_DESIGNSYS_FORBID_RAW_VALUES="true"
```

### Local Overrides (Gitignored)

Create `.specify/extensions/designsys/designsys-config.local.yml` to point at a scratch design system without touching the committed config:

```yaml
bin: "node ../my-design-system/bin/cli.mjs"
gate:
  enforce: false
```

Resolution order is **extension defaults → project config → local override → environment**.

## Examples

### Example 1: Astryx, minimal

```yaml
adapter: astryx
bin: "npx astryx"
```

### Example 2: No CLI, static inventory

```yaml
adapter: static-json
```

with `.design-system/inventory.json`:

```json
{
  "components": [
    {"name": "Calendar", "description": "Month grid for date display",
     "states": ["default", "disabled"],
     "accessibility": "grid role, arrow-key navigation"}
  ],
  "patterns": [
    {"name": "FilterBar", "description": "Horizontal row of filter controls",
     "composes": ["Select", "Popover"]}
  ],
  "tokens": {"space": {"3": "12px"}, "color": {"surface": {"default": "#fff"}}}
}
```

### Example 3: Adopting gradually

Run the ladder and record its findings, but do not block planning yet:

```yaml
adapter: astryx
gate:
  enforce: false
```

Turn `enforce` on once the ledger has a few decisions in it and the team has seen what the gate actually reports.

### Example 4: Monorepo with a scoped CLI

```yaml
adapter: astryx
bin: "pnpm --filter @acme/web exec astryx"
cwd: "packages/web"
audit:
  source_globs: ["packages/web/src/**/*.tsx"]
```

## Combining with other extensions

This extension deliberately stops at the edge of the design system. It composes well with extensions that own the next step.

### Issue trackers — [spec-kit-jira](https://github.com/mbachorik/spec-kit-jira) and friends

The hooks do not collide: the gate runs at `before_plan`, while `spec-kit-jira` creates issues at `after_tasks`. The natural order is

```text
/speckit.specify → designsys.sync → [gate] designsys.check
                 → /speckit.plan → /speckit.tasks
                 → jira.specstoissues → /speckit.implement → designsys.audit
```

Two things are worth wiring up deliberately:

**Design constraints ride into the ticket.** By the time `specstoissues` runs, `design-system.md` has already resolved each surface and recorded its constraints, and the plan carries them in its `## Design System Check` section. Whoever picks up the ticket reads *"use Calendar + Popover, tokens `space.*`, states default/focus/disabled/error"* instead of re-deciding it in the ticket comments — which is where design drift usually gets reintroduced after the gate has done its job.

**Gap reports are the RFC.** A rung-5 gap record is already an argued proposal: the capability needed, the alternatives searched, why each is insufficient, and the scope proposed. That is the substance an RFC or new-component request needs, and it was produced as a by-product of the gate rather than written from scratch. File it as an issue in the **design system's** project rather than the product team's — a local config override for a second project key is usually enough:

```yaml
# .specify/extensions/jira/jira-config.local.yml
project:
  key: "DESIGNSYS"
```

Note this is a **composition pattern, not a built integration**: there is no code here that talks to Jira. The two extensions simply operate on the same artifacts in a sensible order, and a gap record happens to be shaped like a ticket.

### Decision records

If you already run ADRs — [adrkit](https://github.com/mbachorik/adrkit) or otherwise — the ledger is not a competitor. It is keyed by UI capability and holds every walk, including the cheap ones. Rungs 4 and 5 are the ones that carry design system impact and are worth promoting into a reviewed decision record.

## Troubleshooting

### "Design system CLI could not be reached" — the gate fails

**Solution**: This is intentional. The ladder cannot be walked without the source of truth, and a gate that passes when it cannot check anything is not a gate. Verify the CLI directly:

```bash
.specify/extensions/designsys/scripts/bash/ds-query.sh --json search "button"
```

Check `bin` in `designsys-config.yml`, and `cwd` if the CLI must run from a subdirectory.

### "PyYAML is required to read design system configuration"

**Solution**: The interpreter running the scripts is not the one Spec Kit installed into. Install PyYAML into it: `pip install pyyaml`.

### `adapter '<id>' not found`

**Solution**: `adapter:` must name a file in `.specify/extensions/designsys/adapters/`. Shipped: `astryx`, `shadcn`, `static-json`. Use `custom` to define capabilities inline in your config.

### Capability comes back `available: false`

**Solution**: Your adapter does not map it. This is expected for `report_gap` on shadcn and for `extend` on a static inventory — the commands degrade rather than fail. Map it in your config's `capabilities:` block if your CLI does support it.

### The gate keeps failing on `min_candidates_considered`

**Solution**: A rung was rejected on fewer candidates than configured. Either search more broadly — try the user-facing term, the designer's term, and the term the docs use for a neighbouring concept — or, if the design system genuinely offers fewer, lower the threshold. Do not pad the candidates table to get past it.

### A prior decision keeps being surfaced that does not fit

**Solution**: The ledger match is fuzzy by design. Raise `ledger.match_threshold`, or supersede the decision if it is actually wrong. A prior decision is evidence, not an instruction — re-walking is allowed, as long as you say so.

### The ledger never matches anything

**Solution**: Almost always missing `aliases`. A decision recorded with only its canonical phrase will not match a differently-worded lookup. Add the wordings you actually searched with to the existing entries.

## Development

### Repository Structure

```text
spec-kit-design-system/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── extension.yml               # Extension manifest
├── config-template.yml         # Config template, materialized on install
├── adapters/                   # Design system CLI mappings
│   ├── astryx.yml
│   ├── shadcn.yml
│   └── static-json.yml
├── commands/
│   ├── speckit.designsys.sync.md
│   ├── speckit.designsys.check.md
│   ├── speckit.designsys.audit.md
│   └── speckit.designsys.gap.md
├── scripts/
│   ├── bash/                   # Thin shims
│   │   ├── designsys-common.sh
│   │   ├── check-design-gate.sh
│   │   ├── ds-query.sh
│   │   └── ds-ledger.sh
│   └── python/
│       └── designsys.py        # All logic lives here
└── preset/                     # Composes sections into core templates
    ├── preset.yml
    └── templates/
        ├── spec-addendum.md
        ├── plan-addendum.md
        └── constitution-addendum.md
```

All logic lives in one Python module; the bash scripts are thin shims that locate an interpreter and forward arguments. There are no PowerShell shims yet — on Windows, invoke the module directly, which behaves identically:

```powershell
python3 .specify/extensions/designsys/scripts/python/designsys.py gate --json
```

PowerShell shims are a welcome contribution.

### Testing Locally

```bash
cd /path/to/your/project
specify extension add --dev /path/to/spec-kit-design-system
specify preset add --dev /path/to/spec-kit-design-system/preset

# Exercise the scripts directly — they always emit JSON
DS=.specify/extensions/designsys/scripts/bash
$DS/check-design-gate.sh --json | python3 -m json.tool
$DS/ds-query.sh --json component Button
$DS/ds-ledger.sh --json list
```

## Status

Early. The command bodies, the capability contract and the ledger are the stable parts. Adapter coverage beyond Astryx is thin, and the `shadcn` adapter parses prose output rather than a typed envelope. Issues and adapter contributions welcome.

## Contributing

Contributions welcome — adapters for other design system CLIs especially. Fork, branch, and open a pull request.

## Support

- **Issues**: <https://github.com/artursopelnik/spec-kit-design-system/issues>
- **Spec Kit Docs**: <https://github.com/github/spec-kit>

## License

MIT — see [LICENSE](LICENSE).
