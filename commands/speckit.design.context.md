---
description: "Resolve the guidelines in force and the design system context for the current specification, and write them into the spec as explicit requirements"
---

# Design System Context

Give the specification its design system context while it is still a specification. This runs as an **`after_specify` hook**, so the spec that reaches `/speckit.plan` already states which parts of the system are in play and which design dimensions must be answered.

This command does not decide what to build. That is the ladder's job in `/speckit.design.check`. It establishes what the design system already offers for this problem, so the decision is made against evidence rather than memory.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

```
.specify/extensions/design/scripts/bash/ds.sh gate --json
```

Without bash, call the module directly; it behaves identically:
`python3 .specify/extensions/design/scripts/python/design.py gate --json`

Parse for `FEATURE_SPEC`, `CONFIG`, `ADAPTER`, `CAPABILITIES`, `REACHABLE`, `UNREACHABLE_REASON`, `UI_BEARING`, `GUIDELINES_SOURCE`.

**If `UI_BEARING` is `false`**: report that no user-facing surface was found and stop without editing the spec.

**If `REACHABLE` is `false`**: report `UNREACHABLE_REASON` plainly and stop. Do not fill the spec with remembered component names. A wrong inventory is worse than none, because the ladder will then be walked against fiction.

### Checking the mapping

Where the adapter maps `describe`, the design system can state its own command surface:

```
.specify/extensions/design/scripts/bash/ds.sh query describe --json
```

Run this when a capability starts failing in a way that looks like a flag change rather than an outage. Compare the returned commands against the adapter's mapped invocations and report any that no longer exist, which means the adapter file is out of date and a human should update it. Nothing rewrites it automatically: an adapter is committed repository content, and silently editing it would hide a breaking upstream change rather than surface it.

## Outline

### 1. Read the spec for user-facing surfaces

From `FEATURE_SPEC`, work through `## User Scenarios & Testing` and `## Requirements`. List every distinct surface the feature implies, phrased as a **capability**, not as a component name. The point is to search the design system with an open question.

### 2. Check what has already been decided

For each surface, look it up in the decision ledger first:

```
.specify/extensions/design/scripts/bash/ds.sh ledger lookup "<capability phrase>" --json
```

A hit means another feature already resolved this surface. Surfacing it here, while the spec is still being written, is cheaper than surfacing it at the gate, because the spec can simply state the established answer as a requirement. Note the decision id in the candidates table so the gate can adopt it rather than re-deriving it.

A hit does not end the search: still query the design system in step 3, because the spec's requirements should describe real component capabilities, and because a `stale` hit needs re-validation anyway.

### 3. Query the design system

For each surface, run at least two differently-worded searches:

```
.specify/extensions/design/scripts/bash/ds.sh query search "<capability phrase>" --json
```

Pull detail on the strongest hits (`ds.sh query component "<Name>"`, `ds.sh query pattern "<Name>"`).

Record what you find. Do not yet rule anything in or out. That is the gate's decision, made deliberately, with its reasoning written down.

### 4. Fetch the system's actual vocabulary

```
.specify/extensions/design/scripts/bash/ds.sh query tokens --json
.specify/extensions/design/scripts/bash/ds.sh query breakpoints --json
```

**If `HAS_TOKENS` is false**, skip tokens: the design system has no token layer, so there are no names to look up and none to invent. Say so in the spec and drop the `tokens` dimension. Breakpoints still apply if mapped.

This step exists because "use our colors" and "use our breakpoints" are unenforceable instructions on their own. The agent has to know what they are, by name, or it will reach for something plausible. So put the **real names** into the spec: `color.surface.raised`, `space.3`, `md`, `lg`. Never a hex value, never a pixel width, and never a name you have not seen come back from one of these calls.

If `breakpoints` is unmapped, check whether the token response already contains them. If neither has them, say so in the spec rather than inventing a set, and mark it `[NEEDS CLARIFICATION]`. A guessed breakpoint set is worse than an admitted gap, because it will look authoritative in every downstream artifact.

If `breakpoints` answers with the *same* payload as `tokens` — most systems have no breakpoint command, so the adapter maps both onto the token call — the names are still in there and the spec can be written. Say so in the completion report: the adapter can carve the breakpoint slice out of that response (`result_path`, `result_paths`, `pick`), and until it does, every phase that asks for breakpoints pays for the whole token set a second time. Look for a `notes` entry from `ds.sh context`, which says it outright when the mapping resolved to nothing.

Where a listing is large and you only need the shape of it, `--fields` trims what comes back without changing what is available:

```
.specify/extensions/design/scripts/bash/ds.sh query list_components --fields name,description --json
```

