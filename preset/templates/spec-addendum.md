
## Design System Requirements *(include if the feature has a user-facing surface)*

<!--
  Populated by /speckit.design.check, the gate before planning, from the
  decisions it records in design-system.md.
  Do not fill these from memory. A remembered component inventory is the exact
  failure this section exists to prevent. If the CLI is unreachable, leave the
  section marked unresolved rather than guessing.
-->

**Design system**: [NAME, resolved from design-config.yml]
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

### Principles in force

Cited by id rather than restated. The text lives at its source; copying it here
would create a second source of truth that drifts.

**Source**: cli | docs | default | unavailable — where these came from. `default`
means the design system supplied none and the extension's small default set
applies; `unavailable` means nothing is in force and nothing below was checked.
**Version**: [what the source calls this revision, or none stated]
**Surface kinds**: [interactive, layout, text, media, motion — whichever apply]

Only principles that can be checked are cited here: each states a MUST or SHOULD
and carries a `verify` step.

| Principle | Dimension | Requirement |
| --- | --- | --- |
| … | … | [one line, with the system's real breakpoint and token names filled in] |

**Disabled for this project**: [ids and why, or none]
**Stated but not enforceable**: [ids with no `verify` step, or none]

### Dimensions

Every dimension must be answered or explicitly excluded with a reason. A dimension
counts as covered when a principle or a `DS-` requirement speaks to it.

| Dimension | Requirement | Covered by |
|---|---|---|
| States | default, hover, focus, active, disabled, loading, error, empty | DS-00? |
| Responsive | behaviour at each project breakpoint | DS-00? |
| Accessibility | keyboard model, accessible names, focus order, roles | DS-00? |
| Tokens | no raw hex / px / font stacks where a token exists | DS-00? |
| Interaction | feedback, affordance, latency expectations | DS-00? |

### Surfaces

Each surface's resolution (the component, pattern, composition or lab component
it lands on, and why) lives in `design-system.md` in this feature directory,
which is the contract the plan, the implementation and validation read. It is
not repeated here, so there is one place to change it.
