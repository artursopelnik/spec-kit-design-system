---
description: "Resolve what the design system offers, walk the Recall -> Reuse -> Compose -> Extend -> Create ladder, write the design requirements into the spec, and gate planning on the outcome"
---

# Design System Check

Establish what the design system offers for this feature, walk every UI surface down the reuse ladder against it, and write the outcome twice: as the contract in `design-system.md`, and as the requirements in the spec. This command runs as a **mandatory `before_plan` hook**: planning must not start while a UI surface is still unaccounted for.

It is the one place the design system is consulted before planning. Searching for a surface, deciding on it and writing the requirement for it happen in one pass, so each surface is looked up once.

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

Parse the JSON for `FEATURE_DIR`, `FEATURE_SPEC`, `DESIGN_DOC`, `CONFIG`, `ADAPTER`, `CAPABILITIES`, `REACHABLE`, `UNREACHABLE_REASON`, `UI_BEARING`, `PRINCIPLES_SOURCE`, `PRINCIPLES_DISABLED`, `HAS_TOKENS` and `REQUIRED_DIMENSIONS`.

`CAPABILITIES` is what the adapter maps **and** the design system was just reached for: the script spends one real call before reporting any of it, so a CLI that is not installed comes back with nothing rather than with a full contract. An empty list therefore means the source of truth is unavailable. One call is proof of reach, not of every mapping — an individual capability can still answer `available: false` with a `reason`, and that is a failure to ask, never the design system saying it has nothing.

**If `UI_BEARING` is `false`**: the spec declares no user-facing surface. Write a one-line `DESIGN_DOC` recording that the gate was evaluated and found not applicable, then report and stop. Do not invent UI work to justify the gate.

**If `REACHABLE` is `false`**: the design system could not be reached. Do **not** silently pass. Report `UNREACHABLE_REASON`, state that the ladder cannot be walked without the source of truth, and stop. A gate that fails open is not a gate. Do not fill the spec with remembered component names either: a wrong inventory is worse than none.

**If `PRINCIPLES_SOURCE` is `unavailable`**: no principles are in force and the fallback is off. Report it and stop; every requirement this command writes cites principles, and citing an empty set produces a spec that looks checked and is not.

Where a capability starts failing in a way that looks like a changed flag rather than an outage, and the adapter maps `describe`, compare `ds.sh query describe --json` against the adapter's invocations and report any that no longer exist. The adapter file is then out of date and a human should update it; nothing rewrites it automatically.

## Outline

### 1. Enumerate the surfaces

From `FEATURE_SPEC`, extract every distinct UI surface the feature requires: a control, a layout region, a flow step, a piece of feedback. Derive the list from the user stories, the requirements and the acceptance scenarios.

Name surfaces by **capability, not by component**: "a control for picking a start and end date", not "a DateRangePicker". Naming a surface after a component you have in mind pre-decides the ladder and defeats the whole exercise.

### 2. Resolve the vocabulary once

Before walking any surface, fetch what every surface will be held to. Once, for the whole feature: the answers are remembered, so asking again later costs nothing, but reading them again into every surface's reasoning does.

**Principles.** First classify what this feature involves, from `interactive`, `layout`, `text`, `media`, `motion`, then:

```
.specify/extensions/design/scripts/bash/ds.sh principles --applies-to interactive,layout --json
```

Classify honestly, and from the components you expect to use as well as from the feature description: a filter that opens a Popover animates, so `motion` applies. Over-claiming buries the spec in principles that do not apply; under-claiming is how a control ships without a focus state.

Read `principles_source` first:

| `principles_source` | What it means |
| --- | --- |
| `cli` | Your design system stated these itself. They are the authority; nothing else was consulted. |
| `docs` | Static principles your design system publishes — an inventory key or a file it ships. Same authority, different transport. |
| `default` | Your design system supplied none, so the small default set applies. Say so in the spec. |
| `unavailable` | Nothing answered and the fallback is switched off. There are no principles in force: stop and report it rather than writing requirements against principles you assumed. |

