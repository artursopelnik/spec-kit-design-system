# Architecture

The public model is one sentence: give it an RFC, it runs the Spec Kit workflow using your design system. This document is for people changing the extension, not for people using it.

## Three layers, none of them yours to configure

```text
  commands/        agent-facing prose      "what to do, in what order, what not to accept"
       │
       ▼
  scripts/         one script, all logic   "the answer to every question a command asks"
       │
       ▼
  adapters/        declarative YAML        "how to ask your design system"
```

Inside the script, one object carries the resolved project: `DesignSystem` holds
`root`, `config` and `adapter`, and caches the probe. That tuple used to be
threaded through nine functions and rebuilt at the top of every subcommand,
which is why `gate` and each `context` call each paid for their own probe —
four round-trips per phase transition where two would do.

The separation earns its keep by kind of change:

- A change to **judgement** — when a rung may be rejected, what counts as a finding, how hard to push back — is a prose edit in `commands/`. No code, no release of anything else.
- A change to **mechanism** — how principles resolve, how context is assembled, how the workflow position is derived — is one Python function with a test.
- A change to **which design system** — is a YAML file with no code in it at all.

Nothing in `adapters/` may hold rules or component knowledge; a test enforces it (`test_adapters_only_map_and_never_model`). The moment an adapter can carry design knowledge, the design system stops being the source of truth and starts having a rival.

## The script

`scripts/python/design.py`, with `scripts/bash/ds.sh` as a shim that finds an interpreter and forwards. Every subcommand emits exactly one compact JSON object on stdout, per Spec Kit's script convention, and a failure is one too: a refusal is `{"available": false, "error": ...}` on stdout, carrying the same keys the caller's guard reads (`REACHABLE`, `principles_source`), so a command body degrades deliberately instead of crashing. A refusal also exits non-zero, which matters only to a shell running under `set -e`; the JSON is the interface.

| Subcommand           | Answers                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------- |
| `gate`               | Prerequisites: feature paths, resolved config, adapter, reachability, principles source |
| `query <capability>` | Anything the design system can be asked                                                 |
| `principles`         | The principles in force, and where they came from                                       |
| `context <phase>`    | What this phase starts with, and everything it can still retrieve                       |
| `workflow status`    | Where the run is, and what comes next                                                   |
| `rfc <path>`         | The RFC, normalized: sections, open questions, whether it is UI-bearing                 |
| `ledger`             | Prior ladder decisions                                                                  |
| `scan`               | Raw values and token names in the implementation, with the token that carries a value   |
| `sync`               | What moved in the design system since the committed snapshot, and what still names it   |

`scan --strict` and `sync --strict` are the one exception to the exit-zero rule, and only on request: they emit the same JSON and then exit 1 when there is something to fail on, so a CI job can run the audit without an agent in the loop. Nothing in the command bodies passes `--strict`.

## Capability dispatch: two axes, not one function

Asking the design system splits along two independent axes, and keeping them
apart is what stopped this being one 234-line function with five jobs in it
(routing, two transports, three query strategies and envelope construction —
cyclomatic complexity 63).

```text
  run_capability          routing only: which transport, then which strategy
        │
        ├── Transport     WHERE the bytes come from, and whether we got any
        │                 FileTransport · DirectoryTransport · ProcessTransport · McpTransport
        │
        └── Strategy      WHAT they answer, once we have them
                          KeyFieldLookup · WeightedSearch · SliceOnly
```

A **transport** returns a `Fetched`, whose `status` is the three-way the
fail-closed rule needs: reached and answered, reached and explicitly told no,
or never reached. Only a transport can tell those apart. A **strategy** turns a
`Fetched` into an answer; only it knows what the payload means.

Adding a way of asking is a class plus one entry in `TRANSPORTS`. That is not
theoretical: the README promised "CLI, MCP, or files" from the start, and the
MCP transport could not be written while dispatch was one function, because
there was no seam to add it at. `DirectoryTransport` came the same way: a
design system written as a folder of Markdown spec files is read into the
document shape `static-json` reads, so every strategy works on it unchanged.
Which folder is which section (`atoms` → components, `organisms` → patterns)
is the adapter's `tiers` map; the parser knows Markdown, not any system. Like
a file, a directory knows its own shape, so a section it lacks is absent
rather than guessed at.

`WeightedSearch` living here rather than in the dispatcher matters for the same
reason the adapters may not model: ranking an inventory is knowledge about one
transport's payload, not about dispatch. It sat inline in the old function,
which meant the layer that is supposed to know nothing about any particular
design system carried a search engine for one.

Every response is built by `Answer.unavailable` or `Answer.answered`, which is
where the rule below is enforced rather than remembered. Thirteen hand-built
dicts had already drifted: six failure paths carried no `bytes`, the
file-backed paths carried no `result_path_missed`.

