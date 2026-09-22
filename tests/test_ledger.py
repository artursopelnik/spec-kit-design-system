"""The decision ledger: recording, recall across wordings, superseding, staleness."""

from __future__ import annotations

from pathlib import Path

import pytest

DECISION = {
    "capability": "selection of a date range",
    "aliases": ["date range picker", "from-to date selection", "period filter"],
    "resolution": "compose-components",
    "decision": "Calendar inside Popover, range state lifted to the form",
    "components": ["Calendar", "Popover"],
    "design_system_version": "1.4.2",
    "decided_in": "001-booking-filters",
}


def record(design, payload=None):
    return design.ledger_record(Path.cwd(), dict(payload or DECISION))


def lookup(design, query, version=None, threshold=0.34):
    return design.ledger_lookup(Path.cwd(), query, threshold, version)


def test_record_assigns_sequential_ids(design, project):
    assert record(design)["recorded"] == "dd-001"
    assert record(design, {**DECISION, "capability": "sorting a table"})["recorded"] == "dd-002"


def test_record_rejects_incomplete_payloads(design, project):
    with pytest.raises(SystemExit):
        design.ledger_record(Path.cwd(), {"capability": "no resolution given"})


def test_aliases_make_differently_worded_lookups_hit(design, project):
    """The whole point of the ledger: the next author phrases it differently."""
    record(design)
    result = lookup(design, "period filter for bookings")
    assert result["match_count"] == 1
    assert result["matches"][0]["id"] == "dd-001"


def test_unrelated_query_does_not_match(design, project):
    record(design)
    assert lookup(design, "uploading a profile photo")["match_count"] == 0


def test_threshold_is_respected(design, project):
    """A partial match is admitted or excluded by the threshold, not by taste.

    The query below shares one token of three with the stored phrase, so it
    scores 0.5: surfaced at the default 0.34, excluded at 0.6. It used to read
    "period filter for bookings", which the union-based score put at 0.667 —
    but that phrase *is* the stored alias plus a qualifier, so excluding it was
    the bug the threshold was standing in for.
    """
    record(design)
    assert lookup(design, "picking a delivery date", threshold=0.34)["match_count"] == 1
    assert lookup(design, "picking a delivery date", threshold=0.6)["match_count"] == 0


def test_superseded_decisions_are_hidden(design, project):
    record(design)
    record(design, {**DECISION, "decision": "DateRangePicker", "supersedes": "dd-001"})

    result = lookup(design, "date range selection")
    assert [m["id"] for m in result["matches"]] == ["dd-002"]


@pytest.mark.parametrize(
    "current,expected_stale,expected_checked",
    [
        ("1.4.2", False, True),
        ("2.0.0", True, True),
        (None, None, False),
    ],
)
def test_staleness_is_tri_state(design, project, current, expected_stale, expected_checked):
    """Unknown staleness must not read as freshness, which would make an
    unchecked decision look verified."""
    record(design)
    result = lookup(design, "date range selection", version=current)
    assert result["staleness_checked"] is expected_checked
    assert result["matches"][0]["stale"] is expected_stale


def test_hand_edited_empty_decisions_key_does_not_crash(design, project):
    path = design.ledger_path(Path.cwd())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('schema_version: "1.0"\ndecisions:\n', encoding="utf-8")
    assert design.load_ledger(Path.cwd())["decisions"] == []


def test_ledger_lives_in_specify_memory(design, project):
    """Deliberate: `memory-loader` loads this directory into agent context."""
    assert design.ledger_path(Path.cwd()).parent.name == "memory"


# --- one capability, one active decision --------------------------------------
#
# The ledger is the Recall rung's only data source. Two active decisions for one
# capability is exactly the drift the ladder exists to prevent, and it arrives by
# accident rather than by argument: the gate records a surface when it walks it,
# and a later phase records the same surface again from its own notes.


def write(design, **payload):
    """Record one decision from keyword fields, for the shape-level tests below."""
    return design.ledger_record(Path.cwd(), payload)


def test_a_second_decision_for_one_capability_is_refused(design, project):
    write(
        design,
        capability="selection of a date range",
        resolution="compose-components",
        decision="Calendar inside Popover",
    )
    with pytest.raises(SystemExit):
        write(
            design,
            capability="Selection of a Date Range",  # same phrase, different case
            resolution="compose",
            decision="Popover + Calendar",
        )
    assert len(design.load_ledger(Path.cwd())["decisions"]) == 1


def test_superseding_is_how_a_decision_is_replaced(design, project):
    first = write(
        design,
        capability="selection of a date range",
        resolution="compose-components",
        decision="Calendar inside Popover",
    )["recorded"]
    second = write(
        design,
        capability="selection of a date range",
        resolution="extend",
        decision="DateField with a range prop",
        supersedes=first,
    )
    assert second["supersedes"] == first

    decisions = {d["id"]: d for d in design.load_ledger(Path.cwd())["decisions"]}
    assert decisions[first]["status"] == "superseded"
    assert decisions[first]["superseded_by"] == second["recorded"]
    assert decisions[second["recorded"]]["status"] == "active"

    # A superseded decision does not clash, so the capability is writable again.
    write(
        design,
        capability="selection of a date range",
        resolution="create",
        decision="DateRangePicker",
        supersedes=second["recorded"],
    )


