# Benchmarks

Does the extension actually produce better work, or does it just produce more
process? This directory is the apparatus for answering that with numbers instead
of conviction.

It ships the harness, the cases, the scorer and a blind pairwise judge, so a
claim can be a rate (*9 of 10 runs*), a price (*2.4× the tokens*) or a
preference (*preferred in 71% of blind pairs*), rather than an adjective.
**It ships no results.** The
tables further down have no numbers in them yet, on purpose: publishing a
comparison means running an agent many times, and a number nobody can reproduce
is worse than no number. Running it is one command per arm.

## What is compared

The same RFC, on the same design system, three times over:

| Arm | What the agent has |
|---|---|
| `unaided` | The RFC, the repository, and the design system |
| `speckit` | Plus Spec Kit: specify → plan → tasks → implement |
| `extension` | Plus this extension: `/speckit.design.run` |

The middle arm exists so that whatever the numbers show gets attributed to the
right thing. An extension that only recovers what plain Spec Kit already gives
you is not worth installing, and a two-arm comparison cannot tell the
difference.

**Every arm is given the design system.** The inventory sits at the same path in
all three workspaces, an identical `AGENTS.md` says where it is and that it is
the source of truth, and the `unaided` and `speckit` prompts both say to reuse
what exists before building anything new. Withholding it from the comparison
arms would produce a much better-looking result and measure nothing. If you
change one arm's setup, change all three or the run is void.

## What is scored

Five metrics, equally weighted, each between 0 and 1. All five are computable
from any workspace, whichever arm produced it — none of them look for an
artifact only the extension can produce. That property is what makes the
comparison mean anything, and there is a test that holds it.

| Metric | The question | How it is answered |
|---|---|---|
| `inventory_fidelity` | Does the work only use components and APIs the system has? | Component references are resolved against the inventory. A name imported from the design system that it does not export, or a `variant` a component does not declare, is a finding. Names imported from third-party packages are a dependency decision, not a claim, and are left out. |
| `ladder_outcome` | Did each surface land on what the system already offers? | Per surface: did the work use one of the compositions the system actually supports, and did it avoid the cheaper wrong answers this case names (a native date input, a dismissible confirmation, a pixel media query). A surface that was built new but argued in a gap record earns part of the credit, never all of it. |
| `token_discipline` | Does styling go through the system's scale, or around it? | Literal colours and lengths in component code, against uses of the system's tokens, classes or theme. The file that defines the theme is exempt, because that is where those values are supposed to live. |
| `guideline_coverage` | Do the rules in force show up in the work? | Each guideline the case names is looked for by evidence: `FormMessage` and `aria-describedby` for a rule about announced errors, `size="large"` or a 44px target for a rule about touch. |
| `criteria_traceability` | Did the RFC's acceptance criteria survive? | Each criterion is looked for in the documents and tests the run produced, or in the code when it produced neither. |

The total is the mean of whichever metrics apply. A metric with nothing to look
at (no code, no documents) is reported as inapplicable rather than as zero, so
a run that produced nothing does not look like a run that produced something
bad. `metrics_applicable` distinguishes them.

Scoring is deterministic: the agent run is the only stochastic part, and
everything after it is a pure function of the files on disk.

### The same evidence as pass or fail

A median of 0.82 is the right thing to optimise and the wrong thing to say out
loud. So every run also answers seven yes/no checks, derived from the same
evidence:

| Check | True when |
|---|---|
| Used what the system already has | Every surface resolved to something the system offers |
| Avoided the shortcuts | No pattern the case names as the wrong answer |
| Invented nothing | No component or variant the system does not have |
| No literal colours or lengths | Nothing outside the theme file |
| Carried every guideline | Every rule in force shows up in the work |
| Traced every criterion | Every acceptance criterion survived |
| All of the above, in one run | The four-out-of-five problem, made visible |

The report prints these as `k/n` per arm, which is the form a sentence can be
built on: *"in 9 of 10 runs on shadcn/ui the extension arm used the component
the system already had; without it, 4 of 10 did"*. A check is unanswered, not
failed, when the run produced nothing to look at, so `n` never quietly includes
runs that never happened.

### What it cost

The other half of any claim. When the agent reports its own accounting, the
runner records it: Claude Code's `--output-format json` (or the final result
line of `stream-json`) is read directly, and any other agent can drop a
`usage.json` in the workspace and be counted the same way.

```bash
--agent 'claude --permission-mode acceptEdits --output-format json -p "$(cat {prompt_file})"'
```