## Capability dispatch, and one rule

An adapter maps capability names (`search`, `component`, `tokens`, `principles`, …) onto either a subprocess invocation or a file read. Anything unmapped is reported `available: false` and the commands degrade.

The rule the whole extension rests on:

> **A failure to _ask_ is never reported as the design system _answering_ that it has nothing.**

A registry outage, a missing binary, a changed flag: all `available: false`. Only an error code the adapter explicitly declares as "not found" becomes `found: false`. Get this wrong and an outage reads as an empty design system, which pushes every decision toward Create — the exact failure this extension exists to prevent. `probe_adapter` spends one real call at gate time for the same reason: trusting the adapter file would report a full capability set for a CLI that is not installed.

## The answer cache

Every `ds.sh` call is its own process, so a run used to put the same question to the design system's CLI once per phase, per task and per validation round. `DesignSystem.ask` now remembers answers in `.specify/extensions/design/.cache/<feature>.json` (gitignored on creation), without changing what an answer means:

- **Only answers are remembered.** `available: false` is never stored, so an outage is asked again rather than replayed, and a cache cannot turn "unreachable" into "found nothing".
- **The probe is always a real call** (`fresh=True`). Reach proven from memory would prove only that the system was there earlier.
- **Nothing that acts is replayed.** `extend`, `validate` and `report_gap` carry `cacheable=False`.
- **File-backed capabilities are neither cached nor counted.** A file read costs what a cache read costs, and the file may be regenerated.
- **Scoped and keyed conservatively.** One file per feature, entries expire after `cache.ttl_minutes`, and the key covers the whole adapter, the `cwd` and the design system version (configured, or read from the installed package), so changing any of them is a different question.

The cache lives in `ask`, not in `run_capability`, which still routes and nothing else. It also counts every real round-trip and every hit, whether or not caching is on; `ds.sh cache stats` reports them, which is how the cost of a run becomes a number instead of an impression.

## Keeping what a run reads current

A design system ships, and nothing written against the previous one updates
itself. `ds.sh sync` is the routine for that, and it follows the same rules as
`scan`: it states, it does not judge.

- **A committed snapshot.** `sync record` writes the design system's component
  fingerprints, deprecation flags and token values to
  `.specify/memory/design-system-snapshot.json`, next to the ledger. `sync`
  diffs the current answers against it.
- **References, not verdicts.** Every line in `specs/*/*.md`, the
  implementation (`validation.source_globs`) and the active ledger decisions that
  names a removed, deprecated or changed component or a removed or changed token
  is listed. Additions are not: nothing written before them names them. Whether
  a changed component is still used correctly is the reader's call.
- **Fails closed.** A capability that is mapped and does not answer makes the
  whole sync unavailable. A partial snapshot would report every component it
  failed to list as removed, and a missing one must never read as "nothing
  changed". `sync record` writes nothing then.
- **The gate only compares versions.** `SYNC_SNAPSHOT_VERSION` against
  `DESIGN_SYSTEM_VERSION` costs no call; only when they differ does the check
  command run `sync`, and it never records: a new snapshot says the whole
  project has been brought up to date, and one feature cannot say that.

The version is read rather than remembered: `design_system_version` in config
wins, otherwise the installed package's own `package.json` (the package the
adapter stands for, or `design_system_package`), otherwise the range the
project declares. Empty means unchecked, never fresh.

## Principles resolution

```text
adapter maps `principles` as a command?  ──yes──▶ run it ──answers──▶ source: cli
                    │                                    │
                    no                                   no
                    ▼                                    ▼
principles.source names a file?          ──yes──▶ read it ──▶ source: docs
                    │
                    no
                    ▼
adapter maps `principles` as a file?     ──yes──▶ read it ──▶ source: docs
                    │
                    no
                    ▼
                                         principles/default.yml ──▶ source: default
```

Exactly one source is used, and `principles_source` names which: `cli`, `docs`, `default`, or `unavailable` when nothing answered and the fallback is switched off — the case a gate has to fail closed on rather than pass on an empty set. `normalize_principles` accepts prose, a list, or a document with both, under whatever key the system publishes its list (`principles`, `rules`, `items`), because there is no standard for stating a design rule in a checkable form and requiring one would mean asking teams to restate what their design system already says.

Each principle comes back with `enforceable`: it states a MUST or SHOULD **and** carries a `verify` step. Anything else is returned, listed under `unenforceable`, and never dropped — a principle nobody can check is not one to hide, it is one to write a `verify` for, and only what a reader can see gets fixed.

## Focused context

`build_context(phase)` returns what a phase starts with, plus `available_on_demand` and `retrieval` — every capability the design system can still answer, with the call that gets it.

