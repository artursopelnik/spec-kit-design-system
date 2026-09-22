---
description: "Check the implementation independently against the spec, the principles and the design system, and raise findings that feed back into fixing"
---

# Design System Validate

Check what was actually built against what the spec, the principles and the ladder committed to. This runs as an **`after_implement` hook** and is the checker half of the workflow: the agent that wrote the code does not also get to decide it is correct.

Read this as a review of someone else's work, because for this pass it is. Your job is to find what is wrong, not to confirm what you hoped was right. Anything you find becomes a numbered finding that the run must fix and re-validate.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Arguments may scope validation to specific paths or surfaces.

## Prerequisites

```
.specify/extensions/design/scripts/bash/ds.sh gate --json
.specify/extensions/design/scripts/bash/ds.sh workflow status --json
```

Parse the gate for `FEATURE_DIR`, `DESIGN_DOC`, `IMPL_PLAN`, `CONFIG`, `CAPABILITIES`, `PRINCIPLES_SOURCE`, `PRINCIPLES_DISABLED`, `PRINCIPLES_UNENFORCEABLE`, `DOD_ITEMS`, `DOD_ERROR`; the status for `validation_rounds_used`, `max_validation_rounds` and `may_validate_again`.

**If `DESIGN_DOC` does not exist**: the gate never ran for this feature. Report that validation has no contract to check against and recommend `/speckit.design.check`. Do not improvise a contract now. A check against a contract invented after the fact tells you nothing.

**If `may_validate_again` is `false`**: the loop has used its rounds. Do not start another. Report the findings still open and stop; this needs a human.

## Outline

### 1. Determine what to read

Use `validation.source_globs` from `CONFIG` if set. Otherwise infer the implementation paths from the plan's `## Project Structure` section, narrowed to files the feature actually touched.

Ask the design system for what you need as you go:

```
.specify/extensions/design/scripts/bash/ds.sh context validate --applies-to <kinds> \
  --component <Name> --json
```

`available_on_demand` in that response lists everything else you can still ask. A finding you cannot substantiate because you did not look something up is not a finding; look it up.

### 2. Check each committed decision

For every surface in `DESIGN_DOC`, verify the code did what was decided:

- **Reuse** → the named component is imported from the design system and actually used for that surface. A component imported and then wrapped in enough overrides to change its behaviour is not reuse; flag it.
- **Compose** → the named components appear, arranged as described. A composition that quietly grew a bespoke replacement for one of its parts has drifted.
- **Extend** → extension went through the sanctioned mechanism recorded in the ladder, not a copied-and-edited fork.
- **Create** → the new component exists where the gap record said it would, is built from the system's tokens and primitives, and did not grow past the scope the record set.

Flag anything built bespoke that never appeared in `DESIGN_DOC` at all. This is the highest-value finding here: it is the exact failure this extension exists to catch, and it will usually look locally reasonable.

### 3. Check the principles in force

```
.specify/extensions/design/scripts/bash/ds.sh principles --applies-to <kinds from the spec> --json
```

Each entry carries a `verify` field saying how to check it. Work through them. These are the requirements nobody writes down, so they are also the ones nobody checks: a control with no focus style, a layout that breaks at 320px, an action reachable only on hover, a raw hex where a token exists.

Check the ids `DESIGN_DOC` listed under **Principles that apply** for each surface, and check the rest of the applicable set against that surface too. A principle the check phase did not list is not thereby satisfied — if it applies and nothing covers it, that is a finding, and the missing line in `DESIGN_DOC` is part of it.

Ids in `unenforceable` have no `verify` step, so there is nothing to check them against. Do not invent one: report them as a gap in the principles themselves, not as a finding against this feature.

`prose` is not mechanically checkable and still binds. Read it and check the implementation against what the design system actually says about this kind of surface.

Check against the code, not against the spec's claims. The spec saying `PRIN-FOCUS-VISIBLE` applies is not evidence that focus is visible.

Report a principle finding under its id, and give every finding a concrete fix — the change that would clear it, not a restatement of the problem. A finding without a fix is an opinion with a checkbox. Reporting under the id keeps it traceable to the principle rather than to your phrasing of it. An id listed in `PRINCIPLES_DISABLED` is not checked; note that it was skipped, rather than passing over it silently.

### 4. Check the dimensions

For each dimension in `REQUIRED_DIMENSIONS` from the gate, check the corresponding `DS-` requirements from the spec:

- **States**: are default, hover, focus, active, disabled, loading, error and empty handled where applicable? Missing loading and error states are the most common real defect here.
- **Responsive**: does the layout behave at every project breakpoint, per the spec's stated behaviour?
- **Accessibility**: accessible names present, keyboard operability, focus order following visual order, roles correct, focus visible. Check against the obligations the component's own documentation states, retrieved via `ds.sh query component "<Name>"`.
- **Tokens**: when `validation.forbid_raw_values` is true and `HAS_TOKENS` is true, flag raw hex colors, raw px spacing and hardcoded font stacks wherever the system provides a token. Report the token that should have been used, not just the violation.
- **Interaction**: is the feedback the spec required actually implemented?