That is a cheap survey, not a smaller design system. Pull the full record for anything you are going to build against.

### 5. Collect the guidelines in force

First classify what this feature actually involves, from: `interactive`, `layout`, `text`, `media`, `motion`. Then:

```
.specify/extensions/design/scripts/bash/ds.sh guidelines --applies-to interactive,layout --json
```

Classify honestly. Over-claiming buries the spec in guidelines that do not apply; under-claiming is how a control ships without a focus state. If the feature has anything the user can operate, it is `interactive`. If anything occupies space and reflows, it is `layout`.

Classify from the **components you are about to use**, not only from the feature description. A booking filter does not sound like it involves motion, but if it opens a Popover or a Modal then it animates, and `motion` applies. Read the `avoid` and `usage` text of each candidate from step 3 before deciding: that is where a component tells you what it drags in.

The response carries a `source`, and that is the part to read first:

| `source` | What it means |
|---|---|
| `cli` | Your design system stated these itself. They are the authority; nothing else was consulted. |
| `adapter` | Static guidelines your design system ships. Same authority, different transport. |
| `default` | Your design system supplied none, so the small default set applies. Say so in the spec. |

The three are never merged. A design system that states its own guidelines is not also held to ours.

`prose` carries whatever the system says in its own words: principles, do/don't guidance, a rule about which overlay is correct for a destructive action. It is not machine-checkable, and it still outranks anything assumed on the system's behalf. Read it for what binds this feature and turn those into `DS-` requirements, because they are this system's law and nothing else will carry them.

`rules` carries the checkable ones, each with `id`, `requirement`, `verify` and where applicable `standard`. They are already written as testable requirements and do not need re-deriving.

### 6. Write the spec section

Fill in the `## Design System Requirements` section of `FEATURE_SPEC`. The `design` preset appends this section to the spec template, so it is already scaffolded. If the preset is not installed, create the section at the end of the spec instead.

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

Then record the applicable guidelines. Do **not** restate each one in full; cite them by id in a table, since the text lives at its source and duplicating it into every spec creates two sources of truth that will drift:

```markdown
### Guidelines in force

Source: `adapter` (node_modules/@acme/design-system/guidelines.yml).
Cited by id, not restated. Surface kinds: interactive, layout.

| Guideline | Dimension | Requirement |
|---|---|---|
| ACME-TARGET-SIZE | accessibility | Targets at least 48x48px, one spacing step apart |
| ACME-OVERLAY-CHOICE | interaction | Destructive confirmation uses Modal, not Drawer |
| GL-FOCUS-VISIBLE | accessibility | Focus indicator visible at every stop (WCAG 2.4.7) |

Disabled for this project: none.
```

Fill the breakpoint names and token families from step 4, not from memory. A row that says "use the right breakpoints" without naming them has not actually constrained anything.

Then cover each dimension in `REQUIRED_DIMENSIONS` from the gate (states, responsive, accessibility, tokens, interaction). A dimension is covered when a guideline or a `DS-` requirement speaks to it. Only write a feature-specific `DS-` requirement where this feature needs something **beyond** the guidelines; repeating a guideline as a `DS-` entry is noise.

If `GUIDELINES_DISABLED` from the gate is non-empty, list the disabled ids and why. A guideline switched off silently is worse than one never written.

Where the design system's answer is genuinely unclear, use the spec's own idiom rather than guessing:

```
[NEEDS CLARIFICATION: system offers both Drawer and Modal for this flow. Which is correct for a destructive confirmation?]
```

### 7. Add measurable success criteria

Add technology-agnostic entries under `## Success Criteria` for what design compliance means here, for example that the feature introduces no new component outside the design system, or that every interactive element is reachable by keyboard. Keep them measurable; "looks consistent" is not a criterion.

## Completion Report

Report which surfaces were identified, which components and patterns the system surfaced for each, where the guidelines came from, the `DS-` requirements written, and any `[NEEDS CLARIFICATION]` markers left for the user.

## Done When

- [ ] Every user-facing surface was looked up in the decision ledger
- [ ] Every user-facing surface in the spec has been searched against the design system
- [ ] The guidelines in force were resolved and their `source` is stated in the spec
- [ ] The feature's surface kinds were classified and the matching guidelines cited by id
- [ ] Breakpoints and token families are named from what the design system returned, never from memory
- [ ] `## Design System Requirements` is populated with testable `DS-` IDs for what this feature needs *beyond* the guidelines
- [ ] Every required dimension is covered by a guideline or a `DS-` requirement
- [ ] Any disabled guidelines are listed with a reason
- [ ] Genuine ambiguities are marked `[NEEDS CLARIFICATION: ...]` rather than guessed
