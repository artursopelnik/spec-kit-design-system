---
description: "Check the implementation independently against design-system.md, the spec and the principles, raise findings that feed back into fixing, and record the verification when it is clean"
---

# Design System Validate

Check what was actually built against what the ladder committed to in `design-system.md`, the spec's `DS-` requirements and the principles in force. This runs as an **`after_implement` hook** and is the checker half of the workflow: the agent that wrote the code does not also get to decide it is correct.

Read this as a review of someone else's work, because for this pass it is. Your job is to find what is wrong, not to confirm what you hoped was right. Anything you find becomes a numbered finding that the run must fix.

It is also deliberately **bounded**. What a script can settle, a script settles, before the review starts. Round 1 reviews the whole change; a later round checks only the fixes. A clean round closes the run by writing the verification in the same pass.

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

Parse the gate for `FEATURE_DIR`, `FEATURE_SPEC`, `DESIGN_DOC`, `IMPL_PLAN`, `CONFIG`, `CAPABILITIES`, `HAS_TOKENS`, `REQUIRED_DIMENSIONS`, `PRINCIPLES_SOURCE`, `PRINCIPLES_DISABLED`, `PRINCIPLES_UNENFORCEABLE`, `DOD_ITEMS`, `DOD_ERROR`; the status for `validation_rounds_used`, `max_validation_rounds`, `may_validate_again` and `closed_findings`.

**If `DESIGN_DOC` does not exist**: the gate never ran for this feature. Report that validation has no contract to check against and recommend `/speckit.design.check`. Do not improvise a contract now. A check against a contract invented after the fact tells you nothing.

**If `may_validate_again` is `false`**: the loop has used its rounds. Do not start another. Report the findings still open and stop; this needs a human.

This round is number `validation_rounds_used + 1`. Round 1 is a **full round**; any later round is a **fix round**.

## Outline

### 1. Scan first

Use `validation.source_globs` from `CONFIG` if set. Otherwise infer the implementation paths from the plan's `## Project Structure` section, narrowed to files the feature actually touched, and pass them:

```
.specify/extensions/design/scripts/bash/ds.sh scan --path "src/features/booking/**/*.tsx" --json
```

The scan states what needs no judgement, and each of these is a finding without further argument:

- **`raw_values`**: when `validation.forbid_raw_values` is true and `has_tokens` is true, every literal colour, length or font stack is a **violation**. Report the token that should have been used, not just the value. Files that define the tokens are exempt through `validation.theme_globs`; a literal the design system genuinely has no token for is a **note** that says so.
- **`unknown_tokens`**: the contract or the spec names a token the design system does not have. A **violation**: a typo, or a token renamed since the spec was written.
- **`tokens_not_seen`**: a real token the contract asks for appears nowhere in the scanned code under any usual spelling. Look where it belongs: if the surface uses it under a spelling the scan does not know, move on; if it is not used, that is a **violation**.

Then run the project's existing test command. A failing test is a finding like any other, and one you did not have to argue for.

Both run in every round, full or fix: they are cheap, and they are how a fix that broke something else gets caught.

### 2. Full round: review the change

Only in round 1. Ask the design system for what you need as you go; answers are remembered for the feature, so asking again costs nothing:

```
.specify/extensions/design/scripts/bash/ds.sh context validate --applies-to <kinds> \
  --component <Name> --json
```

A finding you cannot substantiate because you did not look something up is not a finding; look it up.

**Each committed decision.** For every surface in `DESIGN_DOC`, verify the code did what was decided:

- **Reuse** → the named component is imported from the design system and actually used for that surface, with the variant, prop or theme setting the contract named for its appearance. A component imported and then wrapped in enough overrides to change its behaviour is not reuse; flag it.
- **Compose** → the named components appear, arranged as described. A composition that quietly grew a bespoke replacement for one of its parts has drifted.
- **Extend** → extension went through the sanctioned mechanism recorded in the ladder, not a copied-and-edited fork.
- **Create** → the lab component exists where the gap record said it would, is marked as not part of the design system with a pointer to its gap record, is built from the system's tokens and primitives, and did not grow past the scope the record set.

