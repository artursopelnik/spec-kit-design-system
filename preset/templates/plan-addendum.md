
## Design System Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Populated by `/speckit.design.check`, which runs as a mandatory `before_plan` hook.
The full walk lives in `design-system.md` in this feature directory, together with the
validation rounds that check the implementation against it. This section is the summary
the plan is accountable to.

**Design system**: [NAME] · **Gate**: PASS | FAIL | NOT APPLICABLE

| Surface | Resolution | Decision | Source |
|---|---|---|---|
| [capability phrase] | Reuse / Compose (pattern) / Compose (components) / Extend / Create | [component, pattern or composition] | recalled `dd-001` / newly walked |

**Principles source**: cli | docs | default | unavailable
**Design system impact**: none | extension proposal | new component proposal
**Open gaps**: [gap records filed, with identifiers, or none]
**Decisions recorded**: [ids added to `.specify/memory/design-decisions.yml`, and any superseded]

### Constraints carried into the plan

Pulled from the components' own documentation, not invented:

- **Tokens**: [token families this feature must use]
- **States**: [states every instance must handle]
- **Responsive**: [behaviour per breakpoint]
- **Accessibility**: [keyboard model, names, focus order]
- **Interaction**: [required feedback and affordances]

### Design Complexity Tracking

Fill ONLY if the Design System Check resolved any surface at Extend or Create.
Each row must justify why the lower rungs do not hold. An empty or hand-waving
justification is a gate failure, not a formality.

| Surface | Rung taken | Lower rungs rejected because | Design system impact |
|---|---|---|---|
| [surface] | Extend / Create | [concrete reason, naming the candidates searched] | [proposal filed] |