The sources are never merged. `principles` carries the citable ones, each with `id`, `requirement`, `verify` and an `enforceable` flag: true when it states a MUST or SHOULD and carries a `verify` step. Cite only those as requirements. The ids in `unenforceable` are intent, not requirements; name them in the completion report as a gap in the design system's own principles. `prose` is the system's guidance in its own words: not mechanically checkable, and still binding. Read it for what applies to this feature.

**Tokens and breakpoints.**

```
.specify/extensions/design/scripts/bash/ds.sh query tokens --json
.specify/extensions/design/scripts/bash/ds.sh query breakpoints --json
```

**If `HAS_TOKENS` is false**, skip tokens: the design system has no token layer, so there are no names to look up and none to invent. Breakpoints still apply if mapped; if neither call has them, say so in the spec rather than inventing a set. If `breakpoints` answers with the same payload as `tokens`, the names are still in there, and the adapter can carve the slice out (`result_path`, `result_paths`, `pick`); say so in the completion report.

These are the only names that may appear in the spec, the plan and the code: `color.surface.raised`, `space.3`, `md`. Never a hex value, a pixel width, or a name you have not seen come back from one of these calls.

**Names the feature already asks for.** Where the spec, or the RFC behind it, names tokens (a design brief pasted in often does), check each against the token list. A name that is not in it is a typo or a renamed token: do not substitute the nearest one, mark it `[NEEDS CLARIFICATION]` in the spec.

### 3. Walk the ladder, per surface

Be **strict about what goes in, light on how it is used.** Most surfaces are an existing component used as documented, and proving that takes one search and one look at the component. The full walk, with candidate tables and a gap record, is for the surfaces where something new would enter the codebase, because that is where a wrong answer costs the most and a thorough one pays back.

So every surface starts on the short path and leaves it only when the short path does not hold.

#### The short path: Recall, then Reuse

**Rung 0, Recall.** Before asking the design system anything, ask whether this was already decided:

```
.specify/extensions/design/scripts/bash/ds.sh ledger lookup "<capability phrase>" --current-version "<version>"
```

Get `<version>` from the design system itself where the adapter maps `describe`, otherwise from its package version or `design_system_version` in config. Without it the lookup reports `"staleness_checked": false` and every `stale` flag comes back `null`, meaning unknown, which is not the same as fresh. Do not read an unchecked decision as a verified-current one.

If the first wording misses, try one other before concluding there is nothing. A prior decision is returned with a `match_score` and a `stale` flag. When `ledger.enabled` in `CONFIG` is false the project keeps no ledger: skip this rung and step 5, and say so once in the completion report.

- **Match, not stale** → adopt the prior decision. Record it in `DESIGN_DOC` citing the decision id and the feature it came from, and move to the next surface. This is the point of the ledger: the second feature to need a date range should not re-run the search that the first one already ran.
- **Match, but `stale`** → the design system has changed since that decision was taken. Do **not** adopt it blindly and do not discard it either. Re-walk from Rung 1, then either confirm the prior decision still holds, or record a superseding decision in step 5.
- **Match you believe is wrong** → re-walk the ladder. If you land somewhere else, supersede the old decision explicitly rather than adding a contradicting one. Two active decisions for one capability is exactly the drift this extension exists to prevent.
- **No match** → go to Reuse.

A prior decision is evidence, not an instruction. If adopting it would produce something the spec clearly does not want, say so and re-walk, but say so explicitly, because silently ignoring the ledger puts it back to being decoration.

**Rung 1, Reuse.** Search once, then look at the strongest hit:

```
.specify/extensions/design/scripts/bash/ds.sh query search "<capability phrase>"
.specify/extensions/design/scripts/bash/ds.sh query component "<Name>"
```

If its props, variants and states cover the surface, **the surface is resolved as Reuse and the walk ends.** Record it in the short form in step 4 and move on. No candidate table is needed to justify using the component the design system offers for exactly this.

If the first search misses, search once more with different wording before leaving the short path: design systems name things in ways you will not guess on the first try, and a second wording is far cheaper than a composition nobody needed.

Covering the surface includes looking the way the spec asks. Where the spec requires a particular appearance (a dark variant, a specific token), say which variant, prop or theme setting of the component delivers it. If none does, the component does not cover the surface as specified, and the walk continues.