Flag anything built bespoke that never appeared in `DESIGN_DOC` at all. This is the highest-value finding here: it is the exact failure this extension exists to catch, and it will usually look locally reasonable.

**The principles in force.**

```
.specify/extensions/design/scripts/bash/ds.sh principles --applies-to <kinds from the spec> --json
```

Each entry carries a `verify` field saying how to check it. Work through the ids each surface lists under **Principles that apply**, and check the rest of the applicable set against that surface too: a principle the check phase did not list is not thereby satisfied. These are the requirements nobody writes down, so they are also the ones nobody checks: a control with no focus style, a layout that breaks at 320px, an action reachable only on hover.

Ids in `unenforceable` have no `verify` step: report them as a gap in the principles themselves, not as a finding against this feature. `prose` is not mechanically checkable and still binds; check the implementation against what the design system actually says about this kind of surface. An id listed in `PRINCIPLES_DISABLED` is not checked; note that it was skipped.

Check against the code, not against the spec's claims. The spec saying `PRIN-FOCUS-VISIBLE` applies is not evidence that focus is visible. Report a principle finding under its id.

**The dimensions.** For each dimension in `REQUIRED_DIMENSIONS`, check the corresponding `DS-` requirements from the spec:

- **States**: are default, hover, focus, active, disabled, loading, error and empty handled where applicable? Missing loading and error states are the most common real defect here.
- **Responsive**: does the layout behave at every project breakpoint, per the spec's stated behaviour?
- **Accessibility**: accessible names present, keyboard operability, focus order following visual order, roles correct, focus visible, as the component's own documentation (`ds.sh query component "<Name>"`) states them.
- **Tokens**: settled by the scan in step 1; do not re-derive it by reading.
- **Interaction**: is the feedback the spec required actually implemented?

Where the adapter maps `validate`, the design system can check its own work. Run it and fold its output in:

```
.specify/extensions/design/scripts/bash/ds.sh query validate "<path or glob>" --json
```

**The Definition of Done.** `DOD_ITEMS` from the gate is the team's own Definition of Done. **If it is empty, skip this entirely** and say nothing about it: most projects keep no DoD, and a checker that reports on its absence is nagging about a feature they chose not to use.

Where there are items, check each one against what the code and the repository actually show, not against what the plan intended. An item you cannot check (nothing in the repository could show it either way, such as a sign-off that happens in another system) is reported as unchecked with the reason, never as met. An unmet item is a **violation**, numbered into the same `DS-F-nnn` sequence. Quote the item as written when reporting it; do not rephrase it or split it into several findings.

If `DOD_ERROR` is non-empty, a DoD file was configured and could not be read. Report it prominently and treat the DoD as unchecked rather than passed.

Every finding names the principle or requirement it breaks and a concrete fix: the change that would clear it, not a restatement of the problem. A finding without a fix is an opinion with a checkbox.

### 3. Fix round: check the fixes

In round 2 and later, do **not** review the whole change again. That was round 1's job, and repeating it is how validation used to take as long as implementing.

- For every finding of the previous round that is now ticked (it is in `closed_findings`), check the code: is it actually fixed, and fixed the way the finding said? A ticked box whose problem is still there is reopened as a new finding that names the original.
- A finding marked `[x]` with an argument instead of a fix: judge the argument. Accept it as a **note**, or reopen it.
- Read what the fixes changed, and only that, for anything they broke.
- The scan and the tests from step 1 have already run.

A new finding in a fix round comes from the scan, the tests, or the code the fixes touched. Nothing else.

### 4. Write the round

Append a validation round to `DESIGN_DOC`. The heading and the checkbox format are load-bearing: `workflow status` counts rounds from the heading and reads open findings from the unticked boxes, which is what makes the fix loop terminate.

