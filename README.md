# Design System Requirements for Spec Kit

[![Spec Kit](https://img.shields.io/badge/spec--kit-extension-blue?logo=github)](https://github.com/github/spec-kit)
[![Version](https://img.shields.io/badge/version-0.1.0-green)](https://github.com/artursopelnik/spec-kit-design-system/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Make the existing design system an active constraint and knowledge source throughout spec-driven development.

Spec Kit takes you from `/speckit.specify` to `/speckit.plan` to `/speckit.implement`. What it does not do is ask whether the interface you are about to build already exists. So the agent builds something locally reasonable, it works, it passes review, and the design system quietly grows a second date picker, a third button variant, and an accessibility fix that now has to be made in five places.

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

**Works with any design system.** The extension holds no component knowledge of its own, and there is no supported-systems list. A capability contract maps onto whatever your system already exposes. Writing an adapter for yours is about ten lines of YAML, and if it has no CLI at all, a generated JSON inventory works. Your design system stays the single source of truth, so nothing is mirrored and nothing can drift.

**It remembers.** Every ladder walk is recorded in a committed ledger keyed by UI capability. The second feature that needs a date range reads the first one's decision instead of re-running its search. Lookups match on the wordings actually searched, so a differently phrased need still finds the answer.

**Design requirements up front.** `DS-` requirements land in the spec at `/speckit.specify`, covering states, responsive behaviour, accessibility, tokens and interaction. Not in a review comment three days later.

**A gate that actually blocks.** `/speckit.plan` does not start until every UI surface has a documented resolution, with the candidates searched and a concrete reason the chosen rung is the lowest that holds.

**Constitutional.** The ladder ships as a `NON-NEGOTIABLE` principle, so `/speckit.analyze` classifies violations as CRITICAL with no extra wiring.

**Fails closed.** An unreachable CLI stops the gate instead of passing it, and a failed call is never reported as "the design system has nothing". A gate that passes when it cannot check anything is worse than no gate.

**Composes, doesn't colonize.** Gap reports come out as standalone RFC files that your existing tracker extension can carry to Jira, Linear, Azure DevOps or GitHub Issues. Optional, and none of it is reimplemented here.

### What it changes

| Without | With |
|---|---|
| The agent searches the design system from scratch each feature, or not at all | Rung 0 reads a prior decision before any search runs |
| "Use the design system" is a review comment | `DS-001: … MUST …` is a spec requirement with acceptance criteria |
| A new component appears in a diff and looks reasonable | A new component requires a written record of the alternatives searched |
| Design compliance is checked after the code exists | Planning does not begin until the surfaces are resolved |
| Nobody learns that the system lacks a date range picker | An RFC lands with the design system's owners |

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
| 5. **Create** | Only when 1 through 4 are *documented* as insufficient. |

A rung may not be rejected on a hunch. Rejecting one requires naming the candidates searched and why each is insufficient. "Doesn't fit" is not a reason.

Surfaces are described by **capability**, not by component name: *"a control for picking a start and end date"*, never *"a DateRangePicker"*. Naming the component you have in mind pre-decides the ladder and defeats the exercise.

When the answer genuinely is Create, that is a legitimate outcome. It just has to be visible:

```markdown
# RFC: DateRangePicker

**Surface**: selection of a start and end date

## Existing alternatives searched
| Candidate | Source | Why insufficient |
|---|---|---|
| DatePicker | component | Single date only; no range semantics |
| Calendar | component | Display-only; no input affordance |
| Select | component | Wrong interaction model; enumerable options only |
| Popover | component | Container primitive; solves placement, not the control |

## Composition attempted
Calendar in Popover with two DatePickers, rejected because range validation has to
live above both fields, which the composition cannot express without reaching into
DatePicker internals.

## Proposal
**Impact**: new component
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

1. **Spec Kit 1.0 or higher.** Verified against `1.0.9.dev0`.
2. **A design system CLI**, or a static JSON inventory if yours has no CLI.

### Install

```bash
git clone https://github.com/artursopelnik/spec-kit-design-system

# From within your spec-kit project
specify extension add --dev /path/to/spec-kit-design-system
specify preset add --dev /path/to/spec-kit-design-system/preset
```

The extension and preset install separately, because the preset lives in the `preset/` subdirectory of this repo.

No release archive is published yet, so installing from a clone is the only path for now. Once there is one, `specify extension add designsys --from <url>` will work too.

Both ship together on purpose. Extensions can only *replace* templates, which would fork your `spec-template` and strand you on whatever version it was copied from. Presets can `append`, which is how the design sections get composed in without forking anything.

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

Once installed, the hooks run on their own. The normal Spec Kit flow is the usage:

```bash
> /speckit.specify   # after_specify   → designsys.sync fills in DS- requirements
> /speckit.plan      # before_plan     → designsys.check gates on the ladder
> /speckit.tasks
> /speckit.implement # after_implement → designsys.audit validates the result
```

You only invoke a command directly to re-run one, or to scope it:

```bash
> /speckit.designsys.check "date range selection"
> /speckit.designsys.audit src/features/booking
```

## Commands

### `/speckit.designsys.sync`

Resolve design system context for the current spec and write it in as explicit requirements.

**Runs as**: `after_specify` (automatic, non-optional)

**Arguments**: none.

**Prerequisites**

* A spec exists for the active feature
* The design system CLI is reachable

**Output**

* `## Design System Requirements` populated in `spec.md` with `DS-` IDs
* Measurable design entries under `## Success Criteria`
* `[NEEDS CLARIFICATION: ...]` markers where the system's answer is genuinely ambiguous

### `/speckit.designsys.check`

Walk the reuse ladder and gate planning on the outcome.

**Runs as**: `before_plan` (automatic, **blocking**, priority 5)

**Arguments**

* `<surface>` (optional): re-check one named surface instead of all

**Prerequisites**

* A spec exists for the active feature
* The design system is reachable. An unreachable CLI fails the gate rather than passing it.

**Output**

* `design-system.md` in the feature directory, one section per surface with resolution, candidates searched, and rejection reasons
* New decisions appended to `.specify/memory/design-decisions.yml`
* A `## Design System Check` summary in `plan.md`
* An explicit pass or fail verdict

### `/speckit.designsys.audit`

Validate the implementation against what was decided.

**Runs as**: `after_implement` (automatic)

**Arguments**

* `<paths>` (optional): scope the audit to specific paths

**Prerequisites**

* `design-system.md` exists. The audit needs a contract to check against and will not improvise one after the fact.

**Output**

* An `## Audit` table in `design-system.md`, findings classified as violation, warning or note
* Small, unambiguous fixes applied in place, such as a raw value with an obvious token or a missing accessible name
* An explicit compliance verdict

### `/speckit.designsys.gap`

Record a justified gap and route it to the design system's owners.

**Runs as**: invoked by `check` when a surface reaches rung 5

**Arguments**

* `<surface>` (optional): the surface that reached rung 5

**Prerequisites**

* The surface already appears in `design-system.md` with rungs 1 through 4 documented as insufficient

**Output**

* A standalone `design-system-gap-<slug>.md` RFC in the feature directory, complete enough to hand to another team unchanged
* The gap filed with the design system's intake where the adapter maps `report_gap`. Otherwise the command that would file it is named, or you are told the file itself is the artifact.
* A recorded interim approach and a constraint on what the local build may become

## Decision memory

Every ladder walk produces a decision. Without somewhere to put it, that decision lives in one feature directory and the next feature re-derives it from scratch, often differently.

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

**`aliases`** holds every wording that was actually searched, *including the ones that missed*. These are what make a later lookup hit when the next author phrases the same need differently. A decision with no aliases will be re-derived.

**`design_system_version`** lets a later lookup tell that the system has moved on. A cached decision against a stale inventory is worse than no decision, because it looks authoritative. Stale hits are re-walked, not adopted.

Contradicting decisions supersede rather than accumulate. Two active decisions for one capability is exactly the drift this extension exists to prevent.

Inspect it directly:

```bash
DS=.specify/extensions/designsys/scripts/bash
$DS/ds-ledger.sh --json list
$DS/ds-ledger.sh --json lookup "period filter"
```

The ledger is deliberately not an ADR system. These decisions are numerous, cheap, and keyed by UI capability rather than by file path. If your team already runs a decision-record process, rungs 4 and 5 are the ones that carry design system impact and are worth escalating into it.

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

Anything unmapped is reported as unavailable, and the commands degrade deliberately rather than failing, or worse, inventing an inventory from memory.

### What ships

Two files, and neither is a vendor binding:

| File | What it is |
|---|---|
| `static-json` | **The universal fallback.** Point it at a generated inventory file and everything works without a CLI at all. Most teams can produce one from Storybook or their token pipeline in a few lines of build script. This is what makes the agnosticism real rather than aspirational. |
| `astryx` | **A worked example**, modelled on [Meta's Astryx](https://github.com/facebook/astryx). It is the one design system that exercises the entire contract: self-description via `manifest --json`, a sanctioned extension path via `swizzle`, and real gap intake via `gap-report`. Copy it as a starting point for yours. |

There is deliberately no list of blessed design systems. Maintaining per-vendor adapters would be a treadmill, and it would turn "works with any design system" into "works with the four we got around to". The contract is the product. The adapters are documentation that happens to execute.

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

Placeholders in `args` are expanded from the call. An argument whose placeholder has no value is dropped along with the flag before it, so a missing optional value cannot leave a dangling flag that swallows the next argument. A list-valued placeholder splices into separate arguments. `result_path` is a dotted path into the parsed response.

Only `search` and `component` are strictly required. `not_found_codes` matters more than it looks: an error code listed there means "the design system answered, and it does not have this". Any other failure is treated as an inability to ask, never as an empty result.

## Configuration Reference

```yaml
# .specify/extensions/designsys/designsys-config.yml

# Which adapter from adapters/. Use "custom" to define capabilities inline.
adapter: astryx

# Override the binary the adapter invokes. Empty uses the adapter default.
bin: ""

# Working directory for the design system, relative to repo root. Empty uses the
# repo root. Both CLI invocations and inventory lookups resolve against it, so a
# monorepo can point at one package.
cwd: ""

# Override the adapter's inventory path or registry list.
# source: ".design-system/inventory.json"
# registries: ["@acme"]

# Override individual capabilities from the chosen adapter.
# capabilities:
#   search:
#     args: ["search", "{query}", "--json", "--detail", "compact"]
#     result_path: "data.results"

ledger:
  enabled: true
  # Minimum token-overlap score for a prior decision to be surfaced. Lower
  # surfaces more and risks false matches, higher misses differently worded
  # lookups. Aliases recorded at decision time matter more than this number.
  match_threshold: 0.34
  revalidate_when_stale: true

# The design system version in use now. Prior decisions taken against a
# different one are flagged stale. Leave empty and staleness is simply not
# checked, which lookups report rather than implying the decision is current.
design_system_version: ""

gate:
  # false lets the ladder run and record findings without blocking
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
  # Empty infers from the plan's Project Structure section
  source_globs: []
```

### Environment variable overrides

```bash
export SPECKIT_DESIGNSYS_ADAPTER="static-json"
export SPECKIT_DESIGNSYS_BIN="npx my-design-system"
export SPECKIT_DESIGNSYS_CWD="packages/web"

export SPECKIT_DESIGNSYS_GATE_ENFORCE="false"
export SPECKIT_DESIGNSYS_REQUIRE_GAP_REPORT="false"
export SPECKIT_DESIGNSYS_MIN_CANDIDATES="3"

export SPECKIT_DESIGNSYS_LEDGER_ENABLED="true"
export SPECKIT_DESIGNSYS_MATCH_THRESHOLD="0.34"
export SPECKIT_DESIGNSYS_FORBID_RAW_VALUES="true"
```

### Local overrides (gitignored)

Create `.specify/extensions/designsys/designsys-config.local.yml` to point at a scratch design system without touching the committed config:

```yaml
bin: "node ../my-design-system/bin/cli.mjs"
gate:
  enforce: false
```

Resolution order is **extension defaults → project config → local override → environment**.

## Examples

### Astryx, minimal

```yaml
adapter: astryx
bin: "npx astryx"
```

### No CLI, static inventory

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

### Adopting gradually

Run the ladder and record its findings, but do not block planning yet:

```yaml
adapter: astryx
gate:
  enforce: false
```

Turn `enforce` on once the ledger has a few decisions in it and the team has seen what the gate actually reports.

### Monorepo with a scoped CLI

```yaml
adapter: astryx
bin: "pnpm --filter @acme/web exec astryx"
cwd: "packages/web"
audit:
  source_globs: ["packages/web/src/**/*.tsx"]
```

## Where this sits in the Spec Kit ecosystem

The extension catalog has 170+ community extensions. This one deliberately owns a narrow slice and reuses the rest. **If an installed extension already does something, this one points at it rather than reimplementing it.**

### Prior art

Nothing in the catalog gates spec-driven development on a design system's own inventory. The closest neighbours solve adjacent problems and compose rather than compete:

| Extension | What it does | Relationship |
|---|---|---|
| `figma` | Grounds spec, plan and tasks in Figma design context | Complementary. Figma is design intent, this is the shipped component inventory. |
| `figma-starter` | Turns Figma screens into per-screen specs | Upstream. Its specs then pass through this gate. |
| `wireframe` | SVG wireframes that become spec constraints honored by plan, tasks and implement | Same pattern, different artifact |
| `a11y-governance` (preset) | WCAG 2.2 AA governance | Overlaps on the accessibility dimension only. Run both. |
| [`adrkit`](https://github.com/mbeacom/adrkit) | Machine-readable ADRs, decision memory keyed by file path | The ledger is keyed by UI capability and holds every walk. Rungs 4 and 5 are what deserve promoting to a real ADR. |

### Memory: reuse `.specify/memory/`

The ledger lives at `.specify/memory/design-decisions.yml` on purpose. That directory is Spec Kit's own memory location, and the `memory-loader` extension loads everything in it before lifecycle commands. If you run it, the ledger reaches agent context with no integration work from either side. `memory`, `memory-md` and `dubsar` occupy the same space, and none of them needed to be reimplemented here.

### Issues and RFCs, both directions

A design system request travels in both directions, and Spec Kit already has extensions for each. **This extension builds neither importer nor exporter.**

**Outbound: a gap you found becomes a proposal.** A rung-5 gap record is written as a standalone `design-system-gap-<slug>.md`, an RFC carrying the capability needed, the alternatives searched, why each is insufficient, and the proposed scope. It is a complete, reviewable document produced as a by-product of the gate rather than written from scratch. Where it goes is your choice:

| You run | Route |
|---|---|
| A design system CLI with intake, such as Astryx `gap-report` | Filed directly with the owning package, the shortest path |
| Core Spec Kit | `/speckit.taskstoissues` to GitHub Issues |
| `jira`, `jira-mirror`, `linear`, `azure-devops` | Whichever you already sync with |
| Nothing | The RFC file *is* the artifact. Commit it, paste it, or open it as a PR against the design system repo. |

File it against the **design system's** project, not the product team's. With the `jira` extension a local override is usually enough:

```yaml
# .specify/extensions/jira/jira-config.local.yml
project:
  key: "DESIGNSYS"
```

**Inbound: a request arrives from the community.** Someone files "we need a date range picker" as a GitHub issue, a GitLab issue, or a Jira ticket. `github-issues`, `issue` and `gh-triage` already turn those into spec artifacts, `intake` normalizes PRDs and design evidence, and the official `assess` extension shapes a raw idea before SDD begins. Install whichever fits your tracker.

What this extension adds to an inbound request is the triage. **The same ladder that stops a product team from building a duplicate also answers whether an incoming request is actually a gap.** Rung 0 checks whether it was already decided, rungs 1 through 4 check whether the system already covers it. A large share of incoming component requests turn out to be answered by an existing component under a name the requester did not know.

One integration note: the gate is hooked to `before_plan`, not to `specify`. So however a spec came into existence, whether typed by hand, imported from an issue, or generated from Figma, **planning is still gated**. If the spec arrived from an importer rather than `/speckit.specify`, the `after_specify` hook will not have fired, so run `/speckit.designsys.sync` once to populate its design requirements.

### Ordering

The hooks do not collide. This gates at `before_plan`, tracker extensions publish at `after_tasks`:

```text
issue / Figma / raw idea
        │  github-issues · issue · intake · assess
        ▼
/speckit.specify → designsys.sync → [GATE] designsys.check
        │
        ▼
/speckit.plan → /speckit.tasks
        │  taskstoissues · jira · linear · azure-devops
        ▼
   tickets carry the resolved design constraints
        │
        ▼
/speckit.implement → designsys.audit
```

That middle step is the one worth noticing. By the time tickets are created, each surface is already resolved and its constraints recorded. Whoever picks up the ticket reads *"use Calendar + Popover, tokens `space.*`, states default/focus/disabled/error"* instead of re-deciding it in the ticket comments, which is where design drift gets reintroduced after the gate has done its job.

## Troubleshooting

### The gate fails with "design system could not be reached"

This is intentional. The ladder cannot be walked without the source of truth, and a gate that passes when it cannot check anything is not a gate. Verify the CLI directly:

```bash
.specify/extensions/designsys/scripts/bash/ds-query.sh --json search "button"
```

Check `bin` in `designsys-config.yml`, and `cwd` if the CLI must run from a subdirectory.

### "PyYAML is required to read design system configuration"

The interpreter running the scripts is not the one Spec Kit installed into. Install PyYAML into it with `pip install pyyaml`.

### `adapter '<id>' not found`

`adapter:` must name a file in `.specify/extensions/designsys/adapters/`. Ships with `astryx` and `static-json`. Use `custom` to define capabilities inline in your config, or drop your own YAML into that directory.

### A capability comes back `available: false`

Your adapter does not map it. This is expected for `extend` and `report_gap` on a static inventory, which has no write side. The commands degrade rather than fail. Map it in your config's `capabilities:` block if your CLI does support it.

### The gate keeps failing on `min_candidates_considered`

A rung was rejected on fewer candidates than configured. Either search more broadly, trying the user-facing term, the designer's term, and the term the docs use for a neighbouring concept, or lower the threshold if the design system genuinely offers fewer. Do not pad the candidates table to get past it.

### A prior decision keeps being surfaced that does not fit

The ledger match is fuzzy by design. Raise `ledger.match_threshold`, or supersede the decision if it is actually wrong. A prior decision is evidence, not an instruction. Re-walking is allowed, as long as you say so.

### The ledger never matches anything

Almost always missing `aliases`. A decision recorded with only its canonical phrase will not match a differently worded lookup. Add the wordings you actually searched with to the existing entries.

## Development

### Repository structure

```text
spec-kit-design-system/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── extension.yml               # Extension manifest
├── config-template.yml         # Config template, materialized on install
├── adapters/                   # Capability mappings: examples, not a vendor list
│   ├── astryx.yml              #   worked example exercising the full contract
│   └── static-json.yml         #   universal fallback, no CLI required
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
├── preset/                     # Composes sections into core templates
│   ├── preset.yml
│   └── templates/
│       ├── spec-addendum.md
│       ├── plan-addendum.md
│       └── constitution-addendum.md
├── tests/                      # pytest over designsys.py
└── .github/workflows/ci.yml    # unit tests plus a real install against Spec Kit
```

All logic lives in one Python module, and the bash scripts are thin shims that locate an interpreter and forward arguments. There are no PowerShell shims yet. On Windows, invoke the module directly, which behaves identically:

```powershell
python3 .specify/extensions/designsys/scripts/python/designsys.py gate --json
```

PowerShell shims are a welcome contribution.

### Testing

```bash
pip install pytest pyyaml
python -m pytest
```

The suite covers config layering, the ledger (recall across wordings, superseding, tri-state staleness), capability dispatch against a fake CLI that reproduces each failure mode, and the fail-closed probe.

CI additionally runs a **real install** on every push: `specify init`, `specify extension add --dev`, `specify preset add --dev`, then asserts that hooks are registered with `before_plan` blocking, that `strategy: append` composed all three templates without losing core content, and that the gate fails closed against a missing binary. It also runs weekly on a schedule, because Spec Kit moves fast and a catalog entry that quietly stops working on a newer release is the failure mode worth catching early.

### Testing against your own project

```bash
cd /path/to/your/project
specify extension add --dev /path/to/spec-kit-design-system
specify preset add --dev /path/to/spec-kit-design-system/preset

# Exercise the scripts directly. They always emit JSON.
DS=.specify/extensions/designsys/scripts/bash
$DS/check-design-gate.sh --json | python3 -m json.tool
$DS/ds-query.sh --json component Button
$DS/ds-ledger.sh --json list
```

## Status

Verified against a real `specify init` project on Spec Kit `1.0.9.dev0`:

* Install via `specify extension add --dev` and `specify preset add --dev`, including config materialization and hook registration in `.specify/extensions.yml`
* `strategy: append` composition on all three templates, with core content preserved and `tasks-template` correctly untouched
* Commands registered as agent skills (`speckit-designsys-*`)
* The gate running against a real feature created by `create-new-feature.sh`
* Capability dispatch, config layering, the ledger and the fail-closed probe, under `pytest`

Two things remain unexercised: a command body end-to-end with an agent actually following it, and the Astryx adapter against a live Astryx install. The adapter is modelled on the published CLI reference, so its flag mapping is unverified against a real binary. Issues and adapter contributions welcome.

## Contributing

Contributions welcome, adapters for other design system CLIs especially. Fork, branch, and open a pull request.

## Support

* **Issues**: <https://github.com/artursopelnik/spec-kit-design-system/issues>
* **Spec Kit docs**: <https://github.com/github/spec-kit>

## License

MIT, see [LICENSE](LICENSE).
