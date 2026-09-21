# Design System Extension for Spec Kit

[![Spec Kit](https://img.shields.io/badge/spec--kit-extension-blue?logo=github)](https://github.com/github/spec-kit)
[![Version](https://img.shields.io/badge/version-0.1.0-green)](https://github.com/artursopelnik/spec-kit-design-system/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Make your design system an active constraint and source of knowledge throughout spec-driven development.
Give it an RFC. It autonomously runs the [Spec Kit](https://github.com/github/spec-kit) workflow and implements the change using your design system. It does not model your design system, it asks yours.

```text
/speckit.design.run docs/rfcs/newsletter-footer.md
```

That is the whole interface. You do not drive the phases, manage context, or configure the workflow.

## Features

- **Works with any design system.** A short YAML adapter maps a small capability contract onto whatever your system exposes. Ships with `shadcn`, `mui`, `antd`, `chakra`, `radix`, `ark-ui`, `static-json` and an `example` template. `adapter: auto` detects the right one.
- **Reuse first, create last.** Every UI need climbs a ladder before anything new is built: Recall → Reuse → Compose → Extend → Create. A genuine gap is sent to your design system's intake, when its CLI offers one. Otherwise it stays documented in the feature.
- **Remembers every decision.** Each ladder walk is saved in a committed ledger keyed by UI capability. The next feature that needs a date range reads the answer instead of searching again, even when it words the need differently.
- **Lean context, nothing out of reach.** Each phase starts with only what it needs, never the whole inventory. Everything else stays one call away, so the agent can still ask for it when it does.
- **A gate that actually blocks.** `/speckit.plan` does not start until every UI surface has a documented resolution: candidates searched, and why the chosen rung is the lowest that holds. Design rules become numbered spec requirements (`DS-001: … MUST …`) with acceptance criteria.
- **Validated by your design system, not by the implementer.** After implementing, a separate pass checks the result against the spec and the ladder decisions, and runs your design system's own lint or token audit when the adapter maps one. Findings go back into implementation and are re-validated, up to 3 rounds.

### Why you need this Extension

Spec Kit's hooks (`before_plan`, `after_implement`, …) give you the *when*. You still have to build the *what*:

- **Asking your design system**, not guessing, through an adapter (CLI, MCP, or files) that works with any design system.
- **A gate that fails closed.** If the design system can't be reached, planning stops. It never silently continues as if the design system had nothing to say.
- **Validation that converges**: findings are tracked as checkboxes and re-checked in bounded rounds, instead of one prompt that says "review against the design system".
- **A ledger** of Reuse → Compose → Extend → Create decisions, so the same call isn't re-argued in every feature.

If you only need a reminder before planning, a hook of your own is enough. If you want the design system to be a real constraint, this is that hook set, already built and tested.

### Does it actually help?

[`benchmarks/`](benchmarks/) answers this with numbers instead of conviction: the same RFC run by the agent alone, with Spec Kit, and with this extension, against trimmed snapshots of shadcn/ui, Radix UI and MUI. Every arm is handed the design system in the same place, and every measure is computable from any arm's output, so none of them rewards the extension for merely having run.

The scores also read as pass or fail, so a result can be stated plainly — *"used the component the system already had in 9 of 10 runs, against 4 of 10 without it"* — beside what each arm cost in tokens and money, because scoring higher at three times the cost is a trade, not a win.

**No results are published yet.** The suite ships the harness, the cases and the scorer; the numbers need an agent, many runs and a stated model. [benchmarks/README.md](benchmarks/README.md) says what to publish alongside one.

## What is an RFC?

An RFC (request for comments) is a short document that says **what should change and why**, before anyone builds it. It is the only input this extension takes. It is not a spec: no component names, no implementation, no design decisions. Those come out of the workflow.

Where it lives does not matter: a markdown file, a GitHub or GitLab issue, a Jira ticket, text an MCP server handed you. The extension takes the text and ignores provenance. None of those integrations live here; compose an extension such as [spec-kit-jira](https://github.com/mbachorik/spec-kit-jira) instead.

### What one looks like

```markdown
# RFC: Newsletter signup in the footer

## Problem
Visitors who like the blog have no way to hear about new posts.

## Proposal
A place in the footer to enter an email address and subscribe. After
subscribing, the visitor sees a confirmation.

## Out of scope
Managing or cancelling subscriptions.

## Acceptance criteria
- [ ] A valid email can be submitted
- [ ] An invalid email shows an error
- [ ] The visitor sees a confirmation afterwards

## Open questions
- Double opt-in by email?
```

The RFC never states its type. This one is a UI feature, and the extension works that out from the text. More on that [below](#types).

### Types

There is no fixed set of RFC types and nothing to declare. Write what fits:

| Kind | Example | What happens |
|---|---|---|
| UI feature | "Newsletter signup in the footer" | Full workflow, your design system is consulted at every phase |
| UI change | "Make the toolbar usable on mobile" | Same, held to rules such as reflow and touch targets |
| UI bug | "The error message on the login form is unreadable" | Same, checked against your tokens and states instead of a one-off fix |

Start from [templates/rfc-template.md](templates/rfc-template.md).

## The ladder

The central rule: **Recall → Reuse → Compose → Extend → Create**. Before a new component is proposed or built, each rung is tried in order.

| Rung | Question |
|---|---|
| 0. Recall | Has another feature already decided this? |
| 1. Reuse | Does an existing component cover it? |
| 2. Compose (pattern) | Does an existing pattern cover the arrangement? |
| 3. Compose (components) | Can existing components be combined? |
| 4. Extend | Can a component be extended through a sanctioned mechanism? |
| 5. Create | Only when 1 through 4 are documented as insufficient. |

The goal is DRY for UI: share and adapt what exists, build new only as a last resort.

**A rung is never rejected on a hunch.** Rejecting one means naming the candidates searched and why each is insufficient. "Doesn't fit" is not a reason.

**Describe capabilities, not components.** Write "a control for picking a start and end date", never "a DateRangePicker". Naming the component pre-decides the ladder.

**Create is a legitimate outcome, as long as it is visible.** It comes with a gap record, the argued case for a new component:

```markdown
# Gap record: DateRangePicker

**Surface**: selection of a start and end date

## Existing alternatives searched
| Candidate | Source | Why insufficient |
|---|---|---|
| DatePicker | component | Single date only; no range semantics |
| Calendar | component | Display-only; no input affordance |
| Select | component | Wrong interaction model; enumerable options only |
| Popover | component | Container primitive; solves placement, not the control |

## Composition attempted
Calendar in Popover with two DatePickers, rejected because range validation
has to live above both fields, which the composition cannot express without
reaching into DatePicker internals.

## Proposal
**Impact**: new component
```

This separates a real gap the design system should close from a search that was not thorough enough.

Every outcome is written to the committed ledger, keyed by UI capability. That is what Recall (rung 0) reads.

The ladder is what runs in the **Plan** step below, and what the gate checks before planning may start.

## How it works

```text
RFC
 ↓
Clarify      what the RFC does not say
 ↓
Specify      a spec naming your design system's real components and tokens
 ↓
Plan         Reuse → Compose → Extend → Create, decided against the real system
 ↓
Tasks        the plan broken into steps
 ↓
Implement    against the components' real props, states and tokens
 ↓
Validate     an independent pass, not the implementer signing off its own work
 ↓
Fix          findings feed back in, then validate again
 ↓
Verify       RFC criteria, spec requirements and principles checked over the whole change
 ↓
Done
```

## Quick start

**Prerequisites:** Spec Kit `>=1.0.0,<2.0.0`.

1. Install from a clone, inside your Spec Kit project:

   ```bash
   git clone https://github.com/artursopelnik/spec-kit-design-system

   specify extension add --dev /path/to/spec-kit-design-system
   specify preset add --dev /path/to/spec-kit-design-system/preset
   ```

2. Run it on an RFC. The adapter is detected, so there is nothing to configure:

   ```text
   /speckit.design.run docs/rfcs/newsletter-footer.md
   ```

> [!NOTE]
> No release archive is published yet, so a clone is the only install path. The preset installs separately because extensions can only *replace* templates, which would fork your `spec-template`, while presets can *append*, composing the design sections in without forking anything.

> [!IMPORTANT]
> Your design system must be legible to an agent: a CLI, a registry, or a generated JSON file. If it exists only as a Figma library and tribal knowledge, there is nothing to ask.

Want to see it first? [Try the demo](#try-it-without-a-design-system).

## Commands

You need the first one. The rest are what it drives, and they also fire as Spec Kit hooks, so they hold for anyone working phase by phase.

| Command | Hook | Purpose |
|---|---|---|
| `/speckit.design.run <rfc>` | | The whole workflow. The one to remember. |
| `/speckit.design.context` | `after_specify` | Resolves principles and design system context into the spec |
| `/speckit.design.check` | `before_plan` | Walks the reuse ladder and gates planning on it (blocking) |
| `/speckit.design.validate` | `after_implement` | The independent checker |

## Your design system

The extension asks yours through a thin adapter that maps capabilities (`search`, `component`, `tokens`, `principles`, ...) onto a CLI call or a file read.

| Adapter | For |
|---|---|
| `shadcn` | [shadcn/ui](https://ui.shadcn.com), via its CLI and registries. It publishes no machine-readable principles, so the default set applies unless you set `principles.source` |
| `mui` | [MUI](https://mui.com) (Material UI), via an inventory file |
| `antd` | [Ant Design](https://ant.design), via an inventory file |
| `chakra` | [Chakra UI](https://chakra-ui.com), via an inventory file |
| `radix` | [Radix UI](https://www.radix-ui.com), via an inventory file |
| `ark-ui` | [Ark UI](https://ark-ui.com), via an inventory file |
| `static-json` | Any system with no CLI: point it at a generated inventory file |
| `example` | Template to copy for your own CLI |

The library adapters read an inventory file your project generates (default `.design-system/inventory.json`, shape in [adapters/static-json.yml](adapters/static-json.yml)), because those libraries have no CLI to ask. Without the file the gate stops rather than guess.

Adapters only map. They never hold rules or component knowledge, otherwise your design system would stop being the source of truth. Writing one: [docs/adapters.md](docs/adapters.md).

### Principles

Principles are the rules the work is held to. They resolve from exactly one source, never merged:

```text
1. your design system's CLI      ──┐
2. static data it ships          ──┼── first one that answers wins
3. a small default set           ──┘
```

The default set is a fallback of fourteen broadly applicable principles (semantic markup, keyboard operation, focus, touch targets, reflow, reduced motion, state coverage, token use). It carries no colors, breakpoints or sizes, because those belong to your system. If your system publishes principles without a CLI, name the file:

```yaml
principles:
  source: "node_modules/@acme/design-system/principles.yml"
```

See [principles/example.yml](principles/example.yml) for the shape.

## Configuration

For most projects the whole file (`.specify/extensions/design/design-config.yml`) is one line:

```yaml
adapter: shadcn   # or auto (default), mui, antd, chakra, radix, ark-ui, static-json, your own
```

Everything else is optional and documented in [config-template.yml](config-template.yml): a `bin` override, a `cwd` for monorepos, a principles `source`, per-capability overrides, `workflow.max_validation_rounds`, and `gate.enforce: false` while adopting. `SPECKIT_DESIGN_*` environment variables and a gitignored `design-config.local.yml` override the committed config.

## Try it without a design system

```bash
./examples/setup-demo.sh /tmp/design-demo
cd /tmp/design-demo
```

Builds a throwaway project wired to a fixture design system (ten components, two patterns, tokens, breakpoints, principles). Walk it with [examples/README.md](examples/README.md).

Or wire it to one of the real systems the benchmarks use, with the RFC and the code a benchmark case is about, and run the workflow on it:

```bash
./examples/setup-demo.sh /tmp/shadcn-demo --system shadcn --case date-range-filter
./examples/setup-demo.sh /tmp/radix-demo  --system radix  --case destructive-confirm
./examples/setup-demo.sh /tmp/mui-demo    --system mui    --case toolbar-mobile
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "design system could not be reached" | The gate probes for real: CLI missing, wrong binary, or inventory not where `source` says. Check with `ds.sh query describe --json`. |
| Principles say `principles_source: default` | Your system supplied none. Map the `principles` capability in your adapter or set `principles.source`. |
| Principles say `principles_source: unavailable` | Nothing answered and `principles.default` is `false`, so nothing is in force. Intended while adopting; a gate that requires principles fails closed here rather than passing on an empty set. |
| A principle is listed under `unenforceable` | It states no MUST/SHOULD, or carries no `verify` step, so nothing can be checked against it. It is still returned and still worth reading — add a `verify` step at the source to make it citable. |
| A capability returns `available: false` | Unmapped in the adapter, or the call failed. The `reason` says which. The run degrades, it does not fail. |
| `breakpoints` returns the whole token set | Most systems have no breakpoint command, so the adapter maps both onto the token call. Carve out the slice with `result_paths` or `pick` ([adapters](docs/adapters.md#one-command-two-questions)); until then every phase that asks pays for the tokens twice, which `ds.sh context <phase>` reports in `notes`. |
| A phase's context is expensive | Every answer reports `bytes` and every context a `sizes` block, so start by looking. Narrow the mapping first, then the call: `ds.sh query list_components --fields name,description`. |
| "PyYAML is required" | `pip install pyyaml` into the interpreter running the scripts. |
| `/usr/bin/env: 'bash\r': No such file or directory` | The checkout converted LF to CRLF — Git for Windows does this by default (`core.autocrlf=true`), and a script that went through it is not executable on Linux, WSL or in a container sharing that checkout. `.gitattributes` pins LF for new checkouts; an existing one is refreshed with `git rm --cached -r . && git reset --hard`. Meanwhile the shim is optional: `python3 .specify/extensions/design/scripts/python/design.py gate --json` does the same thing. |
| The gate keeps failing | Read what it names: a surface with no resolution, a Create with no gap record, or a rung rejected on too few candidates. `gate.enforce: false` downgrades it to a warning. |

## Architecture

Three layers, only the first is public:

- **Commands** (`commands/`): agent-facing prose describing what to do, in what order, and what not to accept.
- **One script** (`scripts/python/design.py`, with a bash shim): prerequisites, capability dispatch, principles, focused context, workflow position, RFC parsing, the ledger. Always emits JSON.
- **Adapters** (`adapters/`): declarative YAML, no code.

There is no run-state file. Workflow position is read from artifacts the work already produces (spec, plan, tasks, design document), so an interrupted run resumes by reading.

More: [architecture](docs/architecture.md) · [autonomous workflow](docs/autonomous-workflow.md) · [adapters](docs/adapters.md)

## Development

```bash
pip install pytest pyyaml
python -m pytest
```

CI also installs the extension into a real Spec Kit project, validates the manifests, checks that hooks register, and walks the example end to end.

```text
commands/      agent-facing command bodies
scripts/       ds.sh shim + design.py
adapters/      capability mappings
principles/    default fallback set and an example
preset/        spec, plan and constitution addenda
templates/     RFC template
examples/      fixture design system and demo project
benchmarks/    cases, design system snapshots, scorer and report
docs/          architecture, adapters, workflow
tests/         pytest suite, one file per concern
.github/       CI: tests, shell and YAML checks, real Spec Kit install
extension.yml  extension manifest
config-template.yml  project config template
CHANGELOG.md   release notes
LICENSE        MIT
```