def test_a_superseded_decision_does_not_block_the_next_one(design, project):
    first = write(
        design, capability="a toast", resolution="reuse", decision="Toast",
    )["recorded"]
    write(
        design, capability="a toast", resolution="create",
        decision="Snackbar", supersedes=first,
    )
    lookup = design.ledger_lookup(Path.cwd(), "a toast", 0.3, None)
    assert lookup["match_count"] == 1, "a retired decision is still being surfaced"


# --- one spelling per rung ----------------------------------------------------


@pytest.mark.parametrize(
    "written, stored",
    [
        ("reuse", "reuse"),
        ("compose", "compose-components"),
        ("Compose (components)", "compose-components"),
        ("compose_components", "compose-components"),
        ("Compose (pattern)", "compose-pattern"),
        ("pattern", "compose-pattern"),
        ("  EXTEND  ", "extend"),
        ("create", "create"),
    ],
)
def test_a_rung_is_stored_under_one_name(design, project, written, stored):
    """A ledger is read back by string match years after the reasoning is gone.
    `compose` and `compose-components` side by side is two answers to one
    question, and the commands' own examples used to disagree."""
    write(design, capability=f"surface {written}", resolution=written, decision="X")
    entry = design.load_ledger(Path.cwd())["decisions"][-1]
    assert entry["resolution"] == stored


def test_an_unknown_rung_is_refused(design, project):
    with pytest.raises(SystemExit):
        write(design, capability="x", resolution="vibes", decision="y")
    assert design.load_ledger(Path.cwd())["decisions"] == []


@pytest.mark.parametrize("alias", ["feature", "decided_in_feature"])
def test_the_feature_field_has_one_name(design, project, alias):
    write(
        design, capability="a surface", resolution="reuse",
        decision="X", **{alias: "001-booking-filters"},
    )
    entry = design.load_ledger(Path.cwd())["decisions"][-1]
    assert entry["decided_in"] == "001-booking-filters"
    assert alias not in entry or alias == "decided_in"


# --- recall has to work for the phrasing the ladder insists on ----------------
#
# Surfaces are named by capability, never by component: "a control for picking a
# start and end date", not "DateRangePicker". Scored against the union of the two
# token sets, every word of that description the stored phrase happens not to use
# counted against the match — so the more carefully a surface was described, the
# less likely it was to recall the decision that already answered it.


DESCRIPTIVE_QUERIES = [
    "a control for picking a start and end date",
    "choosing a start and end date",
    "a way to pick a reporting period",
    "filter bookings by period",
    "date range",
]


@pytest.mark.parametrize("query", DESCRIPTIVE_QUERIES)
def test_a_capability_phrase_recalls_the_decision(design, project, query):
    record(design)
    result = lookup(design, query)
    assert result["match_count"] == 1, f"{query!r} scored below the default threshold"
    assert result["matches"][0]["id"] == "dd-001"


UNRELATED_QUERIES = [
    "sorting a table by column",
    "a transient confirmation message",
    "uploading an avatar image",
    "a navigation sidebar",
    "pagination controls",
    "a table of results",
]


@pytest.mark.parametrize("query", UNRELATED_QUERIES)
def test_a_looser_score_did_not_cost_precision(design, project, query):
    """Recall is only worth widening if the widening stays honest: a decision
    surfaced for an unrelated surface is worse than no decision, because it
    looks authoritative."""
    record(design)
    assert lookup(design, query)["match_count"] == 0


def test_an_exact_phrase_still_scores_one(design, project):
    record(design)
    assert lookup(design, DECISION["capability"])["matches"][0]["match_score"] == 1.0
    for alias in DECISION["aliases"]:
        assert lookup(design, alias)["matches"][0]["match_score"] == 1.0


# --- superseding has to retire the clash ---------------------------------------


def test_supersedes_must_name_an_active_decision(design, project):
    """A typo in `supersedes` used to pass the clash check and leave two active
    decisions for one capability."""
    write(design, capability="a toast", resolution="reuse", decision="Toast")
    with pytest.raises(SystemExit):
        write(design, capability="a toast", resolution="create", decision="Snackbar",
              supersedes="dd-999")
    assert len(design.load_ledger(Path.cwd())["decisions"]) == 1


def test_supersedes_must_retire_the_decision_it_clashes_with(design, project):
    write(design, capability="a toast", resolution="reuse", decision="Toast")
    other = write(design, capability="sorting a table", resolution="reuse",
                  decision="DataTable")["recorded"]
    with pytest.raises(SystemExit):
        write(design, capability="a toast", resolution="create", decision="Snackbar",
              supersedes=other)
    active = [d for d in design.load_ledger(Path.cwd())["decisions"]
              if d.get("status") != "superseded"]
    assert len(active) == 2


def test_a_taken_id_is_refused(design, project):
    first = write(design, capability="a toast", resolution="reuse", decision="Toast")
    with pytest.raises(SystemExit):
        write(design, id=first["recorded"], capability="sorting a table",
              resolution="reuse", decision="DataTable")

