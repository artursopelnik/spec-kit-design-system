---
description: "Take an RFC and run it to done: clarify, specify, plan, implement, validate, fix, verify — using the project's design system throughout"
---

# Run an RFC

Take an RFC and carry it through the whole Spec Kit lifecycle without asking the user to drive each phase by hand. This is the only command a developer needs.

```text
RFC → Clarify → Specify → Plan → Implement → Validate → Fix → Verify → Done
```

You own the run. Do not stop after a phase to ask whether to continue; continue. Stop only for the three things below, because each of them means proceeding would produce confident nonsense:

1. The RFC leaves a question open that changes what gets built, and nothing in the repository answers it.
2. The design system cannot be reached, so every design decision would be a guess.
3. Validation findings survive the configured number of rounds, which means the loop is not converging.

## User Input

```text
$ARGUMENTS
```

The argument is the RFC: a path to a file, `-` for stdin, or the text itself. It may also be empty, in which case look for an RFC the user has already put in the feature directory, and if there is none, ask for one. That is the only question worth asking before starting.

Where the RFC came from is not your concern. A file, a GitHub issue, a Jira ticket, an MCP resource: another tool fetched it, this one runs it.

## Prerequisites

```
.specify/extensions/design/scripts/bash/ds.sh gate --json
```

Without bash: `python3 .specify/extensions/design/scripts/python/design.py gate --json`. Identical behaviour. Every command below has the same fallback, so it is not repeated.

Parse `REACHABLE`, `UNREACHABLE_REASON`, `ADAPTER`, `PRINCIPLES_SOURCE`, `DOD_ITEMS`, `FEATURE_DIR`, `FEATURE_RFC`, `DESIGN_DOC`, `CONFIG`.

**If `REACHABLE` is `false`**: report `UNREACHABLE_REASON` and stop. Do not proceed from a remembered component inventory. A run that invents the design system is worse than no run, because everything downstream will look properly sourced.

**If `PRINCIPLES_SOURCE` is `default`**: the design system supplied no principles and the small default set is in force. Say so once, in the run report. It is not an error, but the user should know which principles the work was held to.

**If `PRINCIPLES_SOURCE` is `unavailable`**: nothing answered and the fallback is switched off, so no principles are in force. Report it and stop rather than proceeding: every phase after this one cites principles, and citing an empty set produces a spec that looks checked and is not.

## The loop

Before each phase, ask where the run is:

```
.specify/extensions/design/scripts/bash/ds.sh workflow status --json
```

It returns `next` and the reason for it, derived from the artifacts on disk rather than from a state file. That is what makes an interrupted run resumable: re-read, continue. Follow `next` rather than your own memory of what you have done.

Each phase gets its focused context, and only its focused context:

```
.specify/extensions/design/scripts/bash/ds.sh context <phase> --applies-to <kinds> --json
```

`available_on_demand` in that response lists everything the design system can still be asked, with the call to make. **Use it.** The context is a starting point, never a budget: whenever you need a component's props, a token value, a pattern's composition or the system's guidance on a question, ask for it. Working from what you happen to have been handed is the failure this phased context exists to prevent, not the behaviour it asks for.

### 1. Clarify

```
.specify/extensions/design/scripts/bash/ds.sh rfc <path> --json
```

Read `open_questions`, `warnings` and `sections`. Then answer what you can from the repository, the RFC itself, and the design system. Ask the user only about what is left and actually changes the outcome. One round of questions, not an interview.

Ambiguity about *how* to build something is usually not a question for the user: it is a question for the design system, and step 3 answers it.

Write the answers into the RFC understanding you carry forward. Then run `/speckit.specify` with the clarified RFC as its input.

### 2. Specify

`/speckit.specify` creates the feature and the spec. Then save the RFC, as given and with your clarifications appended, to `rfc.md` in the new feature directory (`FEATURE_RFC` from a fresh `ds.sh gate --json`). A spec describes *what*, so it tends to summarise a pasted design brief away; the gate and the scan read `rfc.md` to get it back word for word.

The design system is not consulted yet: that happens once, in the gate before planning.

When the spec comes back carrying `[NEEDS CLARIFICATION]` markers, resolve them from the user where they are product questions. Design questions are answered by the gate in the next step. A marker left standing will be resolved by guessing later, when the guess is more expensive.

### 3. Plan

`/speckit.plan`. The `before_plan` hook fires `/speckit.design.check`, which resolves the principles and tokens in force, walks Recall → Reuse → Compose → Extend → Create for every surface, writes `design-system.md` and the spec's `## Design System Requirements`, and blocks planning if a surface is unaccounted for. Most surfaces resolve on the short path (Recall or Reuse); the full walk is for the ones where something new would be built.