The report then prints tokens, output tokens, cost, turns and wall clock per
arm, and states the ratio outright. Expect the extension arm to cost more: it
runs more phases and asks the design system real questions. An honest result
says so in the same breath as the win — *"2.4× the tokens, and here is what that
bought"* — because a reader who finds that out later stops believing the rest.

### Which one is better, asked properly

Counting cannot answer "looks better" or "code I would rather own". That gets
asked, under conditions that make the answer worth quoting:

```bash
python benchmarks/harness/judge.py pair \
  --a benchmarks/results/date-range-filter/speckit/<run> \
  --b benchmarks/results/date-range-filter/extension/<run> \
  --judge 'claude -p "$(cat {prompt_file})"' --judge-name claude-opus-5 --both-orders

python benchmarks/harness/judge.py tally benchmarks/results/judgements
```

What makes it blind, rather than a vote for the thing we hoped would win:

- **Only implementation files are shown.** Specs, plans and design documents are
  left out — they would identify the arm in the first paragraph, and the claim
  under test is about the result, not the paperwork.
- **Mentions of the tooling are redacted** from the code before it is shown, and
  a test fails if a giveaway survives into a bundle.
- **Which submission is A is drawn from a seed**, and `--both-orders` judges the
  same pair twice with the sides swapped, so a judge that favours whatever it
  reads first cancels itself out.
- **The key lives outside the directory the judge runs in**, and the verdict is
  recorded blinded. Nothing is unblinded until `tally`.

The judge picks a winner per criterion — design system fit, accessibility,
requirement coverage, maintainability, overall — so "better" is five separate
answerable questions rather than one vibe.

Two things it still cannot fix, and which belong next to any number it produces:
a judge from the same model family as the agent that wrote a submission will
flatter it, so use a different one where you can and name it either way; and a
preference is a preference, not evidence that the thing works.

### What none of this sees

It does not compile, run or look at the result. It cannot tell you whether the
feature works, whether the layout is any good, or whether the code is pleasant
to maintain. It measures whether the work stayed inside the design system and
carried the requirements — which is the claim this extension makes, and not a
claim about software quality in general.

## The cases

| Case | Design system | Kind | Why it is interesting |
|---|---|---|---|
| `date-range-filter` | shadcn/ui | feature | The system has no date range component, but its Calendar takes `mode="range"` and the composition is documented. Every wrong answer is cheaper than the right one. |
| `destructive-confirm` | Radix UI | feature | `AlertDialog` is exactly the thing. The question is only whether the run finds it instead of reaching for `Dialog` or `window.confirm`. Radix publishes no machine-readable rules, so this is also the case where the extension's own default guidelines apply. |
| `toolbar-mobile` | MUI | change | Existing code to change rather than a blank file. The documented answer collapses overflow into a `Menu`; the cheap answer is a pixel media query that hides actions the keyboard can still reach. |
| `login-error-unreadable` | shadcn/ui | bug | A pale hand-rolled error paragraph. Everything needed already exists and is already wired; the failure mode is patching the colour. |

Each case ships an `rfc.md` written the way the extension asks for one — a
problem and a capability, never a component name, which a test enforces — and a
`seed/` with the code the RFC talks about.

Cases are scored against `benchmarks/systems/`, which holds trimmed snapshots
of the three real design systems: their components with props, variants, states,
what each is for and what it should not be used for, plus tokens, named
breakpoints and, where the system has house rules, a guidelines file. These are
also valid adapter input, and a test reads each one through the shipped adapter
that names it.

### The floor

A case's seed already scores something, because existing code that uses the
system is still code that uses the system. Doing nothing at all scores:

| Case | Floor |
|---|---|
| `date-range-filter` | 0.47 |
| `destructive-confirm` | 0.40 |
| `toolbar-mobile` | 0.39 |
| `login-error-unreadable` | 0.36 |

Read every result against its floor. A run at 0.5 has barely moved. Reproduce
the floors with `--arm unaided --no-agent --score`, which sets a workspace up
and scores it without an agent ever touching it.

## Running it

```bash
pip install pytest pyyaml          # the scorer needs pyyaml
pip install specify-cli            # the speckit and extension arms need Spec Kit
```

One arm of one case, with whatever agent you want to measure:

```bash
python benchmarks/harness/runner.py \
  --case date-range-filter --arm extension \
  --agent 'claude --permission-mode acceptEdits -p "$(cat {prompt_file})"' \
  --repeat 5 --score
```