#### The full walk: Compose, Extend, Create

Reached only when Reuse does not hold. From here on the reasoning is the artifact, because it is what a reviewer, and the design system's owners, will read.

**Rung 2, Compose from a pattern.** Query for an existing composed pattern (`ds.sh query pattern "<phrase>"`, and search again with pattern-shaped wording). Design systems often ship the exact arrangement you are about to rebuild.

**Rung 3, Compose from components.** Can two or more existing components be combined to cover the surface? State the composition explicitly (which components, how arranged). Prefer an ugly composition of owned parts over a pretty new abstraction.

**Rung 4, Extend.** Can an existing component be extended through the system's sanctioned mechanism (`ds.sh query extend "<Name>"`)? Extending via a supported escape hatch (a documented prop, a className override, a swizzle) is still reuse. Forking the source and editing it is not; that is Rung 5 wearing a disguise.

**Rung 5, Create.** Only reachable when rungs 1 through 4 are documented as insufficient, and it always requires a gap record. Before writing one, search **once more** with wording you have not tried yet: a synonym, the user-facing term, the term a designer would use, the term the system's own docs use for a neighbouring concept. Gaps found on the fifth search are common; gaps that survive a deliberate final attempt are real. If this surfaces a viable candidate, drop back to the lower rung and say so — that is a good outcome, not a wasted step.

What gets built is a **lab component**: it lives in the project, not in the design system, it is built only from the system's tokens and primitives, and it covers what this feature needs and nothing more. Mark it as such where it is defined, with one comment naming its gap record, so the next reader can tell it apart from the system's own components. Whether it ever becomes part of the design system is for the system's owners to decide, in their own process; the gap record is the case you hand them, not a promise this feature makes.

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
<the lab component: its scope, and where its source will live>

## What the design system could do
<the change that would make this unnecessary next time>
```

Where the adapter maps `report_gap`, route it into the system's own intake so it lands with the people who can close it:

```
.specify/extensions/design/scripts/bash/ds.sh query report_gap "<title>" "<body>" --json
```

The gate does not pass until the record exists.

### 4. Record the walk

Write `DESIGN_DOC` (`design-system.md` in the feature directory) with one section per surface. A surface resolved on the short path gets the short form:

```markdown
## Surface: <capability phrase>

**Resolution**: Reuse
**Decision**: Button, `variant="primary"`
**Source**: recalled `dd-004` | searched "submit action"
**Principles that apply**: PRIN-FOCUS-VISIBLE, ACME-TARGET-SIZE
```

A surface that took the full walk gets the full form, because its reasoning is the part someone will want to check:

```markdown
## Surface: <capability phrase>

**Resolution**: Compose (pattern) | Compose (components) | Extend | Create
**Decision**: <pattern or composition chosen, or the lab component and its gap record>

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

Honour `gate.min_candidates_considered` from `CONFIG` for **Extend and Create**: a surface may not land on either with fewer candidates rejected than that, because that is where new code enters the project on the strength of the search. If the design system genuinely offers fewer, say so explicitly rather than padding the table. Reuse and Compose use what exists, and need no quota.

### 5. Commit the decision to memory

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

### 6. Carry the constraints forward

For each resolved surface, record the constraints the plan must respect, pulled from the component detail rather than invented:

- **States** every component instance must handle (default, hover, focus, active, disabled, loading, error, empty)
- **Responsive** behaviour across the project's breakpoints
- **Accessibility** obligations the component documents (roles, labels, keyboard model, focus order)
- **Tokens** to be used, never raw hex, px or font stacks where a token exists
- **Interaction** requirements (what feedback, on what latency, with what affordance)

Omit a dimension only when the component's own documentation makes it inapplicable, and say which.

For a **Reuse** surface the component's documentation already answers most of this, so refer to it rather than copying it out: `States, accessibility: as documented for Button`. Spell out only what this feature adds on top: a state the component leaves to its caller, a breakpoint behaviour the spec asks for, the tokens the spec names. Copying a component's documentation into every feature produces a second source that drifts from the first.

### 7. Write the spec section

