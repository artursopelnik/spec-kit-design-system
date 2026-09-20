---
description: "Record a justified design system gap and route it to the owning package"
---

# Design System Gap

Record that the design system genuinely does not cover a required surface, with the evidence that led there, and route it into the system's own intake. This is the fifth rung of the ladder. Reaching it is legitimate; reaching it silently is not.

A gap report is not paperwork. It is the mechanism that keeps the design system honest: every new component a product team needs is either a real gap the system should close, or a search that was not thorough enough. Writing it down is what tells the two apart.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Arguments normally name the surface that reached Rung 5.

## Prerequisites

Run `.specify/extensions/designsys/scripts/bash/check-design-gate.sh --json` and parse for `FEATURE_DIR`, `DESIGN_DOC`, `CONFIG`, `CAPABILITIES`.

The surface must already appear in `DESIGN_DOC` with rungs 1–4 documented as insufficient. **If it does not, stop** and run `/speckit.designsys.check` first. A gap report without a recorded search is exactly the failure mode this extension exists to prevent.

## Outline

### 1. Re-test the ladder once more

Before recording a gap, search once more with wording you have not tried yet — a synonym, the user-facing term, the term a designer would use, the term the system's own docs use for a neighbouring concept. Gaps found on the fifth search are common; gaps that survive a deliberate final attempt are real.

If this surfaces a viable candidate, **abandon the gap report**, update `DESIGN_DOC` to the lower rung, and say so. That is a good outcome, not a wasted step.

### 2. Write the record

Append to `DESIGN_DOC` under the surface's section:

```markdown
### Gap: <ProposedName>

**Surface**: <capability phrase>
**Existing alternatives searched**:
| Candidate | Source | Why insufficient |
|---|---|---|
| DatePicker | component | Single date only; no range semantics, no cross-field validation |
| Calendar | component | Display-only; no input affordance or form integration |
| Select | component | Wrong interaction model; enumerable options only |
| Popover | component | Container primitive; solves placement, not the control |

**Composition attempted**: Calendar inside Popover with two DatePickers — rejected because
range validation and the shared hover preview have to live above both fields, which the
composition cannot express without reaching into DatePicker internals.

**Extension attempted**: DatePicker exposes no prop for a second bound value; extending it
would mean forking its state model rather than using a supported escape hatch.

**Decision**: New component required.

**Scope**: <what it must do — and, importantly, what it must not grow into>
**Design system impact**: new component proposal | extension proposal to <Component>
**Proposed owner**: <package or team, from the CLI's routing if available>
**Interim approach**: <what this feature does while the gap is open>
```

Be specific about why each alternative fails. "Doesn't fit" is not a reason; "no range semantics, and range validation has to live above both fields" is.

### 3. Route it

If the adapter maps `report_gap`, file it with the design system's own intake:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json report_gap "<title>" "<body>"
```

Record the returned identifier or URL in `DESIGN_DOC` so the proposal can be tracked.

If `report_gap` is unmapped, say so explicitly in the completion report and name where the record lives instead. A design system with no intake path is itself worth surfacing to the user — that is the missing link between product teams finding gaps and the system closing them.

### 4. Constrain the local build

A new component built in a feature branch tends to become a permanent private fork. Record in `DESIGN_DOC` how that is avoided: where the component lives, that it uses the system's tokens and primitives rather than raw values, and what would have to happen for it to move upstream.

## Completion Report

State the proposed component, the alternatives ruled out, where the gap was filed (or that no intake exists), and the interim approach.

## Done When

- [ ] A final differently-worded search was attempted and its result recorded
- [ ] Every alternative carries a concrete reason it is insufficient
- [ ] Composition and extension attempts are documented, not just asserted
- [ ] The gap is filed with the design system, or the absence of an intake path is reported
- [ ] The local implementation is constrained to the system's tokens and primitives
