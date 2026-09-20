---
description: "Validate the implementation against the design system contract and report violations"
---

# Design System Audit

Check what was actually built against what the spec and the ladder committed to. This runs as an **`after_implement` hook** and closes the loop: the decisions recorded in `design-system.md` become assertions about the code.

This is the only part of the extension that looks backwards, and it is deliberately the last one. By the time it runs, most design failures should already have been prevented rather than detected.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Arguments may scope the audit to specific paths or surfaces.

## Prerequisites

Run `.specify/extensions/designsys/scripts/bash/check-design-gate.sh --json` and parse for `FEATURE_DIR`, `DESIGN_DOC`, `IMPL_PLAN`, `CONFIG`, `CAPABILITIES`.

**If `DESIGN_DOC` does not exist**: the gate never ran for this feature. Report that the audit has no contract to check against and recommend `/speckit.designsys.check`. Do not improvise a contract now. An audit against a contract invented after the fact tells you nothing.

## Outline

### 1. Determine what to read

Use `audit.source_globs` from `CONFIG` if set. Otherwise infer the implementation paths from the plan's `## Project Structure` section, narrowed to files the feature actually touched.

### 2. Check each committed decision

For every surface in `DESIGN_DOC`, verify the code did what was decided:

- **Reuse** → the named component is imported from the design system and actually used for that surface. A component imported and then wrapped in enough overrides to change its behaviour is not reuse; flag it.
- **Compose** → the named components appear, arranged as described. A composition that quietly grew a bespoke replacement for one of its parts has drifted.
- **Extend** → extension went through the sanctioned mechanism recorded in the ladder, not a copied-and-edited fork.
- **Create** → the new component exists where the gap record said it would, is built from the system's tokens and primitives, and did not grow past the scope the record set.

Flag anything built bespoke that never appeared in `DESIGN_DOC` at all. This is the highest-value finding the audit produces: it is the exact failure this extension exists to catch, and it will usually look locally reasonable.

### 3. Check the dimensions

For each dimension in `audit.required_dimensions`, check the corresponding `DS-` requirements from the spec:

- **States**: are default, hover, focus, active, disabled, loading, error and empty handled where applicable? Missing loading and error states are the most common real defect here.
- **Responsive**: does the layout behave at every project breakpoint, per the spec's stated behaviour?
- **Accessibility**: accessible names present, keyboard operability, focus order following visual order, roles correct, focus visible. Check against the obligations the component's own documentation states, retrieved via `ds-query.sh --json component "<Name>"`.
- **Tokens**: when `audit.forbid_raw_values` is true, flag raw hex colors, raw px spacing and hardcoded font stacks wherever the system provides a token. Report the token that should have been used, not just the violation.
- **Interaction**: is the feedback the spec required actually implemented?

### 4. Report

Write findings into `DESIGN_DOC` under `## Audit`, most severe first:

```markdown
## Audit: <date>

| Severity | Surface | Finding | Fix |
|---|---|---|---|
| violation | Date range | Bespoke `<input type="date">` pair; DESIGN_DOC committed to Rung 3 composition | Use Calendar in Popover as recorded |
| violation | Filter row | `padding: 12px` hardcoded | Use `space.3` |
| warning | Result table | No empty state | Add per DS-006 |
```

Classify honestly:

- **violation**: contradicts a `DS-` requirement or a recorded ladder decision
- **warning**: a required dimension is unanswered, but nothing was contradicted
- **note**: a defensible deviation, recorded so the next reader knows it was deliberate

Do not pad the report. An audit that always finds something teaches people to ignore it; the cleanest useful outcome is "no violations" and it should be reachable.

### 5. On violations

Report them and state clearly that the feature does not yet satisfy its design requirements. Where a fix is small, local and unambiguous (a raw value that has an obvious token, a missing `aria-label`), apply it and say so. Where a fix means reversing an implementation decision, report it with the recommended change and let the user decide; silently rewriting a built feature during an audit hook is not your call.

## Completion Report

State the number of violations, warnings and notes; list the violations; state whether the feature meets its design requirements; and name anything fixed in place.

## Done When

- [ ] Every surface in `DESIGN_DOC` was checked against what the code actually does
- [ ] Bespoke UI absent from `DESIGN_DOC` is flagged
- [ ] Every required dimension was checked against the spec's `DS-` requirements
- [ ] Findings are recorded in `DESIGN_DOC` under `## Audit` with severities
- [ ] The compliance verdict is stated explicitly