`design-system.md` is the contract; the spec states the requirements that come out of it, so the plan and the validation read one set of names. Fill in the `## Design System Requirements` section of `FEATURE_SPEC`. The `design` preset appends it to the spec template; if the preset is not installed, create it at the end of the spec.

Write `DS-` prefixed, testable requirements in the same MUST/SHOULD style as the functional requirements, and only for what this feature needs **beyond** the principles in force:

```markdown
### Requirements

- **DS-001**: The date range control MUST be the composition recorded in
  design-system.md (Calendar in Popover), not bespoke markup.
- **DS-002**: The filter panel MUST use `color.surface.inverse` and `space.6`,
  as the brief asks.
- **DS-003**: The filter row MUST collapse to a stacked form below `md`.
```

Then cite the principles in force by id rather than restating them. Only `enforceable` ones belong here; a row nothing can check reads as a requirement and is not one:

```markdown
### Principles in force

Source: `docs` (node_modules/@acme/design-system/principles.yml), version 2025.4.
Surface kinds: interactive, layout.

| Principle | Dimension | Requirement |
| --- | --- | --- |
| ACME-TARGET-SIZE | accessibility | Targets at least 48x48px, one spacing step apart |
| PRIN-FOCUS-VISIBLE | accessibility | Focus indicator visible at every stop (WCAG 2.4.7) |

Disabled for this project: none.
Stated but not enforceable (no verify step): ACME-DENSITY.
```

Every dimension in `REQUIRED_DIMENSIONS` must be covered by a principle or a `DS-` requirement. If `PRINCIPLES_DISABLED` is non-empty, list the ids and why: a principle switched off silently is worse than one never written. Add measurable entries under `## Success Criteria` for what design compliance means here, for example that the feature introduces no component outside the design system except the lab components its gap records name.

Where a design question is genuinely open and only a person can answer it, use the spec's own idiom rather than guessing, and let the gate fail on it:

```
[NEEDS CLARIFICATION: system offers both Drawer and Modal for this flow. Which is correct for a destructive confirmation?]
```

### 8. Gate

The gate **fails** when any of these hold:

- a surface has no recorded resolution
- a Create resolution has no gap record
- an Extend or Create resolution rests on fewer rejected candidates than `gate.min_candidates_considered`
- a dimension in `REQUIRED_DIMENSIONS` from the gate is unanswered for a resolved surface
- the spec carries a `[NEEDS CLARIFICATION]` marker this command wrote, or a token name the design system does not have

On failure with `gate.enforce: true`: **ERROR and stop.** Name every unmet condition and what would satisfy it. Do not proceed to planning, and do not soften a Create decision into a Reuse one to get past the gate. An honest Create with a gap report is a pass, a dishonest Reuse is a defect you will pay for in review.

On failure with `gate.enforce: false`: record the same findings in `DESIGN_DOC`, report them prominently as warnings, and allow planning to continue.

## Completion Report

Report a compact table: surface, resolution, decision. Then state the gate outcome, where the principles came from, the `DS-` requirements written, any `[NEEDS CLARIFICATION]` left for the user, and any design system impact that now needs an owner.

## Done When

- [ ] The principles in force, the tokens and the breakpoints were resolved once, and every token the spec names exists
- [ ] Every UI surface was looked up in the ledger before the design system was queried
- [ ] Every UI surface in the spec appears in `DESIGN_DOC` with a resolution
- [ ] Surfaces that resolved on the short path (Recall, Reuse) stopped there, in the short form
- [ ] Surfaces that took the full walk record the candidates searched and why the chosen rung is the lowest that holds
- [ ] Constraints (states, responsive, accessibility, tokens, interaction) are carried forward from real component documentation
- [ ] Every Create resolution has a gap record, and what it builds is marked as a lab component
- [ ] Newly-walked surfaces are recorded in the ledger with aliases and a design system version
- [ ] Contradicting decisions supersede the old one rather than sitting alongside it
- [ ] `## Design System Requirements` in the spec states the `DS-` requirements and the principles in force, citing only enforceable ids
- [ ] Every required dimension is covered by a principle or a `DS-` requirement
- [ ] The gate outcome is stated explicitly as pass or fail
