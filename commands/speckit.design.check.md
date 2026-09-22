---
description: "Walk the Recall -> Reuse -> Compose -> Extend -> Create ladder against the design system and gate planning on the outcome"
---

# Design System Check

Walk every UI surface this feature needs down the reuse ladder, using the design system CLI as the source of truth, and record the result as a reviewable artifact. This command runs as a **mandatory `before_plan` hook**: planning must not start while a UI surface is still unaccounted for.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Arguments may name a specific surface to re-check.

## Prerequisites

Run:

```
.specify/extensions/design/scripts/bash/ds.sh gate --json
```

Where bash is unavailable, call the module directly. It behaves identically:
`python3 .specify/extensions/design/scripts/python/design.py gate --json`

Parse the JSON for `FEATURE_DIR`, `FEATURE_SPEC`, `DESIGN_DOC`, `CONFIG`, `ADAPTER`, `CAPABILITIES`, `REACHABLE`, `UNREACHABLE_REASON`, `UI_BEARING` and `REQUIRED_DIMENSIONS`.

`CAPABILITIES` is what the adapter maps **and** the design system was just reached for: the script spends one real call before reporting any of it, so a CLI that is not installed comes back with nothing rather than with a full contract. An empty list therefore means the source of truth is unavailable. One call is proof of reach, not of every mapping — an individual capability can still answer `available: false` with a `reason`, and that is a failure to ask, never the design system saying it has nothing.

**If `UI_BEARING` is `false`**: the spec declares no user-facing surface. Write a one-line `DESIGN_DOC` recording that the gate was evaluated and found not applicable, then report and stop. Do not invent UI work to justify the gate.

**If `REACHABLE` is `false`**: the design system could not be reached. Do **not** silently pass. Report `UNREACHABLE_REASON`, state that the ladder cannot be walked without the source of truth, and stop. A gate that fails open is not a gate.

## Outline

### 1. Enumerate the surfaces

From `FEATURE_SPEC`, extract every distinct UI surface the feature requires: a control, a layout region, a flow step, a piece of feedback. Read the `## Design System Requirements` section if `/speckit.design.context` already populated it; otherwise derive the list from the user stories and acceptance scenarios.

Name surfaces by **capability, not by component**: "a control for picking a start and end date", not "a DateRangePicker". Naming a surface after a component you have in mind pre-decides the ladder and defeats the whole exercise.

### 2. Walk the ladder, per surface

For each surface, in order. Stop at the first rung that holds.

**Rung 0, Recall.** Before asking the design system anything, ask whether this was already decided:

```
.specify/extensions/design/scripts/bash/ds.sh ledger lookup "<capability phrase>" --current-version "<version>"
```

Get `<version>` from the design system itself where the adapter maps `describe`, otherwise from its package version or `design_system_version` in config. Without it the lookup reports `"staleness_checked": false` and every `stale` flag comes back `null`, meaning unknown, which is not the same as fresh. Do not read an unchecked decision as a verified-current one.

Look up each surface with **more than one wording**, the same discipline as searching the design system. A prior decision is returned with a `match_score` and a `stale` flag. When `ledger.enabled` in `CONFIG` is false the project keeps no ledger: skip this rung and step 4, and say so once in the completion report.

- **Match, not stale** → adopt the prior decision. Record it in `DESIGN_DOC` citing the decision id and the feature it came from, and move to the next surface. This is the point of the ledger: the second feature to need a date range should not re-run the search that the first one already ran.
- **Match, but `stale`** → the design system has changed since that decision was taken. Do **not** adopt it blindly and do not discard it either. Re-walk from Rung 1, then either confirm the prior decision still holds, or record a superseding decision in step 4.
- **Match you believe is wrong** → re-walk the ladder. If you land somewhere else, supersede the old decision explicitly rather than adding a contradicting one. Two active decisions for one capability is exactly the drift this extension exists to prevent.
- **No match** → walk the ladder normally.

A prior decision is evidence, not an instruction. If adopting it would produce something the spec clearly does not want, say so and re-walk, but say so explicitly, because silently ignoring the ledger puts it back to being decoration.

