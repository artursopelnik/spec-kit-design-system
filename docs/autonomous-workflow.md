# The autonomous workflow

What `/speckit.design.run` actually does, and where the guardrails are.

```text
RFC
 ↓
Clarify ──────────── what the RFC does not say
 ↓
Specify ──────────── /speckit.specify
 ↓
Plan ─────────────── /speckit.plan behind the gate, which walks the ladder and
 ↓                   writes the spec's design requirements; then /speckit.tasks
 ↓
Implement ────────── /speckit.implement, task by task
 ↓
Validate ─────────── independent pass, appends a round of findings
 ↓
findings? ─── no ──▶ Verify ──▶ Done
 │
 yes
 ↓
Fix ──▶ Validate     bounded at max_validation_rounds
```

## What "autonomous" means here

The run continues on its own between phases. It stops for three things, and nothing else:

1. **A question that changes what gets built**, which the RFC leaves open and the repository cannot answer. Asked once, as a batch, not as an interview.
2. **An unreachable design system.** Every downstream decision would be a guess dressed up as sourced work.
3. **Findings that will not converge**, after the configured number of validate–fix rounds.

It does not stop to ask permission to proceed, and it does not hand back after each phase. That was the point of the refactor: a developer gives it an RFC, not a sequence of commands.

## Where it keeps its place

Nowhere — deliberately. Before each phase the run asks:

```bash
ds.sh workflow status --json
```

which derives the position from the artifacts on disk: whether `spec.md` still carries `[NEEDS CLARIFICATION]`, whether `plan.md` exists, whether `tasks.md` has unticked tasks, how many validation rounds `design-system.md` records, which findings are still open, and whether it carries a `## Verification` section. There is no `iterations.md`, no `memory.md`, no run-state file to get out of sync.

The practical benefit: an interrupted run resumes by reading. So does a second agent, a different session, or a human who wants to know where things stand.

## Focused context, and the line it must not cross

Each phase starts with what it needs:

```bash
ds.sh context implement --component DatePicker --component Popover --json
```

- **clarify** — RFC, principles
- **specify** — RFC, principles, candidates for the surfaces searched
- **plan** — spec, principles, named components, tokens, breakpoints
- **implement** — plan, named components, tokens
- **validate** — spec, principles, named components
- **verify** — spec, principles

The whole inventory is never inlined. But every response carries `available_on_demand` and `retrieval`, listing each capability the design system can still answer and the exact call that gets it, and the commands tell the agent to use them.

The distinction is the feature:

> **Focused context is about what arrives first. It is never about what is reachable.**

An agent that cannot get a component's real props will invent plausible ones, and plausible-but-wrong is the most expensive output there is. Reducing noise is worth doing; creating blind spots is not.

## Maker and checker

`/speckit.design.validate` is a separate pass with its own prerequisites, its own context, and instructions to read the work as someone else's. The agent that wrote the code does not get to be the only one deciding it is correct.

It is deliberately lightweight: no verdict files, no sign-off workflow, no governance. Just a checker that writes findings the implementation pass has to answer.

Findings go into `design-system.md`:

```markdown
## Validation round 1 — 2026-05-14

- [ ] DS-F-001 **violation** · Filter row · `padding: 12px` hardcoded · Fix: use `space.3`
- [ ] DS-F-002 **warning** · Result table · No empty state · Fix: add per DS-006
```

Numbered sequentially across the whole feature, never restarting per round, so `DS-F-002` means one thing forever. The heading format and the checkbox are read by `workflow status`, which is what makes the loop terminate.

## Termination

Two conditions end the loop, and one of them is subtle:

- **A round with no findings ends it.** A round whose findings were _ticked off_ does not. Otherwise the fixing pass would be signing off its own fixes, and the checker separation would be decorative.
- **`max_validation_rounds` (default 3) stops it.** The run reports what is still open, what it tried, and why it thinks the findings are not converging. Three rounds that fail the same way is information; a fourth is noise.

Ending the loop is not finishing the run. A clean round sets `next` to `verify`, which asks the question validation does not: did the RFC actually get what it asked for. That pass appends a `## Verification` section to `design-system.md`, and `complete: true` follows from that section existing — the same artifact-derived rule as every other phase.

Raise it if your project genuinely needs to:

```yaml
workflow:
  max_validation_rounds: 5
```

## Driving it by hand

Everything above is also true phase by phase. The hooks are wired in `extension.yml`, not inside the run command, so `/speckit.specify`, `/speckit.plan` and `/speckit.implement` fire the context, gate and validate steps whether or not you used `/speckit.design.run`. The autonomous path is a convenience over the same rails, and skipping it costs you nothing but the typing.
