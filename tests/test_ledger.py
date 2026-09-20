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


def record(designsys, payload=None):
    return designsys.ledger_record(Path.cwd(), dict(payload or DECISION))


def lookup(designsys, query, version=None, threshold=0.34):
    return designsys.ledger_lookup(Path.cwd(), query, threshold, {}, version)


def test_record_assigns_sequential_ids(designsys, project):
    assert record(designsys)["recorded"] == "dd-001"
    assert record(designsys, {**DECISION, "capability": "sorting a table"})["recorded"] == "dd-002"


def test_record_rejects_incomplete_payloads(designsys, project):
    with pytest.raises(SystemExit):
        designsys.ledger_record(Path.cwd(), {"capability": "no resolution given"})


def test_aliases_make_differently_worded_lookups_hit(designsys, project):
    """The whole point of the ledger: the next author phrases it differently."""
    record(designsys)
    result = lookup(designsys, "period filter for bookings")
    assert result["match_count"] == 1
    assert result["matches"][0]["id"] == "dd-001"


def test_unrelated_query_does_not_match(designsys, project):
    record(designsys)
    assert lookup(designsys, "uploading a profile photo")["match_count"] == 0


def test_threshold_is_respected(designsys, project):
    record(designsys)
    assert lookup(designsys, "period filter for bookings", threshold=0.99)["match_count"] == 0


def test_superseded_decisions_are_hidden(designsys, project):
    record(designsys)
    record(designsys, {**DECISION, "decision": "DateRangePicker", "supersedes": "dd-001"})

    result = lookup(designsys, "date range selection")
    assert [m["id"] for m in result["matches"]] == ["dd-002"]


@pytest.mark.parametrize(
    "current,expected_stale,expected_checked",
    [
        ("1.4.2", False, True),
        ("2.0.0", True, True),
        (None, None, False),
    ],
)
def test_staleness_is_tri_state(designsys, project, current, expected_stale, expected_checked):
    """Unknown staleness must not read as freshness — that would make an
    unchecked decision look verified."""
    record(designsys)
    result = lookup(designsys, "date range selection", version=current)
    assert result["staleness_checked"] is expected_checked
    assert result["matches"][0]["stale"] is expected_stale


def test_hand_edited_empty_decisions_key_does_not_crash(designsys, project):
    path = designsys.ledger_path(Path.cwd())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('schema_version: "1.0"\ndecisions:\n', encoding="utf-8")
    assert designsys.load_ledger(Path.cwd())["decisions"] == []


def test_ledger_lives_in_specify_memory(designsys, project):
    """Deliberate: `memory-loader` loads this directory into agent context."""
    assert designsys.ledger_path(Path.cwd()).parent.name == "memory"