```markdown
## Validation round 1 — 2026-05-14

Principles source: `docs` (version 2025.4). Surface kinds: interactive, layout.
Scan: 14 files, 2 raw values, 0 unknown tokens. Tests: 48 passed, 1 failed.

- [ ] DS-F-001 **violation** · Date range · Bespoke `<input type="date">` pair; `DESIGN_DOC`
      committed to Rung 3 composition · Fix: use Calendar in Popover as recorded
- [ ] DS-F-002 **violation** · Filter row · `padding: 12px` hardcoded · Fix: use `space.3`
- [ ] DS-F-003 **violation** · Filter row · PRIN-FOCUS-VISIBLE: `outline: none` with no
      replacement · Fix: restore a focus indicator from the system's focus token
- [ ] DS-F-004 **warning** · Result table · No empty state · Fix: add per DS-006
```

Number findings sequentially across the whole feature, never restarting per round, so `DS-F-003` means one thing forever.

Classify honestly:

- **violation**: contradicts a `DS-` requirement, a principle in force, a recorded ladder decision, or the team's Definition of Done
- **warning**: a required dimension is unanswered, but nothing was contradicted
- **note**: a defensible deviation, recorded so the next reader knows it was deliberate

Do not pad the round. A checker that always finds something teaches people to ignore it; a clean round is a legitimate and reachable outcome, and when the work is clean, say so:

```markdown
## Validation round 2 — 2026-05-14

No findings. All round 1 findings verified fixed.
```

### 5. A clean round closes the run

When the round you just wrote has no findings, the loop is over, and the last question is one validation does not ask on its own: did the change deliver what was asked for? Answer it now, in this pass:

- Every acceptance criterion of the RFC, as the spec's acceptance scenarios carry them, is met by what was built.
- Every `DS-` requirement in the spec is satisfied.
- Where `DOD_ITEMS` is non-empty, every item is met.
- The tests passed in this round's run.

Then append a `## Verification` section to `DESIGN_DOC`, directly after the round. The heading is load-bearing in the same way the round heading is: `workflow status` reads it, and without it the run reports `next: verify` instead of done. Say what was checked and the verdict, not just that it happened:

```markdown
## Verification — 2026-05-14

RFC acceptance criteria: 3 of 3 met.
Spec requirements: DS-001 … DS-005 satisfied.
Principles: `docs` (version 2025.4), all applicable honoured; ACME-DENSITY not
enforceable (no verify step), noted rather than checked.
Definition of Done: no file; not checked.
Tests: 48 passed.

Verdict: the change meets its design requirements.
```

If a criterion is not met, it is not verified: raise it as a finding in this round instead, and the round is not clean.

### 6. Hand back

Findings are fixed by the implementation pass, not here, with two exceptions: where a fix is small, local and unambiguous (a raw value with an obvious token, a missing `aria-label`), apply it, tick the box and say so in the round. Where a fix means reversing an implementation decision, leave it open. Silently rewriting a built feature from inside the checker collapses the separation this command exists to provide.

State the verdict plainly: the feature either meets its design requirements or it does not.

## Completion Report

Which round this was, full or fix; the scan's numbers; the number of violations, warnings and notes and the violations themselves; how many rounds remain; anything fixed in place; and, for a clean round, the verification verdict.

## Done When

- [ ] The scan ran and its raw values, unknown tokens and unseen tokens were each turned into a finding or accounted for
- [ ] The project's tests were run and their result recorded in the round
- [ ] In a full round: every surface in `DESIGN_DOC` was checked against what the code actually does, and bespoke UI absent from it is flagged
- [ ] In a full round: every applicable principle was checked using its `verify` step and the design system's prose guidance, and skipped ids are named
- [ ] In a full round: every required dimension was checked, and where the project keeps a Definition of Done, every item
- [ ] In a fix round: every ticked finding was checked in the code, and nothing outside the fixes was re-reviewed
- [ ] Every finding names the principle or requirement it breaks and the fix that would clear it
- [ ] Findings are appended to `DESIGN_DOC` as `## Validation round N` with `- [ ] DS-F-nnn` entries
- [ ] A clean round is followed by a `## Verification` section with what was checked and the verdict
