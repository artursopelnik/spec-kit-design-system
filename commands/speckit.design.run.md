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

Parse `REACHABLE`, `UNREACHABLE_REASON`, `ADAPTER`, `GUIDELINES_SOURCE`, `FEATURE_DIR`, `CONFIG`.

**If `REACHABLE` is `false`**: report `UNREACHABLE_REASON` and stop. Do not proceed from a remembered component inventory. A run that invents the design system is worse than no run, because everything downstream will look properly sourced.

**If `GUIDELINES_SOURCE` is `default`**: the design system supplied no guidelines and the small default set is in force. Say so once, in the run report. It is not an error, but the user should know which guidelines the work was held to.

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

`/speckit.specify` creates the feature and the spec. The `after_specify` hook fires `/speckit.design.context`, which resolves the guidelines in force, searches the design system for each surface, and writes the `## Design System Requirements` section.

Let the hook do that work. Do not duplicate it here.

When the spec comes back carrying `[NEEDS CLARIFICATION]` markers, resolve them: from the design system where they are design questions, from the user where they are product questions. A marker left standing will be resolved by guessing later, when the guess is more expensive.

### 3. Plan

`/speckit.plan`. The `before_plan` hook fires `/speckit.design.check`, which walks Reuse → Compose → Extend → Create for every surface and blocks planning if a surface is unaccounted for.

If the gate fails, fix the cause and re-run it. Do not disable it and do not route around it.

Then `/speckit.tasks`.

### 4. Implement

`/speckit.implement`, working task by task.

Before writing code for a surface, pull exactly what you need for it:

```
.specify/extensions/design/scripts/bash/ds.sh context implement \
  --component DatePicker --component Popover --json
```

Then implement against the component's real props, variants, states and accessibility notes rather than against what a component of that name usually does. If a token, breakpoint or pattern is not in front of you, query it. Never write a literal color, length or font stack where a token exists.

### 5. Validate

The `after_implement` hook fires `/speckit.design.validate`. That command is the checker, and it is deliberately a separate pass with its own prerequisites: the agent that wrote the code is not the one that gets to declare it correct.

Run it as a genuine review, not a confirmation. Its output is a numbered list of findings appended to `design-system.md` as a validation round.

### 6. Fix, then validate again

```text
Validate → findings? ── no ──→ Verify → Done
              │
             yes
              ↓
             Fix → Validate
```

For each open finding, make the smallest change that resolves it, then tick it off in `design-system.md`:

```markdown
- [x] DS-F-003 Filter row lost its focus indicator — restored via the system's focus token
```

Then re-run `/speckit.design.validate`. It appends the next round.

`workflow status` returns `may_validate_again: false` once `max_validation_rounds` is used up. When that happens, **stop**. Report the surviving findings, what you tried, and why you think they are not converging. Three rounds that fail the same way is information; a fourth is noise.

A finding you disagree with is not fixed by deleting it. Argue it in the design document, mark it `[x]` with the reasoning, and let the next validation round judge.

### 7. Verify

Last pass, over the whole change rather than per finding:

- Every acceptance criterion in the RFC is met.
- Every `DS-` requirement in the spec is satisfied.
- Every guideline in force was honoured, or its exception is written down.
- The tests the project already has still pass. Run them.
- `workflow status` returns `complete: true`.

Record each new ladder decision so the next feature does not re-derive it:

```
.specify/extensions/design/scripts/bash/ds.sh ledger record - --json <<'JSON'
{"capability":"selection of a date range","resolution":"compose",
 "decision":"Popover + Calendar + two DateField inputs",
 "aliases":["date range picker","period filter"],
 "feature":"001-booking-filters","design_system_version":"2.1.0"}
JSON
```

## Completion Report

Short. The user asked for a change, not a narrative:

- What was built, in one or two sentences.
- Which design system components, patterns and tokens it used, and any surface that reached Extend or Create with the reason.
- Which guidelines were in force and where they came from (`cli`, `adapter` or `default`).
- Validation: how many rounds, what was found, what was fixed.
- Anything left open, and why.

## Done When

- [ ] The RFC's open questions are answered, not assumed
- [ ] The spec carries no unresolved `[NEEDS CLARIFICATION]` markers
- [ ] Every UI surface was resolved through the ladder against the real design system
- [ ] The implementation uses the system's own components and tokens, with no invented names
- [ ] Validation ran as an independent pass and its findings were fixed or argued
- [ ] The final validation round is clean, or the run stopped and said why
- [ ] New ladder decisions are in the ledger
