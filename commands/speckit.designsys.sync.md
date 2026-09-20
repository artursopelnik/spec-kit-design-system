---
description: "Resolve design system context for the current specification and write it into the spec as explicit requirements"
---

# Design System Sync

Give the specification its design system context while it is still a specification. This runs as an **`after_specify` hook**, so the spec that reaches `/speckit.plan` already states which parts of the system are in play and which design dimensions must be answered.

This command does not decide what to build. That is the ladder's job in `/speckit.designsys.check`. It establishes what the design system already offers for this problem, so the decision is made against evidence rather than memory.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

Run:

```
.specify/extensions/designsys/scripts/bash/check-design-gate.sh --json
```

Where bash is unavailable, call the module directly. It behaves identically:
`python3 .specify/extensions/designsys/scripts/python/designsys.py gate --json`

Parse for `FEATURE_SPEC`, `CONFIG`, `ADAPTER`, `CAPABILITIES`, `REACHABLE`, `UNREACHABLE_REASON`, `UI_BEARING`.

**If `UI_BEARING` is `false`**: report that no user-facing surface was found and stop without editing the spec.

**If `REACHABLE` is `false`**: report `UNREACHABLE_REASON` plainly and stop. Do not fill the spec with remembered component names. A wrong inventory is worse than none, because the ladder will then be walked against fiction.

### Checking the mapping

Where the adapter maps `describe`, the design system can state its own command surface:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json describe
```

Run this when a capability starts failing in a way that looks like a flag change rather than an outage. Compare the returned commands against the adapter's mapped invocations and report any that no longer exist, which means the adapter file is out of date and a human should update it. Nothing rewrites it automatically: an adapter is committed repository content, and silently editing it would hide a breaking upstream change rather than surface it.

## Outline

### 1. Read the spec for user-facing surfaces

From `FEATURE_SPEC`, work through `## User Scenarios & Testing` and `## Requirements`. List every distinct surface the feature implies, phrased as a **capability**, not as a component name. The point is to search the design system with an open question.

### 2. Check what has already been decided

For each surface, look it up in the decision ledger first:

```
.specify/extensions/designsys/scripts/bash/ds-ledger.sh --json lookup "<capability phrase>"
```

A hit means another feature already resolved this surface. Surfacing it here, while the spec is still being written, is cheaper than surfacing it at the gate, because the spec can simply state the established answer as a requirement. Note the decision id in the candidates table so the gate can adopt it rather than re-deriving it.

A hit does not end the search: still query the design system in step 3, because the spec's requirements should describe real component capabilities, and because a `stale` hit needs re-validation anyway.

### 3. Query the design system

For each surface, run at least two differently-worded searches:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json search "<capability phrase>"
```

Pull detail on the strongest hits (`ds-query.sh --json component "<Name>"`, `--json pattern "<Name>"`).

Record what you find. Do not yet rule anything in or out. That is the gate's decision, made deliberately, with its reasoning written down.

### 4. Fetch the system's actual vocabulary

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json tokens
.specify/extensions/designsys/scripts/bash/ds-query.sh --json breakpoints
```

This step exists because "use our colors" and "use our breakpoints" are unenforceable instructions on their own. The agent has to know what they are, by name, or it will reach for something plausible. So put the **real names** into the spec: `color.surface.raised`, `space.3`, `md`, `lg`. Never a hex value, never a pixel width, and never a name you have not seen come back from one of these calls.

If `breakpoints` is unmapped, check whether the token response already contains them. If neither has them, say so in the spec rather than inventing a set, and mark it `[NEEDS CLARIFICATION]`. A guessed breakpoint set is worse than an admitted gap, because it will look authoritative in every downstream artifact.

### 5. Collect the baseline requirements

Some requirements hold for every design system and therefore appear in no spec. Nobody writes "it has to be accessible" or "it has to work on a phone", so nobody checks them, so each feature decides for itself and decides differently.

First classify what this feature actually involves, from: `interactive`, `layout`, `text`, `media`, `motion`. Then:

```
.specify/extensions/designsys/scripts/bash/ds-baseline.sh --json --applies-to interactive,layout
```

Classify honestly. Over-claiming buries the spec in rules that do not apply; under-claiming is how a control ships without a focus state. If the feature has anything the user can operate, it is `interactive`. If anything occupies space and reflows, it is `layout`.

