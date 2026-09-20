---
description: "Walk the Reuse -> Compose -> Extend -> Create ladder against the design system and gate planning on the outcome"
---

# Design System Check

Walk every UI surface this feature needs down the reuse ladder, using the design system CLI as the source of truth, and record the result as a reviewable artifact. This command runs as a **mandatory `before_plan` hook**: planning must not start while a UI surface is still unaccounted for.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Arguments may name a specific surface to re-check, or pass `--refresh` to re-derive the CLI mapping from the design system's own self-description.

## Prerequisites

Run:

```
.specify/extensions/designsys/scripts/bash/check-design-gate.sh --json
```

Where bash is unavailable, call the module directly — it behaves identically:
`python3 .specify/extensions/designsys/scripts/python/designsys.py gate --json`

Parse the JSON for `FEATURE_DIR`, `FEATURE_SPEC`, `DESIGN_DOC`, `CONFIG`, `ADAPTER`, `CAPABILITIES`, `REACHABLE`, `UNREACHABLE_REASON` and `UI_BEARING`.

`CAPABILITIES` reflects what the design system could actually answer just now, not what the adapter file claims — the script probes it. An empty list therefore means the source of truth is unavailable.

**If `UI_BEARING` is `false`**: the spec declares no user-facing surface. Write a one-line `DESIGN_DOC` recording that the gate was evaluated and found not applicable, then report and stop. Do not invent UI work to justify the gate.

**If `REACHABLE` is `false`**: the design system could not be reached. Do **not** silently pass. Report `UNREACHABLE_REASON`, state that the ladder cannot be walked without the source of truth, and stop. A gate that fails open is not a gate.

## Outline

### 1. Enumerate the surfaces

From `FEATURE_SPEC`, extract every distinct UI surface the feature requires — a control, a layout region, a flow step, a piece of feedback. Read the `## Design System Requirements` section if `/speckit.designsys.sync` already populated it; otherwise derive the list from the user stories and acceptance scenarios.

Name surfaces by **capability, not by component**: "a control for picking a start and end date", not "a DateRangePicker". Naming a surface after a component you have in mind pre-decides the ladder and defeats the whole exercise.

### 2. Walk the ladder, per surface

For each surface, in order. Stop at the first rung that holds.

**Rung 0 — Recall.** Before asking the design system anything, ask whether this was already decided:

```
.specify/extensions/designsys/scripts/bash/ds-ledger.sh --json lookup "<capability phrase>" --current-version "<version>"
```

Get `<version>` from the design system itself where the adapter maps `describe`, otherwise from its package version or `design_system_version` in config. Without it the lookup reports `"staleness_checked": false` and every `stale` flag comes back `null` — unknown, which is not the same as fresh. Do not read an unchecked decision as a verified-current one.

Look up each surface with **more than one wording** — the same discipline as searching the design system. A prior decision is returned with a `match_score` and a `stale` flag.

- **Match, not stale** → adopt the prior decision. Record it in `DESIGN_DOC` citing the decision id and the feature it came from, and move to the next surface. This is the point of the ledger: the second feature to need a date range should not re-run the search that the first one already ran.
- **Match, but `stale`** → the design system has changed since that decision was taken. Do **not** adopt it blindly and do not discard it either. Re-walk from Rung 1, then either confirm the prior decision still holds, or record a superseding decision in step 5.
- **Match you believe is wrong** → re-walk the ladder. If you land somewhere else, supersede the old decision explicitly rather than adding a contradicting one. Two active decisions for one capability is exactly the drift this extension exists to prevent.
- **No match** → walk the ladder normally.

A prior decision is evidence, not an instruction. If adopting it would produce something the spec clearly does not want, say so and re-walk — but say so explicitly, because silently ignoring the ledger puts it back to being decoration.

