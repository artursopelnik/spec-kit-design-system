---
description: "Resolve design system context for the current specification and write it into the spec as explicit requirements"
---

# Design System Sync

Give the specification its design system context while it is still a specification. This runs as an **`after_specify` hook**, so the spec that reaches `/speckit.plan` already states which parts of the system are in play and which design dimensions must be answered.

This command does not decide what to build — that is the ladder's job in `/speckit.designsys.check`. It establishes what the design system already offers for this problem, so the decision is made against evidence rather than memory.

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

Where bash is unavailable, call the module directly — it behaves identically:
`python3 .specify/extensions/designsys/scripts/python/designsys.py gate --json`

Parse for `FEATURE_SPEC`, `CONFIG`, `ADAPTER`, `CAPABILITIES`, `REACHABLE`, `UNREACHABLE_REASON`, `UI_BEARING`.

**If `UI_BEARING` is `false`**: report that no user-facing surface was found and stop without editing the spec.

**If `REACHABLE` is `false`**: report `UNREACHABLE_REASON` plainly and stop. Do not fill the spec with remembered component names — a wrong inventory is worse than none, because the ladder will then be walked against fiction.

### Checking the mapping

Where the adapter maps `describe`, the design system can state its own command surface:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json describe
```

Run this when a capability starts failing in a way that looks like a flag change rather than an outage. Compare the returned commands against the adapter's mapped invocations and report any that no longer exist — the adapter file is then out of date and a human should update it. Nothing rewrites it automatically: an adapter is committed repository content, and silently editing it would hide a breaking upstream change rather than surface it.

## Outline

### 1. Read the spec for user-facing surfaces

From `FEATURE_SPEC`, work through `## User Scenarios & Testing` and `## Requirements`. List every distinct surface the feature implies, phrased as a **capability**, not as a component name. The point is to search the design system with an open question.

### 2. Check what has already been decided

For each surface, look it up in the decision ledger first:

```
.specify/extensions/designsys/scripts/bash/ds-ledger.sh --json lookup "<capability phrase>"
```

A hit means another feature already resolved this surface. Surfacing it here — while the spec is still being written — is cheaper than surfacing it at the gate, because the spec can simply state the established answer as a requirement. Note the decision id in the candidates table so the gate can adopt it rather than re-deriving it.

A hit does not end the search: still query the design system in step 3, because the spec's requirements should describe real component capabilities, and because a `stale` hit needs re-validation anyway.

### 3. Query the design system

For each surface, run at least two differently-worded searches:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json search "<capability phrase>"
```

Pull detail on the strongest hits (`ds-query.sh --json component "<Name>"`, `--json pattern "<Name>"`). Also fetch the token vocabulary once (`ds-query.sh --json tokens`) so the spec can reference real token names.

Record what you find. Do not yet rule anything in or out — that is the gate's decision, made deliberately, with its reasoning written down.

### 4. Write the spec section

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

Cover each dimension in `audit.required_dimensions` from `CONFIG` — states, responsive, accessibility, tokens, interaction — with at least one requirement, or state explicitly why a dimension does not apply to this feature.

Where the design system's answer is genuinely unclear, use the spec's own idiom rather than guessing:

```
[NEEDS CLARIFICATION: system offers both Drawer and Modal for this flow — which is correct for a destructive confirmation?]
```

### 5. Add measurable success criteria

Add technology-agnostic entries under `## Success Criteria` for what design compliance means here — for example that the feature introduces no new component outside the design system, or that every interactive element is reachable by keyboard. Keep them measurable; "looks consistent" is not a criterion.

## Completion Report

Report which surfaces were identified, which components and patterns the system surfaced for each, the `DS-` requirements written, and any `[NEEDS CLARIFICATION]` markers left for the user.

## Done When

- [ ] Every user-facing surface was looked up in the decision ledger
- [ ] Every user-facing surface in the spec has been searched against the design system
- [ ] `## Design System Requirements` is populated with testable `DS-` IDs
- [ ] Every required dimension is covered or explicitly excluded with a reason
- [ ] Token references use real token names from the system, not invented ones
- [ ] Genuine ambiguities are marked `[NEEDS CLARIFICATION: ...]` rather than guessed
