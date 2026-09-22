# Design System Extension for Spec Kit

[![Spec Kit](https://img.shields.io/badge/spec--kit-extension-blue?logo=github)](https://github.com/github/spec-kit)
[![Version](https://img.shields.io/badge/version-0.1.0-green)](https://github.com/artursopelnik/spec-kit-design-system/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<p align="center">
  <b>You write the RFC. Your design system picks the components.</b><br>
  One command runs the whole <a href="https://github.com/github/spec-kit">Spec Kit</a> workflow, and every UI decision in it<br>
  is answered by <i>your</i> design system instead of guessed by the agent.
</p>

---

## What it does

You hand it an RFC:

```text
/speckit.design.run docs/rfcs/newsletter-footer.md
```

That is the whole interface. You do not drive the phases, manage context or
configure the workflow.

From that one line it asks what the RFC leaves open, writes a spec naming your
real components and tokens, plans, implements, and then checks the result. Every
answer about components, patterns, tokens and rules comes from your design
system, through a short adapter. This repo holds no component knowledge of its
own. It asks yours.

What that changes in practice:

- **It looks before it builds.** Every UI need climbs a ladder: Recall → Reuse →
  Compose → Extend → Create. Something new gets built only after the earlier
  rungs are documented as insufficient.
- **It remembers.** Each decision lands in a committed ledger, keyed by UI
  capability. The next feature that needs a date range reads the answer instead
  of searching again, even when it words the need differently.
- **It blocks.** `/speckit.plan` does not start until every UI surface has a
  documented resolution, and your design system's rules land in the spec as
  numbered requirements (`DS-001: ... MUST ...`) with acceptance criteria. If
  the design system cannot be reached, planning stops. It never continues as if
  your system had nothing to say.
- **It keeps the context lean.** Each phase starts with only what it needs,
  never the whole inventory. Everything else stays one call away, so the agent
  can still ask when it turns out to need it.
- **It checks its own work.** A separate pass validates the implementation
  against the spec and the ladder decisions, and runs your design system's lint
  or token audit when the adapter maps one. Findings go back into
  implementation, up to 3 rounds.
- **It fits any design system.** A short YAML adapter maps a small capability
  contract onto whatever your system exposes: a CLI, files, or an MCP tool.

Spec Kit's hooks give you the *when*. This is the *what*, already built and
tested.

## Quick start

**You need:** Spec Kit `>=1.0.0,<2.0.0`, and a design system an agent can read.
A CLI, a registry, or a generated JSON file. If it only exists as a Figma
library and tribal knowledge, there is nothing to ask.

**1. Install it into your Spec Kit project.**

```bash
git clone https://github.com/artursopelnik/spec-kit-design-system

specify extension add --dev /path/to/spec-kit-design-system
specify preset add --dev /path/to/spec-kit-design-system/preset
```

**2. Run it on an RFC.** The adapter is detected, so there is nothing to
configure:

```text
/speckit.design.run docs/rfcs/newsletter-footer.md
```

That's it. ✅

> [!NOTE]
> No release archive is published yet, so a clone is the only install path. The
> preset installs separately because extensions can only *replace* templates,
> which would fork your `spec-template`. Presets can *append*, so the design
> sections compose in without forking anything.

### Want to see it first?

```bash
./examples/setup-demo.sh /tmp/design-demo
cd /tmp/design-demo
```

That builds a throwaway project wired to a fixture design system: ten
components, two patterns, tokens, breakpoints, principles. Walk it with
[examples/README.md](examples/README.md).

Or point the demo at one of the real systems the benchmarks use, with the RFC
and the code a benchmark case is about:

```bash
./examples/setup-demo.sh /tmp/shadcn-demo --system shadcn --case date-range-filter
./examples/setup-demo.sh /tmp/radix-demo  --system radix  --case destructive-confirm
./examples/setup-demo.sh /tmp/mui-demo    --system mui    --case toolbar-mobile
```

## The RFC you write

An RFC says **what should change and why**, before anyone builds it. It is the
only input this extension takes. It is not a spec: no component names, no
implementation, no design decisions. Those come out of the workflow.

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

Start from [templates/rfc-template.md](templates/rfc-template.md).

Where the RFC lives does not matter: a markdown file, a GitHub or GitLab issue,
a Jira ticket, text an MCP server handed you. The extension takes the text and
ignores where it came from. None of those integrations live here; compose an
extension such as [spec-kit-jira](https://github.com/mbachorik/spec-kit-jira)
instead.

And you never declare a type. The RFC above is a UI feature, and the extension
works that out from the text:

| Kind | Example | What happens |
|---|---|---|
| UI feature | "Newsletter signup in the footer" | Full workflow, your design system is consulted at every phase |
| UI change | "Make the toolbar usable on mobile" | Same, held to rules such as reflow and touch targets |
| UI bug | "The error message on the login form is unreadable" | Same, checked against your tokens and states instead of a one-off fix |

## What happens after you hit enter

```text
RFC
 ↓
Clarify      what the RFC does not say
 ↓
Specify      a spec naming your design system's real components and tokens
 ↓
Plan         Recall → Reuse → Compose → Extend → Create, against the real system
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

You only need the first command below. The rest are what it drives, and they
also fire as Spec Kit hooks, so they hold for anyone working phase by phase.

| Command | Hook | Purpose |
|---|---|---|
| `/speckit.design.run <rfc>` | | The whole workflow. The one to remember. |
| `/speckit.design.context` | `after_specify` | Resolves principles and design system context into the spec |
| `/speckit.design.check` | `before_plan` | Walks the reuse ladder and gates planning on it (blocking) |
| `/speckit.design.validate` | `after_implement` | The independent checker |

## The ladder

The central rule: **Recall → Reuse → Compose → Extend → Create**. Before a new
component is proposed or built, each rung is tried in order.

| Rung | Question |
|---|---|
| 0. Recall | Has another feature already decided this? |
| 1. Reuse | Does an existing component cover it? |
| 2. Compose (pattern) | Does an existing pattern cover the arrangement? |
| 3. Compose (components) | Can existing components be combined? |
| 4. Extend | Can a component be extended through a sanctioned mechanism? |
| 5. Create | Only when 1 through 4 are documented as insufficient. |

It is DRY for UI: share and adapt what exists, build new as a last resort. Three
rules keep it honest.

**A rung is never rejected on a hunch.** Rejecting one means naming the
candidates searched and why each is insufficient. "Doesn't fit" is not a reason.

**Describe capabilities, not components.** Write "a control for picking a start
and end date", never "a DateRangePicker". Naming the component pre-decides the
ladder.

**Create is fine, as long as it is visible.** It comes with a gap record, the
argued case for a new component:

```markdown
# Gap: selection of a start and end date

**Feature**: 003-booking-filters · **Design system**: acme-ds · **Version**: 1.4.2

## What is needed
A control for choosing a start and an end date together, where the two are
validated against each other.

## What was searched
| Candidate | Rung | Why it is insufficient |
|---|---|---|
| DatePicker | reuse | Single date only; no range semantics |
| Calendar | reuse | Display-only; no input affordance |
| Select | reuse | Wrong interaction model; enumerable options only |
| Calendar + Popover + two DatePickers | compose | Range validation has to live above both fields, which the composition cannot express without reaching into DatePicker internals |

## What we are building instead
A DateRangeField in `src/components/`, built from the system's tokens and its
Popover primitive.

## What the design system could do
Give DatePicker a range mode, or ship the paired control as a pattern.
```

Note the title. The gap is named by the capability, not by the component that
will close it. Calling it `DateRangePicker` would pre-decide the very question
the record exists to argue. That is what separates a real gap your design system
should close from a search that was not thorough enough.

A genuine gap is sent to your design system's intake when its CLI offers one.
Otherwise it stays documented in the feature. Either way the outcome goes into
the ledger, keyed by capability, and that is what Recall reads next time.

## Your design system

The extension asks yours through a thin adapter that maps capabilities
(`search`, `component`, `tokens`, `principles`, ...) onto a CLI call, a file
read, or an MCP tool. One adapter can mix all three.

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

The library adapters read an inventory file your project generates (default
`.design-system/inventory.json`, shape in
[adapters/static-json.yml](adapters/static-json.yml)), because those libraries
have no CLI to ask. Without the file the gate stops rather than guess.

Adapters only map. They never hold rules or component knowledge, otherwise your
design system would stop being the source of truth. Writing one:
[docs/adapters.md](docs/adapters.md).

### Principles

Principles are the rules the work is held to. They resolve from exactly one
source, never merged:

```text
1. your design system's CLI      ──┐
2. static data it ships          ──┼── first one that answers wins
3. a small default set           ──┘
```

The default set is fourteen broadly applicable principles: semantic markup,
keyboard operation, focus, touch targets, reflow, reduced motion, state
coverage, token use. It carries no colors, breakpoints or sizes, because those
belong to your system.

If your system publishes principles without a CLI, name the file:

```yaml
principles:
  source: "node_modules/@acme/design-system/principles.yml"
```

See [principles/example.yml](principles/example.yml) for the shape.

### Definition of Done

Principles are your design system's rules. A Definition of Done is your team's,
so the DoD is never asked of the design system, and **nothing ships as a
default**. If you keep one, write it in
`.specify/extensions/design/definition-of-done.md` as a plain list:

```markdown
# Definition of Done

Agreed in the design system guild, revisit each quarter.

- Unit tests for every new component
- A Storybook story per variant
- Changelog entry
- Design review signed off by someone who did not build it
```

No schema, no ids, no `verify` field. Headings and prose around the list are
ignored; the bullets are the DoD. Validation checks each item against what was
actually built and raises unmet ones as ordinary `DS-F-nnn` findings, so they go
through the same fix loop as everything else, and the feature is not done until
they are resolved or argued in writing.

That list is an example to copy and edit, not a starting set. A DoD that arrived
with an extension would raise findings against rules nobody at your place agreed
to, which is why the file is empty until you write it. No file means no DoD:
nothing is checked, nothing nags. To keep it elsewhere, a shared file in a
monorepo or one your design system package ships, point `dod.source` at it.

### Configuration

For most projects the whole file
(`.specify/extensions/design/design-config.yml`) is one line:

```yaml
adapter: shadcn   # or auto (default), mui, antd, chakra, radix, ark-ui, static-json, your own
```

Everything else is optional and documented in
[config-template.yml](config-template.yml): a `bin` override, a `cwd` for
monorepos, a principles `source`, a `dod.source`, per-capability overrides,
`workflow.max_validation_rounds`, and `gate.enforce: false` while adopting.
`SPECKIT_DESIGN_*` environment variables and a gitignored
`design-config.local.yml` override the committed config.

## Does it actually help?

[`benchmarks/`](benchmarks/) is there to answer that with numbers: the same RFC
run by the agent alone, with Spec Kit, and with this extension, against trimmed
snapshots of shadcn/ui, Radix UI and MUI. Every arm is handed the design system
in the same place, and every measure is computable from any arm's output, so
none of them rewards the extension for merely having run.

The scores also read as pass or fail, so a result can be stated plainly, like
*"used the component the system already had in 9 of 10 runs, against 4 of 10
without it"*, beside what each arm cost in tokens and money. Scoring higher at
three times the cost is a trade, not a win.

**No results are published yet.** The suite ships the harness, the cases and the
scorer. The numbers need an agent, many runs and a stated model.
[benchmarks/README.md](benchmarks/README.md) says what to publish alongside one.

## How it is built

Three layers, only the first is public:

- **Commands** (`commands/`): agent-facing prose describing what to do, in what
  order, and what not to accept.
- **One script** (`scripts/python/design.py`, with a bash shim): prerequisites,
  capability dispatch, principles, focused context, workflow position, RFC
  parsing, the ledger. Always emits JSON.
- **Adapters** (`adapters/`): declarative YAML, no code.

There is no run-state file. Workflow position is read from the artifacts the
work already produces (spec, plan, tasks, design document), so an interrupted
run resumes by reading.

More: [architecture](docs/architecture.md) · [autonomous
workflow](docs/autonomous-workflow.md) · [adapters](docs/adapters.md) ·
[troubleshooting](docs/troubleshooting.md)

## Development

```bash
pip install pytest pyyaml
python -m pytest
```

CI also installs the extension into a real Spec Kit project, validates the
manifests, checks that hooks register, and walks the example end to end.

```text
commands/      agent-facing command bodies
scripts/       ds.sh shim + design.py
adapters/      capability mappings
principles/    default fallback set and an example
preset/        spec, plan and constitution addenda
templates/     RFC template
examples/      fixture design system and demo project
benchmarks/    cases, design system snapshots, scorer and report
docs/          architecture, adapters, workflow, troubleshooting
tests/         pytest suite, one file per concern
```

## License

MIT. See [LICENSE](LICENSE).
