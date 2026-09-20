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

The surface must already appear in `DESIGN_DOC` with rungs 1 through 4 documented as insufficient. **If it does not, stop** and run `/speckit.designsys.check` first. A gap report without a recorded search is exactly the failure mode this extension exists to prevent.

## Outline

### 1. Re-test the ladder once more

Before recording a gap, search once more with wording you have not tried yet: a synonym, the user-facing term, the term a designer would use, the term the system's own docs use for a neighbouring concept. Gaps found on the fifth search are common; gaps that survive a deliberate final attempt are real.

If this surfaces a viable candidate, **abandon the gap report**, update `DESIGN_DOC` to the lower rung, and say so. That is a good outcome, not a wasted step.

### 2. Write the record

Write it to **its own file**, `design-system-gap-<slug>.md` in the feature directory, and link it from the surface's section in `DESIGN_DOC`.

A standalone file matters: a gap record is the argued case for a new component, and it usually has to travel: to the design system's repo, to an issue tracker, to a review. A section buried inside `design-system.md` cannot be handed to another tool or another team. This file is written so it can be, unchanged.

Use this structure:

```markdown
# RFC: <ProposedName>

**Status**: proposed
**Raised by**: <feature id, e.g. 003-booking-filters>
**Design system**: <name> <version>
**Surface**: <capability phrase>

## Summary

<Two sentences: what capability is missing, and what this proposes.>

## Existing alternatives searched
| Candidate | Source | Why insufficient |
|---|---|---|
| DatePicker | component | Single date only; no range semantics, no cross-field validation |
| Calendar | component | Display-only; no input affordance or form integration |
| Select | component | Wrong interaction model; enumerable options only |
| Popover | component | Container primitive; solves placement, not the control |

## Composition attempted

Calendar inside Popover with two DatePickers, rejected because range validation and the
shared hover preview have to live above both fields, which the composition cannot express
without reaching into DatePicker internals.

## Extension attempted

DatePicker exposes no prop for a second bound value; extending it would mean forking its
state model rather than using a supported escape hatch.

## Proposal

**Scope**: <what it must do, and importantly what it must not grow into>
**Impact**: new component | extension to <Component>
**Proposed owner**: <package or team, from the CLI's routing if available>
**Interim approach**: <what this feature does while the gap is open>
```

Be specific about why each alternative fails. "Doesn't fit" is not a reason; "no range semantics, and range validation has to live above both fields" is.

### 3. Route it

The RFC file is the deliverable and it is complete on its own. Routing it is a handoff, and how you hand it off depends on what the project already runs. **Do not build a path that an installed extension already provides.**

In order of preference:

**The design system's own intake.** If the adapter maps `report_gap`, file it there. This is the most direct route, because it reaches the people who own the component:

```
.specify/extensions/designsys/scripts/bash/ds-query.sh --json report_gap "<title>" "<body>"
```

Record the returned identifier or URL in the RFC's header so the proposal can be tracked.

**An issue tracker the project already syncs with.** If `report_gap` is unmapped, check `.specify/extensions.yml` for an installed tracker extension and tell the user which one can carry this. Core `/speckit.taskstoissues` targets GitHub Issues, and extensions such as `jira`, `jira-mirror`, `linear` or `azure-devops` retarget it. Name the command; do not invoke it yourself. Which tracker a component request belongs in, and under which project key, is the user's call, and a design system request usually belongs in the **design system's** project, not the product team's.

**Nothing installed.** Then the RFC file *is* the artifact. Say so plainly: it is a complete, reviewable proposal that can be committed, pasted into a tracker by hand, or opened as a pull request against the design system repo. Do not treat the absence of a tracker as a failure, and do not invent an intake path.

A design system with no intake route at all is worth surfacing once to the user, since it is the missing link between product teams finding gaps and the system closing them, but say it as an observation, not as a blocker.

### 4. Constrain the local build

A new component built in a feature branch tends to become a permanent private fork. Record in `DESIGN_DOC` how that is avoided: where the component lives, that it uses the system's tokens and primitives rather than raw values, and what would have to happen for it to move upstream.

## Completion Report

State the proposed component, the alternatives ruled out, where the RFC file lives, where it was filed (or which command would file it), and the interim approach.

## Done When

- [ ] A final differently-worded search was attempted and its result recorded
- [ ] The RFC exists as its own file and reads as a complete proposal without the rest of the feature directory
- [ ] Every alternative carries a concrete reason it is insufficient
- [ ] Composition and extension attempts are documented, not just asserted
- [ ] The RFC is filed, or the command that would file it is named, or the user is told the file itself is the artifact
- [ ] The local implementation is constrained to the system's tokens and primitives