**Rung 1, Reuse.** Query the design system for existing components:

```
.specify/extensions/design/scripts/bash/ds.sh query search "<capability phrase>"
```

Run at least two differently-worded queries per surface, because design systems name things in ways you will not guess on the first try. Then pull detail on the promising hits with `ds.sh query component "<Name>"`. A component whose props, variants and states already cover the surface ends the walk.

**Rung 2, Compose from a pattern.** Query for an existing composed pattern (`ds.sh query pattern "<phrase>"`, and search again with pattern-shaped wording). Design systems often ship the exact arrangement you are about to rebuild.

**Rung 3, Compose from components.** Can two or more existing components be combined to cover the surface? State the composition explicitly (which components, how arranged). Prefer an ugly composition of owned parts over a pretty new abstraction.

**Rung 4, Extend.** Can an existing component be extended through the system's sanctioned mechanism (`ds.sh query extend "<Name>"`)? Extending via a supported escape hatch (a documented prop, a className override, a swizzle) is still reuse. Forking the source and editing it is not; that is Rung 5 wearing a disguise.

**Rung 5, Create.** Only reachable when rungs 1 through 4 are documented as insufficient, and it always requires a gap record. Before writing one, search **once more** with wording you have not tried yet: a synonym, the user-facing term, the term a designer would use, the term the system's own docs use for a neighbouring concept. Gaps found on the fifth search are common; gaps that survive a deliberate final attempt are real. If this surfaces a viable candidate, drop back to the lower rung and say so — that is a good outcome, not a wasted step.

Write the record to its own file, `design-system-gap-<slug>.md` in the feature directory, and link it from the surface's section in `DESIGN_DOC`. A standalone file matters because a gap record is the argued case for a new component, and it has to travel: to the design system's repo, to an issue tracker, to a review.

```markdown
# Gap: <capability phrase>

**Feature**: <feature id> · **Design system**: <name> · **Version**: <version>

## What is needed
<the capability, described without naming the component you have in mind>

## What was searched
| Candidate | Rung | Why it is insufficient |
|---|---|---|
| DatePicker | reuse | Single date only; no range semantics |
| Calendar + Popover | compose | Covers display and placement, not cross-field validation |

## What we are building instead
<scope, and where the source will live>

## What the design system could do
<the change that would make this unnecessary next time>
```

Where the adapter maps `report_gap`, route it into the system's own intake so it lands with the people who can close it:

```
.specify/extensions/design/scripts/bash/ds.sh query report_gap "<title>" "<body>" --json
```

The gate does not pass until the record exists.

### 3. Record the walk

Write `DESIGN_DOC` (`design-system.md` in the feature directory) with one section per surface:

```markdown
## Surface: <capability phrase>

**Resolution**: Reuse | Compose (pattern) | Compose (components) | Extend | Create
**Decision**: <component / pattern / composition chosen>

**Searched**:
| Candidate | Source | Verdict |
| --- | --- | --- |
| DatePicker | component | Single date only; no range semantics |
| Calendar | component | Display-only, no input affordance |
| Select | component | Wrong interaction model for dates |
| Popover | component | Container only; solves placement, not the control |

**Principles that apply**: ACME-TARGET-SIZE, ACME-OVERLAY-CHOICE, PRIN-FOCUS-VISIBLE

**Why the chosen rung**: <one or two sentences>
**Design system impact**: none | extension proposal | new component proposal
```

**Principles that apply** is the line validation reads back. Take the ids from
`ds.sh principles --applies-to <kinds> --json`, listing the ones that bear on
**this** surface rather than the whole set — a surface that lists everything has
classified nothing. Cite only `enforceable` ids: an id with no `verify` step
gives validation nothing to check, and listing it here would look like coverage.
A surface with no applicable principle says `none` and why, which is a claim
somebody can disagree with; a blank line is not.

Honour `gate.min_candidates_considered` from `CONFIG`: a rung may not be rejected on fewer candidates than that. If the design system genuinely offers fewer, say so explicitly rather than padding the table.

### 4. Commit the decision to memory

When `ledger.enabled` is true, record each newly-walked surface so the next feature starts from it instead of from nothing:

```
.specify/extensions/design/scripts/bash/ds.sh ledger record - --json <<'JSON'
{
  "capability": "selection of a date range",
  "aliases": ["date range picker", "from-to date selection", "period filter"],
  "resolution": "compose-components",
  "decision": "Calendar inside Popover, range state lifted to the form",
  "components": ["Calendar", "Popover"],
  "rejected": [{"candidate": "DatePicker", "reason": "single date only; no range semantics"}],
  "constraints": {"tokens": ["space.*", "color.surface.*"], "states": ["default", "focus", "disabled", "error"]},
  "design_system": "acme-ds",
  "design_system_version": "1.4.2",
  "decided_in": "003-booking-filters"
}
JSON
```

`resolution` is one of `reuse`, `compose-pattern`, `compose-components`, `extend`,
`create` — the rung, in the ledger's own spelling. Anything else is refused rather
than stored, because a ledger is read back by string match long after the reasoning
is gone, and two spellings of one rung are two answers to one question.

Three fields decide whether this ledger is worth having:

- **`aliases`**: record every wording you actually searched with, including the ones that missed. These are what make a future lookup hit when the next author phrases the same need differently. A decision with no aliases is a decision that will be re-derived.
- **`design_system_version`**: so a later lookup can tell that the system has moved on. Get it from the CLI (`ds.sh query describe`) where available; otherwise from the design system package's version.
- **`decided_in`**: the feature that took the decision, so a later reader can go and see the argument rather than just the verdict. This is the only name for it; `feature` is folded into it.

Do not record a surface that was adopted unchanged from a prior decision, because it is already there. When re-walking produced a *different* answer, add `"supersedes": "<id>"` so the old decision is retired rather than left to contradict the new one.

This is the **only** place a decision is written. A second active decision for the same capability is refused, and the refusal names the id to supersede. If you meant to replace the earlier answer, say so with `supersedes`; if you did not, the earlier answer already stands and there is nothing to write.

Skip this step entirely when the gate fails. A decision that was never allowed to pass should not become the precedent the next feature inherits.

### 5. Carry the constraints forward

For each resolved surface, record the constraints the plan must respect, pulled from the component detail rather than invented:

- **States** every component instance must handle (default, hover, focus, active, disabled, loading, error, empty)
- **Responsive** behaviour across the project's breakpoints
- **Accessibility** obligations the component documents (roles, labels, keyboard model, focus order)
- **Tokens** to be used, never raw hex, px or font stacks where a token exists
- **Interaction** requirements (what feedback, on what latency, with what affordance)

Omit a dimension only when the component's own documentation makes it inapplicable, and say which.

### 6. Gate

The gate **fails** when any of these hold:

- a surface has no recorded resolution
- a Create resolution has no gap record
- a rung was rejected on fewer candidates than `gate.min_candidates_considered`
- a dimension in `REQUIRED_DIMENSIONS` from the gate is unanswered for a resolved surface

On failure with `gate.enforce: true`: **ERROR and stop.** Name every unmet condition and what would satisfy it. Do not proceed to planning, and do not soften a Create decision into a Reuse one to get past the gate. An honest Create with a gap report is a pass, a dishonest Reuse is a defect you will pay for in review.

On failure with `gate.enforce: false`: record the same findings in `DESIGN_DOC`, report them prominently as warnings, and allow planning to continue.

## Completion Report

Report a compact table: surface, resolution, decision. Then state the gate outcome, and list any design system impact that now needs an owner.

## Done When

- [ ] Every UI surface was looked up in the ledger before the design system was queried
- [ ] Every UI surface in the spec appears in `DESIGN_DOC` with a resolution
- [ ] Each resolution records the candidates searched and why the chosen rung is the lowest that holds
- [ ] Constraints (states, responsive, accessibility, tokens, interaction) are carried forward from real component documentation
- [ ] Every Create resolution has a gap record
- [ ] Newly-walked surfaces are recorded in the ledger with aliases and a design system version
- [ ] Contradicting decisions supersede the old one rather than sitting alongside it
- [ ] The gate outcome is stated explicitly as pass or fail
