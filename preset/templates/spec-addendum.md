
## Design System Requirements *(include if the feature has a user-facing surface)*

<!--
  Populated by /speckit.designsys.sync against the design system CLI.
  Do not fill these from memory. A remembered component inventory is the exact
  failure this section exists to prevent. If the CLI is unreachable, leave the
  section marked unresolved rather than guessing.
-->

**Design system**: [NAME, resolved from designsys-config.yml]
**Surfaces identified**: [capability phrases, not component names]
**Breakpoints**: [the system's own names, retrieved from it, never invented]
**Token families in play**: [e.g. `color.surface.*`, `space.*`, `radius.*`]

### Requirements

Written as testable MUST/SHOULD statements with `DS-` IDs, in the same style as the
functional requirements above.

- **DS-001**: [System MUST reuse ... / MUST NOT introduce bespoke ...]
- **DS-002**: [Token requirement, referencing real token names from the system]
- **DS-003**: [State coverage requirement]
- **DS-004**: [Responsive behaviour requirement]
- **DS-005**: [Accessibility requirement]

Mark genuine ambiguity rather than resolving it silently:
`[NEEDS CLARIFICATION: system offers both Drawer and Modal here. Which is correct?]`

### Baseline

Requirements that hold for every feature in this design system, cited by id rather
than restated. The text lives in the extension's `baseline.yml`; copying it here
would create a second source of truth that drifts.

**Surface kinds**: [interactive, layout, text, media, motion — whichever apply]

| Rule | Dimension | Requirement |
|---|---|---|
| BL-… | … | [one line, with the system's real breakpoint and token names filled in] |

**Disabled for this project**: [rule ids and why, or none]

### Dimensions

Every dimension must be answered or explicitly excluded with a reason. A dimension
counts as covered when a baseline rule or a `DS-` requirement speaks to it.

| Dimension | Requirement | Covered by |
|---|---|---|
| States | default, hover, focus, active, disabled, loading, error, empty | DS-00? |
| Responsive | behaviour at each project breakpoint | DS-00? |
| Accessibility | keyboard model, accessible names, focus order, roles | DS-00? |
| Tokens | no raw hex / px / font stacks where a token exists | DS-00? |
| Interaction | feedback, affordance, latency expectations | DS-00? |

### Candidates surfaced

What the design system offered for each surface. This is evidence for the reuse
ladder in `/speckit.designsys.check`, not a decision. The decision is made there,
deliberately, and recorded in `design-system.md`.

| Surface | Candidates | Source |
|---|---|---|
| [capability phrase] | [Component, Pattern, ...] | search / component / pattern |