If the gate fails, fix the cause and re-run it. Do not disable it and do not route around it. Where it fails on a `[NEEDS CLARIFICATION]` it wrote, that is a design question only a person can answer: ask, record the answer in the spec, and re-run the gate.

Then `/speckit.tasks`.

### 4. Implement

`/speckit.implement`, working task by task.

Before writing code for a surface, pull exactly what you need for it:

```
.specify/extensions/design/scripts/bash/ds.sh context implement \
  --component DatePicker --component Popover --json
```

Then implement against the component's real props, variants, states and accessibility notes rather than against what a component of that name usually does. If a token, breakpoint or pattern is not in front of you, query it. Never write a literal color, length or font stack where a token exists.

Where `DOD_ITEMS` from the gate is non-empty, the team keeps a Definition of Done and validation will check it. Work to it as you go rather than discovering it in round 1: a missing changelog entry or story is cheap to write now and costs a whole round later.

### 5. Validate

The `after_implement` hook fires `/speckit.design.validate`. That command is the checker, and it is deliberately a separate pass with its own prerequisites: the agent that wrote the code is not the one that gets to declare it correct.

Run it as a genuine review, not a confirmation. It starts with `ds.sh scan`, which settles raw values and token names mechanically, runs the tests, and then reviews the whole change once. Its output is a numbered list of findings appended to `design-system.md` as a validation round.

### 6. Fix, then validate the fixes

```text
Validate → findings? ── no ──→ Verification (same pass) → Done
              │
             yes
              ↓
             Fix → Validate the fixes
```

For each open finding, make the smallest change that resolves it, then tick it off in `design-system.md`:

```markdown
- [x] DS-F-003 Filter row lost its focus indicator — restored via the system's focus token
```

Then re-run `/speckit.design.validate`. The second round checks the fixes, what they touched, the scan and the tests; it does not review the whole change again.

`workflow status` returns `next: "stop"` once `max_validation_rounds` (2 by default) is used up with work still unchecked. When that happens, **stop**. Report the surviving findings, what you tried, and why you think they are not converging. Findings that survive a full review and a round of targeted fixes are information; another round is noise.

A finding you disagree with is not fixed by deleting it. Argue it in the design document, mark it `[x]` with the reasoning, and let the next validation round judge.

### 7. Close

A clean validation round verifies the whole change against the RFC in the same pass and appends a `## Verification` section to `design-system.md`; the format is in `/speckit.design.validate`. Only then does `workflow status` return `complete: true`.

If `workflow status` returns `next: "verify"`, a clean round was written without its `## Verification` section. Add it now, as that command describes, rather than running another round.

The ladder decisions are already recorded: `/speckit.design.check` writes each
surface it walks, at the moment it walks it, which is the only point where the
candidates and the reasoning are still in hand. **Do not record them again here.**
A second write for the same capability is refused, and rightly — two active
decisions for one surface is the drift the ladder exists to prevent.

Confirm instead that the walk landed:

```
.specify/extensions/design/scripts/bash/ds.sh ledger list --json
```

Skip this when `ledger.enabled` in `CONFIG` is false: the project keeps no ledger
and there is nothing to confirm. Otherwise every surface resolved in `DESIGN_DOC`
should appear, except those adopted unchanged from a prior decision, which were
already there. A surface that is missing means the gate passed without committing
its reasoning to memory: record it now, with the aliases actually searched,
before the run closes.

## Completion Report

Short. The user asked for a change, not a narrative:

- What was built, in one or two sentences.
- Which design system components, patterns and tokens it used, and any surface that reached Extend or Create with the reason.
- Which principles were in force, where they came from (`cli`, `docs` or `default`) and at what version, plus any that could not be enforced for want of a `verify` step.
- Validation: how many rounds, what was found, what was fixed.
- Where the project keeps a Definition of Done, that it was checked and is met. Say nothing about it where there is none.
- Anything left open, and why.
- What asking the design system cost: `calls` and `hits` from `.specify/extensions/design/scripts/bash/ds.sh cache stats --json`, one line.

## Done When

- [ ] The RFC's open questions are answered, not assumed
- [ ] The spec carries no unresolved `[NEEDS CLARIFICATION]` markers
- [ ] Every UI surface was resolved through the ladder against the real design system
- [ ] The implementation uses the system's own components and tokens, with no invented names
- [ ] Validation ran as an independent pass and its findings were fixed or argued
- [ ] The final validation round is clean, or the run stopped and said why
- [ ] Every newly-walked surface is in the ledger, recorded once, by the gate
- [ ] A `## Verification` section in `design-system.md` records what was checked and the verdict
