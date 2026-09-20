# Example

A fixture design system and a throwaway project, so the workflow can be walked end to end without a real design system CLI installed.

This exists because most of the workflow lives in the command files as prose, and prose is the part a test suite cannot check. The only way to find out whether those instructions actually work is to follow them.

## Setup

```bash
./examples/setup-demo.sh /tmp/design-demo
cd /tmp/design-demo
```

That runs `specify init`, installs the extension and preset from your working copy, and wires up the Acme fixture as though it were an npm package:

```
node_modules/@acme/design-system/
├── inventory.json     # 10 components, 2 patterns, tokens, breakpoints, guidelines prose
└── guidelines.yml     # Acme's own guidelines: 4 rules plus prose
```

The config points at it the way a real multi-repo setup would, with the guidelines living inside the design system package rather than copied into the project. Because Acme publishes its own, the extension's default guidelines are never read — which you can see for yourself:

```bash
DS=.specify/extensions/design/scripts/bash/ds.sh
$DS guidelines --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['source'], [r['id'] for r in d['rules']])"
# adapter ['ACME-TARGET-SIZE', 'ACME-OVERLAY-CHOICE', ...]   — no GL-* anywhere
```

## Against a real design system

The same demo can be wired to one of the inventories the benchmarks use —
trimmed snapshots of shadcn/ui, Radix UI and MUI — together with the RFC and the
starting code of a benchmark case:

```bash
./examples/setup-demo.sh /tmp/shadcn-demo --system shadcn --case date-range-filter
./examples/setup-demo.sh /tmp/radix-demo  --system radix  --case destructive-confirm
./examples/setup-demo.sh /tmp/mui-demo    --system mui    --case toolbar-mobile
cd /tmp/shadcn-demo && /speckit.design.run rfc.md
```

Each of those cases is built around a decision the system has an answer to and
the obvious shortcut does not: shadcn has no date range component but a Calendar
that takes `mode="range"`; Radix has `AlertDialog` for exactly the confirmation
the RFC asks for; MUI documents collapsing an overflowing toolbar into a `Menu`.
Radix publishes no rules of its own, so that one is also where the extension's
default guidelines apply instead of a file the system ships.

What a good answer looks like for each is written down in
`benchmarks/cases/<id>/case.yml`, and `benchmarks/README.md` explains how a run
gets scored against it — including how to run the same RFC without the extension
and compare.

## The fixture

`acme-design-system/inventory.json` is built so the ladder has to work rather than short-circuit:

| Surface | What should happen |
|---|---|
| Confirming a cancellation | **Rung 2.** `ConfirmDialog` pattern covers it exactly, and both the prose and `ACME-OVERLAY-CHOICE` forbid Drawer here. |
| The filter row | **Rung 2.** `FilterBar` pattern exists and states its own collapse behaviour. |
| Selecting a date range | **Rung 3.** Every single-date candidate disqualifies itself in its own `avoid` text, so composition is the lowest rung that holds. |

Each component carries `usage` and `avoid`. The `avoid` text is what gives the ladder concrete rejection reasons instead of "doesn't fit":

```json
"avoid": "Exposes exactly one value. No range semantics, no cross-field validation."
```

That field is worth copying into your own inventory. It does more work than anything else in the file.

## Walking it

The short way, which is also the way a developer would actually use this:

```bash
cd /tmp/design-demo
cat > booking-filters-rfc.md <<'MD'
# RFC: Filter bookings by date range

## Problem
Users with many bookings cannot narrow the list, so they scroll.

## Proposal
A control for selecting a start and end date above the booking list, and a way to
cancel a booking from the list with a confirmation step.

## Acceptance criteria
- [ ] The list narrows to bookings within the selected range
- [ ] Cancelling asks for confirmation and cannot be triggered accidentally
MD

# then, in your agent:
/speckit.design.run booking-filters-rfc.md
```

The long way, one call at a time, which is what the run command does internally:

```bash
DS=.specify/extensions/design/scripts/bash/ds.sh

$DS gate --json | python3 -m json.tool        # prerequisites, as every command starts
$DS rfc booking-filters-rfc.md --json         # what the RFC does and does not say
$DS workflow status --json                    # where the run is, and what is next

$DS context specify --applies-to interactive,layout --query "date range selection" --json
$DS query search "confirm destructive action" --json
$DS query component DatePicker --json         # read its `avoid`
$DS query breakpoints --json                  # sm md lg xl, by name
$DS guidelines --applies-to interactive,layout --json
```

Note what `context` returns and what it does not: guidelines that apply, the candidates for the query you asked about, and `available_on_demand` listing every other call you can still make. It never dumps the inventory, and it never stops you asking for it.

Then prove the point of the ledger:

```bash
$DS ledger record - --json <<'JSON'
{"capability":"selection of a date range for filtering",
 "aliases":["date range selection","filter by period","from-to date selection"],
 "resolution":"compose-components",
 "decision":"Calendar inside Popover, range state lifted into the FilterBar",
 "design_system":"acme","design_system_version":"2.1.0","decided_in":"001-booking-filters"}
JSON

$DS ledger lookup "period filter for bookings" --json   # hits, differently worded
$DS ledger lookup "DateRangePicker" --json              # hits, by the component
```

That last lookup is the one worth watching. Someone who arrives already thinking "we need a DateRangePicker" finds the decision that says the system composes one instead.

## What this walkthrough has already caught

Running it is not ceremony. The first pass produced three fixes:

**Search ranking was meaningless.** Every candidate scored 1, because the score was a raw token-overlap count against short descriptions, so results came back in insertion order. `Button` outranked `Modal` and `ConfirmDialog` for "confirm destructive action". Scoring is now weighted per field and normalized.

**CamelCase names were one token.** `ConfirmDialog` never matched "confirm", and `DateRangePicker` never matched "date range picker". Since design system components are uniformly CamelCase, this broke component search and ledger recall at the same time. Tokenization now splits on case boundaries.

**Surface-kind classification only looked at the feature description.** A booking filter does not sound like it involves motion, so `ACME-MOTION-BUDGET` was filtered out even though the feature opens a Popover and a Modal, both of which animate. The context command now says to classify from the components you are about to use as well.

If you walk it and something reads as ambiguous, that is a finding about the command bodies, not about you. Open an issue.
