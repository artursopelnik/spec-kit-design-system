# Examples

A fixture design system and a throwaway project, so the workflow can be walked end to end without a real design system CLI installed.

This exists because the gate logic lives in four command files as prose, and prose is the part a test suite cannot check. The only way to find out whether those instructions actually work is to follow them.

## Setup

```bash
./examples/setup-demo.sh /tmp/designsys-demo
cd /tmp/designsys-demo
```

That runs `specify init`, installs the extension and preset from your working copy, and wires up the Acme fixture as though it were an npm package:

```
node_modules/@acme/design-system/
├── inventory.json        # 10 components, 2 patterns, tokens, breakpoints, guidelines
└── spec-kit-rules.yml    # 4 house rules, one of them overriding a baseline rule
```

The config points at it the way a real multi-repo setup would, with the rules living inside the design system package rather than copied into the project.

## The fixture

`acme-design-system/inventory.json` is built so the ladder has to work rather than short-circuit:

| Surface | What should happen |
|---|---|
| Confirming a cancellation | **Rung 2.** `ConfirmDialog` pattern covers it exactly, and both the guidelines and `ACME-OVERLAY-CHOICE` forbid Drawer here. |
| The filter row | **Rung 2.** `FilterBar` pattern exists and states its own collapse behaviour. |
| Selecting a date range | **Rung 3.** Every single-date candidate disqualifies itself in its own `avoid` text, so composition is the lowest rung that holds. |

Each component carries `usage` and `avoid`. The `avoid` text is what gives the ladder concrete rejection reasons instead of "doesn't fit":

```json
"avoid": "Exposes exactly one value. No range semantics, no cross-field validation."
```

That field is worth copying into your own inventory. It does more work than anything else in the file.

## Walking it

```bash
cd /tmp/designsys-demo
DS=.specify/extensions/designsys/scripts/bash

# Prerequisites, as every command body starts
$DS/check-design-gate.sh --json | python3 -m json.tool

# A feature to walk
.specify/scripts/bash/create-new-feature.sh --json --short-name "booking-filters" \
  "Let users filter their bookings by a date range and cancel a booking from the list"
```

Then follow `commands/speckit.designsys.sync.md` step by step, then `commands/speckit.designsys.check.md`. The commands are written to be executed by an agent, so read them as instructions and do what they say.

```bash
$DS/ds-ledger.sh --json lookup "selection of a date range"   # rung 0, empty at first
$DS/ds-query.sh   --json search "date range selection"
$DS/ds-query.sh   --json component DatePicker                # read its `avoid`
$DS/ds-query.sh   --json breakpoints                         # sm md lg xl, by name
$DS/ds-query.sh   --json guidelines                          # the system's own law
$DS/ds-rules.sh   --json --applies-to interactive,layout
```

Record the walk, then prove the point of the ledger:

```bash
$DS/ds-ledger.sh --json record - <<'JSON'
{"capability":"selection of a date range for filtering",
 "aliases":["date range selection","filter by period","from-to date selection"],
 "resolution":"compose-components",
 "decision":"Calendar inside Popover, range state lifted into the FilterBar",
 "design_system":"acme","design_system_version":"2.1.0","decided_in":"001-booking-filters"}
JSON

$DS/ds-ledger.sh --json lookup "period filter for bookings"   # hits, differently worded
$DS/ds-ledger.sh --json lookup "DateRangePicker"              # hits, by the component
```

That last lookup is the one worth watching. Someone who arrives already thinking "we need a DateRangePicker" finds the decision that says the system composes one instead.

## What this walkthrough has already caught

Running it is not ceremony. The first pass produced three fixes:

**Search ranking was meaningless.** Every candidate scored 1, because the score was a raw token-overlap count against short descriptions, so results came back in insertion order. `Button` outranked `Modal` and `ConfirmDialog` for "confirm destructive action". Scoring is now weighted per field and normalized.

**CamelCase names were one token.** `ConfirmDialog` never matched "confirm", and `DateRangePicker` never matched "date range picker". Since design system components are uniformly CamelCase, this broke component search and ledger recall at the same time. Tokenization now splits on case boundaries.

**Surface-kind classification only looked at the feature description.** A booking filter does not sound like it involves motion, so `ACME-MOTION-BUDGET` was filtered out even though the feature opens a Popover and a Modal, both of which animate. `sync` now says to classify from the components you are about to use as well.

If you walk it and something reads as ambiguous, that is a finding about the command bodies, not about you. Open an issue.