| Phase     | Starts with                                             |
| --------- | ------------------------------------------------------- |
| clarify   | RFC, principles                                         |
| specify   | RFC, principles, candidates for what was searched       |
| plan      | spec, principles, named components, tokens, breakpoints |
| implement | plan, named components, tokens                          |
| validate  | spec, principles, named components                      |
| verify    | spec, principles                                        |

Each response carries `bytes`, and the context carries a `sizes` block per section plus a total, so "focused" is a measured claim rather than an assumed one. Sizes are reported, never enforced: nothing is dropped from a payload on the way through. Where an answer is bulkier than it needs to be — `breakpoints` mapped onto the token command without a slice is the usual case — the context says so in `notes` and the fix belongs in the adapter, which is the only layer that knows the shape of that system's response.

The property to preserve when changing this: **focused, never restricted**. Two tests hold the line — one asserts an unasked-for component does not arrive, the other asserts the same component is retrievable a call later. A change that makes the first pass by making the second fail has broken the feature, not improved it.

## Workflow position without a state file

`workflow_status` derives everything from artifacts the work already produces:

| Signal              | Read from                                               |
| ------------------- | ------------------------------------------------------- |
| clarified           | `spec.md` carries no `[NEEDS CLARIFICATION]`            |
| specified / planned | `spec.md`, `plan.md` exist                              |
| implemented         | `tasks.md` has no unticked task                         |
| validated           | `design-system.md` has `## Validation round N` sections |
| open findings       | unticked `- [ ] DS-F-nnn` entries                       |
| verified            | `design-system.md` has a `## Verification` section      |

So an interrupted run resumes by reading, and recorded state cannot drift from real state. The cost is a format contract with the validate command: the round heading and the finding checkbox are load-bearing, and that is stated in the command body where someone editing it will see it.

The loop terminates on two conditions: a round with no findings at all ends it, and `max_validation_rounds` (2 by default) stops it. A round whose findings were ticked off does not count as clean — that would let the fixing pass sign off its own fixes — so when the last allowed round's findings have been ticked, `next` is `stop`, not another `validate`.

What a script can settle never takes a round. `ds.sh scan` reports raw values in the implementation, token names the contract or spec asks for that the design system lacks, and contract tokens written nowhere in the code. The validate pass turns them into findings; its own review runs once in full, and a fix round checks only the fixes, what they touched, the scan and the tests.

The clean round also writes the `## Verification` section, recording that the whole change was checked back against the RFC; the run is complete only once it exists. If a clean round omits it, `next` becomes `verify`, so the gap is visible rather than skipped. Every phase here is derived from an artifact, so a phase with no artifact is one the run skips — which is what happened while `verify` was derived from the validate row rather than from anything it wrote.

## What is mechanism, and what is judgement

Worth being exact about, because "a gate that blocks" reads as a mechanical
guarantee and only part of it is one.

Mechanical, in the script, and not negotiable by an agent:

- reachability. `probe_adapter` spends a real call, and an unreachable design
  system comes back with an empty `CAPABILITIES` and `REACHABLE: false`. A
  refusal — bad config, missing adapter, an unexpected error — carries the same
  markers, so the guard fires on the failure nobody anticipated too.
- principles resolution, and `principles_source: unavailable` when nothing
  answered and the fallback is off.
- workflow position, the round count and the bound on it.
- the ledger: one active decision per capability, one spelling per rung.

Judgement, in the command bodies, honoured because the agent is told to:

- `gate.enforce` — whether a failed gate errors or warns.
- `gate.min_candidates_considered` — how thin a search may be before a surface
  may land on Extend or Create.
- `ledger.enabled` — whether lookup and recording happen at all.
- `validation.forbid_raw_values` — whether a raw value becomes a finding.

These four are handed over in `CONFIG` and decide nothing in the script during
a run (`scan --strict`, a CI job's own choice, counts raw values as violations
only when `forbid_raw_values` is on). That
is the layering working as intended: judgement belongs in prose, where it can
be argued with. It is also the reason `tests/test_config.py` pins them — a
setting the script ignores and no command body mentions is enforced by nothing,
while still sitting in the config file looking as though it works.

## Where Spec Kit does the work

The phases are wired as Spec Kit hooks in `extension.yml`, not inside the run command:

```text
before_plan     → /speckit.design.check      (blocking)
after_implement → /speckit.design.validate
```

There is no `after_specify` hook. The design system is consulted once before planning, by the gate: searching for a surface, deciding on it and writing its requirement into the spec happen in one pass, rather than a context pass that searched every surface and a gate that searched it again.

`/speckit.design.run` drives Spec Kit's own commands and lets the hooks fire. It is the autonomous path over the same rails, not a second implementation of them, which is why working phase by phase by hand still gets every guarantee.