**Rung 1 — Reuse.** Query the design system for existing components:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json search "<capability phrase>"
```

Run at least two differently-worded queries per surface — design systems name things in ways you will not guess on the first try. Then pull detail on the promising hits with `ds-query.sh --json component "<Name>"`. A component whose props, variants and states already cover the surface ends the walk.

**Rung 2 — Compose from a pattern.** Query for an existing composed pattern (`ds-query.sh --json pattern "<phrase>"`, and search again with pattern-shaped wording). Design systems often ship the exact arrangement you are about to rebuild.

**Rung 3 — Compose from components.** Can two or more existing components be combined to cover the surface? State the composition explicitly (which components, how arranged). Prefer an ugly composition of owned parts over a pretty new abstraction.

**Rung 4 — Extend.** Can an existing component be extended through the system's sanctioned mechanism (`ds-query.sh --json extend "<Name>"`)? Extending via a supported escape hatch — a documented prop, a className override, a swizzle — is still reuse. Forking the source and editing it is not; that is Rung 5 wearing a disguise.

**Rung 5 — Create.** Only reachable when rungs 1–4 are documented as insufficient. Invoke `/speckit.designsys.gap` for this surface. If `gate.require_gap_report` is true, the gate does not pass until that record exists.

### 3. Record the walk

Write `DESIGN_DOC` (`design-system.md` in the feature directory) with one section per surface:

```markdown
## Surface: <capability phrase>

**Resolution**: Reuse | Compose (pattern) | Compose (components) | Extend | Create
**Decision**: <component / pattern / composition chosen>

**Searched**:
| Candidate | Source | Verdict |
|---|---|---|
| DatePicker | component | Single date only; no range semantics |
| Calendar | component | Display-only, no input affordance |
| Select | component | Wrong interaction model for dates |
| Popover | component | Container only; solves placement, not the control |

**Why the chosen rung**: <one or two sentences>
**Design system impact**: none | extension proposal | new component proposal
```

Honour `gate.min_candidates_considered` from `CONFIG`: a rung may not be rejected on fewer candidates than that. If the design system genuinely offers fewer, say so explicitly rather than padding the table.

### 4. Commit the decision to memory

When `ledger.enabled` is true, record each newly-walked surface so the next feature starts from it instead of from nothing:

```
.specify/extensions/designsys/scripts/bash/ds-ledger.sh --json record - <<'JSON'
{
  "capability": "selection of a date range",
  "aliases": ["date range picker", "from-to date selection", "period filter"],
  "resolution": "compose-components",
  "decision": "Calendar inside Popover, range state lifted to the form",
  "components": ["Calendar", "Popover"],
  "rejected": [{"candidate": "DatePicker", "reason": "single date only; no range semantics"}],
  "constraints": {"tokens": ["space.*", "color.surface.*"], "states": ["default", "focus", "disabled", "error"]},
  "design_system": "astryx",
  "design_system_version": "1.4.2",
  "decided_in": "003-booking-filters"
}
JSON
```

Two fields decide whether this ledger is worth having:

- **`aliases`** — record every wording you actually searched with, including the ones that missed. These are what make a future lookup hit when the next author phrases the same need differently. A decision with no aliases is a decision that will be re-derived.
- **`design_system_version`** — so a later lookup can tell that the system has moved on. Get it from the CLI (`ds-query.sh --json describe`) where available; otherwise from the design system package's version.

Do not record a surface that was adopted unchanged from a prior decision — it is already there. When re-walking produced a *different* answer, add `"supersedes": "<id>"` so the old decision is retired rather than left to contradict the new one.

Skip this step entirely when the gate fails. A decision that was never allowed to pass should not become the precedent the next feature inherits.

### 5. Carry the constraints forward

For each resolved surface, record the constraints the plan must respect, pulled from the component detail rather than invented:

- **States** every component instance must handle (default, hover, focus, active, disabled, loading, error, empty)
- **Responsive** behaviour across the project's breakpoints
- **Accessibility** obligations the component documents (roles, labels, keyboard model, focus order)
- **Tokens** to be used — never raw hex, px or font stacks where a token exists
- **Interaction** requirements (what feedback, on what latency, with what affordance)

Omit a dimension only when the component's own documentation makes it inapplicable, and say which.

### 6. Gate

The gate **fails** when any of these hold:

- a surface has no recorded resolution
- a Create resolution has no gap record while `gate.require_gap_report` is true
- a rung was rejected on fewer candidates than `gate.min_candidates_considered`
- a required dimension from `audit.required_dimensions` is unanswered for a resolved surface

On failure with `gate.enforce: true`: **ERROR and stop.** Name every unmet condition and what would satisfy it. Do not proceed to planning, and do not soften a Create decision into a Reuse one to get past the gate — an honest Create with a gap report is a pass, a dishonest Reuse is a defect you will pay for in review.

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