`{prompt_file}` and `{workspace}` are substituted into the command, which runs
with the workspace as its working directory. Any agent CLI works; the harness
only cares that it reads the prompt and writes files.

Then the same for `--arm speckit` and `--arm unaided`, and:

```bash
python benchmarks/harness/report.py benchmarks/results --out benchmarks/results/REPORT.md
```

Without `--agent` the runner sets the workspace up and stops, which is how you
drive a run by hand in an interactive session: open the workspace, paste the
prompt, and score it afterwards with

```bash
python benchmarks/harness/score.py --run benchmarks/results/<case>/<arm>/<run>
```

### How many runs

Agent runs vary enough that three of them prove nothing. Five per arm per case
is the point where the report stops warning you; more is better, and the report
prints the spread next to every median so a single catastrophic run is visible
rather than averaged away.

Keep one sitting's runs on one model and one version of the extension, and
record both. A comparison that mixes models measures the models.

## Publishing a result

If you run this and want the numbers quoted anywhere, publish with them:

- the agent and model, exactly (`claude-opus-5`, not "Claude")
- the extension commit and the Spec Kit version
- the number of runs per arm, and the report's spread
- what it cost, in the same place as what it won
- for a judged claim: the judge model, how many pairs, and whether both orders
  were shown
- the full `benchmarks/results/` tree minus the workspaces, so the scores can
  be recomputed

Three sentences that would be fair to write, given the runs behind them:

> On four cases across shadcn/ui, Radix UI and MUI, 10 runs per arm with
> `claude-opus-5`: the extension arm used the component the system already had
> in 38 of 40 runs, against 21 of 40 without it.

> It spent 2.4× the tokens doing so.

> A blind pairwise review by `<some other model>`, 40 pairs shown in both
> orders, preferred the extension arm's result in 71% of pairs on design system
> fit and 58% overall.

And one that would not, however tempting: *"100% of results look better"*. It
would need every pair to be judged, blind, by a judge with no stake, with the
ties counted — and a run of ties or a single loss makes it false. The apparatus
is here to find out what is actually true, which is a different and more
durable kind of useful.

`benchmarks/results/` is git-ignored except for the scores and manifests, so a
result can be committed without committing four spec-kit projects with it.

## Adding a case

1. `benchmarks/cases/<id>/rfc.md` — a problem and a capability. No component
   names: naming one has already walked the ladder for the agent, and a test
   fails if a name from the system's inventory appears in it.
2. `benchmarks/cases/<id>/seed/` — the code the RFC is about, if any.
3. `benchmarks/cases/<id>/case.yml` — what a good answer looks like:

   ```yaml
   surfaces:
     - id: period-selection
       capability: "choosing a start and an end date"
       expected_resolution: compose-components
       rationale: "why this is the lowest rung that holds"
       satisfied_by: [[Calendar, Popover]]     # any one set counts
       forbidden:
         - pattern: '<input[^>]*type="date"'   # searched in code, never in documents
           because: "drops the theme, the range semantics and the locale handling"
   guidelines:
     - id: SHADCN-FIELD-ERRORS
       evidence: ["FormMessage", "aria-describedby"]   # any one match counts
   criteria:
     - text: "An end before the start is refused"
       evidence: ['(?i)end .{0,30}before .{0,30}start']
   always_score: ["src/components/LoginForm.tsx"]      # the subject of the change
   ```

Write `satisfied_by` from the system's own inventory rather than from an
implementation you have in mind. A forbidden pattern is searched in code only,
never in documents: a design document that lists `window.confirm` as a rejected
candidate is doing its job, and reading that as a violation would punish exactly
the runs that argued their case.

Adding a design system is `benchmarks/systems/<id>/` with an `inventory.json`
and a `system.yml` saying which adapter reads it, what counts as reaching for
its tokens, and which imports are claims about the system.

## Files

```text
cases/<id>/case.yml      what a good answer looks like, per surface
cases/<id>/rfc.md        the input, written as an RFC
cases/<id>/seed/         the code the RFC talks about
systems/<id>/            inventory, guidelines, and how to score against them
harness/runner.py        builds an arm's workspace, runs an agent in it
harness/score.py         the five metrics; deterministic, arm-neutral
harness/report.py        medians, spread, pass rates, cost, and the difference
harness/judge.py         blinded pairwise judging, and the tally that unblinds it
harness/prompts/         one prompt per arm, the shared AGENTS.md brief, the judge's rubric
samples/                 hand-written workspaces that pin the scorer in tests
results/                 where runs land (git-ignored except the scores)
```
