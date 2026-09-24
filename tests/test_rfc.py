"""The RFC is the only input abstraction.

Where it came from — a file, a GitHub issue, a Jira ticket, an MCP resource —
is deliberately not this extension's business. Something else fetches it; this
reads it and finds out what it does not say.
"""

from __future__ import annotations

import textwrap


RFC = textwrap.dedent(
    """\
    # RFC: Filter bookings by date range

    ## Problem
    Users with many bookings cannot narrow the list, so they scroll.

    ## Proposal
    A control for selecting a start and end date above the booking list, plus a
    way to cancel a booking from the list with a confirmation step.

    ## Out of scope
    Saved filters.

    ## Acceptance criteria
    - [ ] The list narrows to bookings within the selected range
    - [ ] Cancelling asks for confirmation

    ## Open questions
    - Should the range default to the current month?
    """
)


def test_the_sections_the_workflow_reads_are_found(design):
    rfc = design.parse_rfc(RFC, origin="docs/rfc.md")

    assert rfc["title"] == "RFC: Filter bookings by date range"
    assert "cannot narrow the list" in rfc["sections"]["problem"]
    assert "Saved filters" in rfc["sections"]["out_of_scope"]
    assert "narrows to bookings" in rfc["sections"]["acceptance"]
    assert rfc["origin"] == "docs/rfc.md"


def test_open_questions_become_the_clarify_agenda(design):
    rfc = design.parse_rfc(RFC)
    assert any("current month" in question for question in rfc["open_questions"])


def test_a_ui_bearing_rfc_is_recognized(design):
    assert design.parse_rfc(RFC)["ui_bearing"] is True


def test_a_backend_rfc_is_not(design):
    text = "# RFC: Nightly reconciliation\n\nAggregate ledger entries into a report row.\n"
    assert design.parse_rfc(text)["ui_bearing"] is False


def test_headings_the_author_phrased_differently_still_match(design):
    text = textwrap.dedent(
        """\
        # Add a bulk export

        ## Background
        Support exports one row at a time.

        ## Solution
        A button that exports the current selection.

        ## Done when
        - [ ] A selection of any size exports in one action
        """
    )
    rfc = design.parse_rfc(text)
    assert "one row at a time" in rfc["sections"]["problem"]
    assert "exports the current selection" in rfc["sections"]["proposal"]
    assert "one action" in rfc["sections"]["acceptance"]


def test_a_thin_rfc_is_accepted_and_flagged(design):
    """A one-line RFC is a legitimate starting point. The clarify phase exists
    for exactly this, so it is warned about rather than rejected."""
    rfc = design.parse_rfc("Let users filter bookings by date range.")

    assert rfc["title"] == "Let users filter bookings by date range."
    assert rfc["warnings"]
    assert any("acceptance" in warning for warning in rfc["warnings"])


def test_clarification_markers_are_collected_wherever_they_appear(design):
    text = "# RFC\n\nShow a list.\n\n[NEEDS CLARIFICATION: paginated or infinite scroll?]\n"
    assert any("paginated" in question for question in design.parse_rfc(text)["open_questions"])


def test_a_short_ui_rfc_is_still_recognized(design):
    """RFCs are short. A three-line one about a filter control must not read as
    backend work, because that would skip the design system entirely."""
    text = "# RFC: Filter bookings\n\n## Proposal\nA date range control above the booking list.\n"
    assert design.parse_rfc(text)["ui_bearing"] is True


def test_a_short_backend_rfc_is_still_not(design):
    text = "# RFC: Retention\n\n## Proposal\nPurge ledger entries older than seven years.\n"
    assert design.parse_rfc(text)["ui_bearing"] is False


# --- the design brief ----------------------------------------------------------


import pytest as _pytest


@_pytest.mark.parametrize(
    "heading",
    ["## Design guidelines", "## Design-Vorgaben", "## Gestaltung", "## Look & Feel", "## Styleguide"],
)
def test_a_pasted_design_brief_is_its_own_section(design, heading):
    """Teams paste their guidelines at the end of the RFC under whatever heading
    their wiki uses. The spec summarises *what*, so this section is how the brief
    reaches the gate word for word."""
    rfc = design.parse_rfc(
        "# RFC: Footer signup\n\n## Problem\nNo way to subscribe.\n\n"
        f"{heading}\nDunkler Hintergrund `color.surface.inverse`, Abstand `space.6`.\n"
    )
    assert "color.surface.inverse" in rfc["sections"]["design"]
    assert "space.6" in rfc["sections"]["design"]


def test_an_rfc_without_a_brief_is_fine(design):
    rfc = design.parse_rfc("# RFC: Footer signup\n\n## Problem\nNo way to subscribe.\n")
    assert "design" not in rfc["sections"]
    assert not any("design" in warning for warning in rfc["warnings"])
