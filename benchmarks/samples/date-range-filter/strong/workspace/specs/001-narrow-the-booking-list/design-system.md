# Design system decisions: 001-narrow-the-booking-list

## Surface: choosing a start and an end date

**Resolution**: Compose (components)
**Decision**: Calendar with `mode="range"` inside a Popover, triggered by a
Button, with the range held in the form.

**Searched**:

| Candidate | Source | Verdict |
|---|---|---|
| Input | component | `type="date"` hands the control to the browser; no range semantics, no theme |
| Select | component | Dates are not an enumerable set |
| Calendar | component | Selects the range, but has no trigger and no popover |
| Popover | component | Solves placement, not the selection |
| DatePicker | pattern | The documented composition, and the lowest rung that holds |

**Why the chosen rung**: the registry ships no date range component, but it
documents this composition and the Calendar already takes `mode="range"`.
Building one would duplicate what the Calendar does.

**Design system impact**: none

## Surface: saying that the period is impossible

**Resolution**: Reuse
**Decision**: FormMessage, which is already wired to its control through
aria-describedby and aria-invalid.

## Surface: the list the filter acts on

**Resolution**: Reuse
**Decision**: the existing Table primitives, unchanged.

## Validation round 1 — 2026-09-18

- [x] DS-F-001 **violation** · Period control · trigger was `size="sm"`, a 32px
      target · Fix: `size="default"` with `min-h-11` at the sm breakpoint

## Validation round 2 — 2026-09-18

No findings.
