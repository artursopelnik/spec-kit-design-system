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

- **Works with any design system** — the extension holds no component knowledge of its own. A capability contract maps onto whatever your system already exposes: Astryx, shadcn/ui, or a static JSON inventory if it has no CLI at all. Your design system stays the single source of truth; nothing is mirrored, so nothing can drift.
- **It remembers** — every ladder walk is recorded in a committed ledger keyed by UI capability. The second feature that needs a date range reads the first one's decision instead of re-running its search. Lookups match on the wordings actually searched, so a differently-phrased need still finds the answer.
- **Design requirements up front** — `DS-` requirements land in the spec at `/speckit.specify`, covering states, responsive behaviour, accessibility, tokens and interaction. Not in a review comment three days later.
- **A gate that actually blocks** — `/speckit.plan` does not start until every UI surface has a documented resolution, with the candidates searched and a concrete reason the chosen rung is the lowest that holds.
- **Constitutional** — ships the ladder as a `NON-NEGOTIABLE` principle, so `/speckit.analyze` classifies violations as CRITICAL with no extra wiring.
- **Fails closed** — an unreachable CLI stops the gate instead of passing it, and a failed call is never reported as "the design system has nothing". A gate that passes when it cannot check anything is worse than no gate.
- **Composes, doesn't colonize** — gap reports come out as standalone RFC files that your existing tracker extension can carry to Jira, Linear, Azure DevOps or GitHub Issues. Optional, and none of it is reimplemented here.

### What it actually changes

No benchmark is claimed — this has not been measured against a control, and anyone quoting a percentage at you about this has not measured it either. What it changes is mechanical and checkable:

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

- A standalone `design-system-gap-<slug>.md` RFC in the feature directory, complete enough to hand to another team unchanged
- The gap filed with the design system's intake, where the adapter maps `report_gap`; otherwise the command that would file it is named, or you are told the file itself is the artifact
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

## Where this sits in the Spec Kit ecosystem

The extension catalog has 170+ community extensions. This one deliberately owns a narrow slice and reuses the rest. **If an installed extension already does something, this one points at it rather than reimplementing it.**

### Prior art

Nothing in the catalog gates spec-driven development on a design system's own inventory. The closest neighbours solve adjacent problems and compose rather than compete:

| Extension | What it does | Relationship |
|---|---|---|
| `figma` | Grounds spec/plan/tasks in Figma design context via REST or MCP | Complementary: Figma is design intent, this is the shipped component inventory |
| `figma-starter` | Turns Figma screens into per-screen specs | Upstream: its specs then pass through this gate |
| `wireframe` | SVG wireframes that become spec constraints honored by plan/tasks/implement | Same pattern, different artifact |
| `a11y-governance` (preset) | WCAG 2.2 AA governance | Overlaps on the accessibility dimension only; run both |
| [`adrkit`](https://github.com/mbeacom/adrkit) | Machine-readable ADRs, decision memory keyed by file path | The ledger is keyed by UI capability and holds every walk; rungs 4–5 are what deserve promoting to a real ADR |

### Memory: reuse `.specify/memory/`

The ledger lives at `.specify/memory/design-decisions.yml` on purpose. That directory is Spec Kit's own memory location, and the `memory-loader` extension loads everything in it before lifecycle commands — so if you run it, the ledger reaches agent context with no integration work from either side. `memory`, `memory-md` and `dubsar` occupy the same space; none of them needed to be reimplemented here.

### Issues and RFCs — both directions

A design system request travels in both directions, and Spec Kit already has extensions for each. **This extension builds neither importer nor exporter.**

**Outbound — a gap you found becomes a proposal.** A rung-5 gap record is written as a standalone `design-system-gap-<slug>.md`: an RFC carrying the capability needed, the alternatives searched, why each is insufficient, and the proposed scope. It is a complete, reviewable document produced as a by-product of the gate rather than written from scratch. Where it goes is your choice:

| You run | Route |
|---|---|
| A design system CLI with intake (e.g. Astryx `gap-report`) | Filed directly with the owning package — the shortest path |
| Core Spec Kit | `/speckit.taskstoissues` → GitHub Issues |
| `jira`, `jira-mirror`, `linear`, `azure-devops` | Whichever you already sync with |
| Nothing | The RFC file *is* the artifact — commit it, paste it, or open it as a PR against the design system repo |

File it against the **design system's** project, not the product team's. With the `jira` extension a local override is usually enough:

```yaml
# .specify/extensions/jira/jira-config.local.yml
project:
  key: "DESIGNSYS"
```

**Inbound — a request arrives from the community.** Someone files "we need a date range picker" as a GitHub issue, a GitLab issue, or a Jira ticket. `github-issues`, `issue` and `gh-triage` already turn those into spec artifacts; `intake` normalizes PRDs and design evidence; the official `assess` extension shapes a raw idea before SDD begins. Install whichever fits your tracker.

What this extension adds to an inbound request is the triage: **the same ladder that stops a product team from building a duplicate also answers whether an incoming request is actually a gap.** Rung 0 checks whether it was already decided; rungs 1–4 check whether the system already covers it. A large share of incoming component requests turn out to be answered by an existing component under a name the requester did not know.

One integration note: the gate is hooked to `before_plan`, not to `specify`. So however a spec came into existence — typed by hand, imported from an issue, generated from Figma — **planning is still gated**. If the spec arrived from an importer rather than `/speckit.specify`, the `after_specify` hook will not have fired, so run `/speckit.designsys.sync` once to populate its design requirements.

### Ordering

The hooks do not collide — this gates at `before_plan`, tracker extensions publish at `after_tasks`:

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

That middle step is the one worth noticing: by the time tickets are created, each surface is already resolved and its constraints recorded. Whoever picks up the ticket reads *"use Calendar + Popover, tokens `space.*`, states default/focus/disabled/error"* instead of re-deciding it in the ticket comments — which is where design drift gets reintroduced after the gate has done its job.

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