The response carries each rule's `id`, `requirement`, `verify` and `standard`. These are not suggestions and they do not need to be re-derived; they are already written as testable requirements.

### 6. Write the spec section

Fill in the `## Design System Requirements` section of `FEATURE_SPEC`. The `designsys` preset appends this section to the spec template, so it is already scaffolded with its dimension table and candidate table. If the preset is not installed, create the section at the end of the spec instead.

Use `DS-` prefixed, testable requirement IDs in the same MUST/SHOULD style as the functional requirements above:

```markdown
### Requirements

- **DS-001**: The date range control MUST be built from the design system rather than
  bespoke markup; candidates surfaced: DatePicker, Calendar, Popover.
- **DS-002**: All spacing and color values MUST reference design tokens
  (`space.*`, `color.surface.*`); raw hex or px values are not acceptable.
- **DS-003**: Every interactive element MUST handle default, hover, focus, active,
  disabled, loading and error states.
- **DS-004**: The layout MUST behave correctly at all project breakpoints, with the
  filter row collapsing to a stacked form below `md`.
- **DS-005**: The control MUST be operable by keyboard alone and expose an accessible
  name; focus order follows visual order.
```

Then record the applicable baseline rules. Do **not** restate each one in full; cite them by id in a table, since the text lives in `baseline.yml` and duplicating it into every spec creates two sources of truth that will drift:

```markdown
### Baseline

These apply to every feature in this design system and are not restated here.
Surface kinds: interactive, layout.

| Rule | Dimension | Requirement |
|---|---|---|
| BL-A11Y-KEYBOARD | accessibility | Operable by keyboard alone (WCAG 2.1.1) |
| BL-A11Y-FOCUS-VISIBLE | accessibility | Focus indicator visible at every stop (WCAG 2.4.7) |
| BL-RESP-BREAKPOINTS | responsive | Behaviour specified at `sm`, `md`, `lg`, `xl` |
| BL-INPUT-NO-HOVER-ONLY | interaction | Nothing reachable only on hover (WCAG 1.4.13) |
| BL-STATE-COVERAGE | states | default, hover, focus, active, disabled, loading, error, empty |
| BL-TOKEN-NO-RAW-VALUES | tokens | Use `color.*`, `space.*`, `radius.*`; no raw hex or px |

Disabled for this project: none.
```

Fill the breakpoint names and token families from step 4, not from memory. A baseline row that says "use the right breakpoints" without naming them has not actually constrained anything.

Then cover each dimension in `audit.required_dimensions` from `CONFIG` (states, responsive, accessibility, tokens, interaction). A dimension is covered when a baseline rule or a `DS-` requirement speaks to it. Only write a feature-specific `DS-` requirement where this feature needs something **beyond** the baseline; repeating a baseline rule as a `DS-` entry is noise.

If `BASELINE_DISABLED` from the gate is non-empty, list the disabled rule ids and why. A rule switched off silently is worse than one never written.

Where the design system's answer is genuinely unclear, use the spec's own idiom rather than guessing:

```
[NEEDS CLARIFICATION: system offers both Drawer and Modal for this flow. Which is correct for a destructive confirmation?]
```

### 7. Add measurable success criteria

Add technology-agnostic entries under `## Success Criteria` for what design compliance means here, for example that the feature introduces no new component outside the design system, or that every interactive element is reachable by keyboard. Keep them measurable; "looks consistent" is not a criterion.

## Completion Report

Report which surfaces were identified, which components and patterns the system surfaced for each, the `DS-` requirements written, and any `[NEEDS CLARIFICATION]` markers left for the user.

## Done When

- [ ] Every user-facing surface was looked up in the decision ledger
- [ ] Every user-facing surface in the spec has been searched against the design system
- [ ] The feature's surface kinds were classified and the matching baseline rules cited by id
- [ ] Breakpoints and token families are named from what the CLI returned, never from memory
- [ ] `## Design System Requirements` is populated with testable `DS-` IDs for what this feature needs *beyond* the baseline
- [ ] Every required dimension is covered by a baseline rule or a `DS-` requirement
- [ ] Any disabled baseline rules are listed with a reason
- [ ] Genuine ambiguities are marked `[NEEDS CLARIFICATION: ...]` rather than guessed
