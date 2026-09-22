
<!--
  Appended by the design preset. Renumber to follow the principles already in
  your constitution, then run /speckit.constitution to materialize and version it.

  Why this belongs in the constitution rather than only in the extension:
  /speckit.analyze reads the constitution's MUST statements as a rule set and
  classifies conflicts as CRITICAL, requiring the spec, plan or tasks to change
  rather than the principle to be reinterpreted. Stating the ladder here makes it
  enforceable at analysis time, not just at the plan gate.
-->

### N. Recall → Reuse → Compose → Extend → Create (NON-NEGOTIABLE)

The design system is the source of truth for user interface, and it is consulted before
anything is built, not after. Every user-facing surface MUST be resolved at the lowest
rung of this ladder that holds:

0. **Recall**: another feature already resolved this surface, and its decision stands.
1. **Reuse**: an existing component covers the surface.
2. **Compose (pattern)**: an existing pattern covers the arrangement.
3. **Compose (components)**: existing components combine to cover it.
4. **Extend**: an existing component extends through a sanctioned mechanism.
5. **Create**: a new component, only when rungs 1 through 4 are documented as insufficient.

A surface MUST be looked up among the decisions already taken before the design system is
queried, and a prior decision MUST be adopted, or superseded in writing, rather than
quietly re-argued: two live answers to one question is the drift this ladder exists to
prevent. A rung MUST NOT be rejected without a written record of the candidates searched
and a concrete reason each is insufficient; "doesn't fit" is not a reason. A surface MUST be
described by capability rather than by the component the author has in mind, because
naming the component pre-decides the ladder. New components MUST be accompanied by a gap
record routed to the design system's owners; a new component that is built without one is
a private fork of the design system, regardless of where its source file lives.

Design requirements (states, responsive behaviour, accessibility, tokens and interaction)
MUST be stated in the specification and carried into the plan. They are requirements,
not review comments. Raw color, spacing and typography values MUST NOT be used where a
design token exists.

The design system's own principles, where it publishes any, are the authority for how its
components are used. Nothing MAY be substituted for them or merged into them. An
implementation MUST be validated against the specification and those principles by a pass
independent of the one that wrote it, and findings MUST be resolved or argued in writing
before the feature is considered done.

**Rationale**: coding agents are fast enough to build a locally plausible component before
anyone thinks to look for the existing one, and the result passes review because it works.
The cost lands later, as drift: two date pickers, three button variants, an accessibility
fix that has to be made in five places. The ladder is not bureaucracy against speed. It is
what keeps speed from being spent building what already exists.