Where the adapter maps `validate`, the design system can check its own work. Run it and fold its output in:

```
.specify/extensions/design/scripts/bash/ds.sh query validate "<path or glob>" --json
```

### 5. Run the tests

Run the project's existing test command. A failing test is a finding like any other, and one you did not have to argue for.

### 6. Check the Definition of Done

`DOD_ITEMS` from the gate is the team's own Definition of Done. **If it is empty, skip this step entirely** and say nothing about it: most projects keep no DoD, and a checker that reports on its absence is nagging about a feature they chose not to use.

Where there are items, check each one against the change, the same way as everything above: against what the code and the repository actually show, not against what the plan intended. These are plain sentences rather than structured rules, so read each one for what it asks and find the evidence that settles it. An item you cannot check — nothing in the repository could show it either way, such as a sign-off that happens in another system — is reported as unchecked with the reason, never as met.

An unmet item is a **violation**: the team set this bar for themselves, so falling short of it is a contradiction of a stated requirement, not a suggestion. Number it into the same `DS-F-nnn` sequence as everything else, which is what puts it in the fix loop and keeps the feature from being done until it is resolved or argued.

Quote the item as written when reporting it. Do not rephrase it into your own words, and do not split one item into several findings: the team wrote that line, and they should recognise it in the finding.

If `DOD_ERROR` is non-empty, a DoD file was configured and could not be read. Report it prominently and treat this step as unchecked rather than passed. Someone believes their rules are being enforced; silence would leave them believing it.

### 7. Write the round

Append a validation round to `DESIGN_DOC`. The heading and the checkbox format are load-bearing: `workflow status` counts rounds from the heading and reads open findings from the unticked boxes, which is what makes the fix loop terminate.

```markdown
## Validation round 1 — 2026-05-14

Principles source: `docs` (version 2025.4). Surface kinds: interactive, layout. Tests: 48 passed, 1 failed.

- [ ] DS-F-001 **violation** · Date range · Bespoke `<input type="date">` pair; `DESIGN_DOC`
      committed to Rung 3 composition · Fix: use Calendar in Popover as recorded
- [ ] DS-F-002 **violation** · Filter row · `padding: 12px` hardcoded · Fix: use `space.3`
- [ ] DS-F-003 **violation** · Filter row · PRIN-FOCUS-VISIBLE: `outline: none` with no
      replacement · Fix: restore a focus indicator from the system's focus token
- [ ] DS-F-004 **warning** · Result table · No empty state · Fix: add per DS-006
```

Number findings sequentially across the whole feature, never restarting per round, so `DS-F-003` means one thing forever.

Classify honestly:

- **violation**: contradicts a `DS-` requirement, a principle in force, or a recorded ladder decision
- **warning**: a required dimension is unanswered, but nothing was contradicted
- **note**: a defensible deviation, recorded so the next reader knows it was deliberate

Do not pad the round. A checker that always finds something teaches people to ignore it; a clean round is a legitimate and reachable outcome, and when the work is clean, say so:

```markdown
## Validation round 2 — 2026-05-14

No findings. All round 1 findings verified fixed.
```

### 8. Hand back

Findings are fixed by the implementation pass, not here, with two exceptions: where a fix is small, local and unambiguous (a raw value with an obvious token, a missing `aria-label`), apply it, tick the box and say so in the round. Where a fix means reversing an implementation decision, leave it open. Silently rewriting a built feature from inside the checker collapses the separation this command exists to provide.

State the verdict plainly: the feature either meets its design requirements or it does not.

## Completion Report

Number of violations, warnings and notes; the violations themselves; which round this was and how many remain; whether the feature meets its design requirements; anything fixed in place.

## Done When

- [ ] Every surface in `DESIGN_DOC` was checked against what the code actually does
- [ ] Bespoke UI absent from `DESIGN_DOC` is flagged
- [ ] Every applicable principle was checked against the code using its `verify` step, and skipped ids are named
- [ ] Every finding names the principle or requirement it breaks and the fix that would clear it
- [ ] The design system's own prose guidance was read and checked against, not just the checkable rules
- [ ] Every required dimension was checked against the spec's `DS-` requirements
- [ ] The project's tests were run and their result recorded in the round
- [ ] Where the project keeps a Definition of Done, every item was checked and unmet ones raised as findings
- [ ] Findings are appended to `DESIGN_DOC` as `## Validation round N` with `- [ ] DS-F-nnn` entries
- [ ] The verdict is stated explicitly
