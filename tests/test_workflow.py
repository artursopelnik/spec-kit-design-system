"""The autonomous workflow: does it know where it is, and does it terminate?

The run has no state file. Progress is read back out of the artifacts the work
already produces — spec, plan, tasks, design document — which is what makes an
interrupted run resumable and stops the recorded state from drifting away from
the actual state.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def status(design, project):
    def _status():
        return design.workflow_status(design.DesignSystem.resolve())

    return _status


def write(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text), encoding="utf-8")


def plan_and_tasks(feature, done: bool = True) -> None:
    write(feature / "plan.md", "# Plan\n\nBuild the filter row from FilterBar.\n")
    mark = "x" if done else " "
    write(feature / "tasks.md", f"# Tasks\n\n- [{mark}] T001 Build it\n- [{mark}] T002 Wire it up\n")


def validation_round(feature, number: int, findings: list[str], fixed: list[str] = ()) -> None:
    lines = [f"## Validation round {number} — 2026-05-14", ""]
    lines += [f"- [ ] {entry}" for entry in findings]
    lines += [f"- [x] {entry}" for entry in fixed]
    existing = (feature / "design-system.md").read_text() if (
        feature / "design-system.md"
    ).is_file() else "# Design System\n\n"
    (feature / "design-system.md").write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")


def verification(feature, verdict: str = "Meets its design requirements.") -> None:
    """What the verify pass leaves behind. `workflow status` derives the phase
    from it, so a run is not complete until it exists."""
    doc = feature / "design-system.md"
    existing = doc.read_text() if doc.is_file() else "# Design System\n\n"
    doc.write_text(
        f"{existing}\n## Verification — 2026-05-14\n\n{verdict}\n", encoding="utf-8"
    )


# --- progression ---------------------------------------------------------------


def test_without_a_feature_the_run_starts_at_specify(status):
    result = status()
    assert result["next"] == "specify"
    assert result["complete"] is False


def test_an_unclarified_spec_blocks_before_specifying_further(status, feature):
    write(
        feature / "spec.md",
        """\
        # Spec

        [NEEDS CLARIFICATION: Drawer or Modal for the destructive confirmation?]
        """,
    )
    result = status()
    assert result["phases"]["clarify"] == "blocked"
    assert result["next"] == "clarify"


def test_the_phases_advance_without_being_driven_by_hand(status, feature):
    """One RFC, one run: each artifact appearing moves `next` along on its own,
    which is what lets the run command follow the workflow rather than the user
    calling each phase."""
    seen = []

    seen.append(status()["next"])          # spec exists (the feature fixture writes one)
    plan_and_tasks(feature, done=False)
    seen.append(status()["next"])
    plan_and_tasks(feature, done=True)
    seen.append(status()["next"])
    validation_round(feature, 1, [])
    seen.append(status()["next"])
    verification(feature)
    seen.append(status()["next"])

    assert seen == ["plan", "implement", "validate", "verify", "done"]


def test_a_clean_validation_is_not_the_end_of_the_run(status, feature):
    """Validation says the implementation matches what was decided. Verify asks
    the different question — whether the RFC actually got what it asked for —
    so a clean round hands over to it rather than finishing."""
    plan_and_tasks(feature)
    validation_round(feature, 1, [])
    result = status()

    assert result["open_findings"] == []
    assert result["phases"]["validate"] == "done"
    assert result["phases"]["verify"] == "pending"
    assert result["next"] == "verify"
    assert result["complete"] is False


def test_the_run_finishes_once_verification_is_recorded(status, feature):
    plan_and_tasks(feature)
    validation_round(feature, 1, [])
    verification(feature)
    result = status()

    assert result["open_findings"] == []
    assert result["phases"]["verify"] == "done"
    assert result["verified"] is True
    assert result["complete"] is True


# --- the validate -> fix -> validate loop ---------------------------------------


def test_findings_send_the_run_back_to_fixing(status, feature):
    plan_and_tasks(feature)
    validation_round(feature, 1, ["DS-F-001 **violation** · Filter row · raw padding"])
    result = status()

    assert result["next"] == "fix"
    assert result["open_findings"] == ["DS-F-001"]
    assert result["complete"] is False


def test_fixing_then_revalidating_reaches_done(status, feature):
    plan_and_tasks(feature)
    validation_round(feature, 1, ["DS-F-001 **violation** · Filter row · raw padding"])
    assert status()["next"] == "fix"

    # The fix pass ticks the finding off, then validation appends a clean round.
    doc = feature / "design-system.md"
    doc.write_text(doc.read_text().replace("- [ ] DS-F-001", "- [x] DS-F-001"), encoding="utf-8")
    assert status()["next"] == "validate"

    validation_round(feature, 2, [])
    result = status()
    assert result["validation_rounds_used"] == 2
    assert result["closed_findings"] == ["DS-F-001"]
    # Clean, but the whole change has not been checked against the RFC yet.
    assert result["next"] == "verify"
    assert result["complete"] is False

    verification(feature)
    result = status()
    assert result["next"] == "done"
    assert result["complete"] is True


def test_the_loop_is_bounded(status, feature):
    """Three rounds that fail the same way is information; a fourth is noise.
    The run must stop and hand back rather than iterate forever."""
    plan_and_tasks(feature)
    for round_number in range(1, 4):
        validation_round(feature, round_number, [f"DS-F-00{round_number} **violation** · still wrong"])

    result = status()
    assert result["validation_rounds_used"] == 3
    assert result["may_validate_again"] is False
    assert result["next"] == "stop"
    assert "human" in result["reason"]
    assert result["complete"] is False


def test_the_bound_is_configurable_for_the_projects_that_need_it(
    status, feature, write_config
):
    write_config({"workflow": {"max_validation_rounds": 1}})
    plan_and_tasks(feature)
    validation_round(feature, 1, ["DS-F-001 **violation** · still wrong"])

    result = status()
    assert result["max_validation_rounds"] == 1
    assert result["next"] == "stop"


def test_progress_survives_an_interrupted_run(status, feature, design):
    """Nothing is remembered in the process, so a fresh invocation reads the
    same position off disk."""
    plan_and_tasks(feature)
    validation_round(feature, 1, ["DS-F-001 **violation** · raw padding"])

    first = status()
    second = design.workflow_status(design.DesignSystem.resolve())
    assert first == second


def test_no_state_file_is_created(status, feature, project):
    """A run-state file would be a second source of truth about work the
    artifacts already describe."""
    plan_and_tasks(feature)
    validation_round(feature, 1, [])
    status()

    files = {path.name for path in feature.iterdir()}
    assert files == {"spec.md", "plan.md", "tasks.md", "design-system.md"}


# --- verify is a phase, not a restatement of the one before it ----------------
#
# Position is derived from artifacts, so a phase needs an artifact. `verify` was
# derived from `last_round_clean and implemented` — the same condition as
# `validate` — which meant it reported itself done the moment validation passed,
# and `next` went straight from a clean round to `done`. A run following `next`,
# as the run command tells it to, skipped the pass entirely.


def test_a_clean_round_asks_for_verification_before_done(design, project, feature):
    (feature / "spec.md").write_text("# Spec", encoding="utf-8")
    (feature / "plan.md").write_text("# Plan", encoding="utf-8")
    (feature / "tasks.md").write_text("- [x] T001\n", encoding="utf-8")
    (feature / "design-system.md").write_text(
        "## Validation round 1\n\nNo findings.\n", encoding="utf-8"
    )

    status = design.workflow_status(design.DesignSystem.resolve())
    assert status["next"] == "verify", status["reason"]
    assert status["complete"] is False
    assert status["verified"] is False
    assert status["phases"]["verify"] == "pending"
    assert status["phases"]["validate"] == "done"


def test_a_recorded_verification_completes_the_run(design, project, feature):
    (feature / "spec.md").write_text("# Spec", encoding="utf-8")
    (feature / "plan.md").write_text("# Plan", encoding="utf-8")
    (feature / "tasks.md").write_text("- [x] T001\n", encoding="utf-8")
    (feature / "design-system.md").write_text(
        "## Validation round 1\n\nNo findings.\n\n"
        "## Verification — 2026-05-14\n\nRFC criteria: 3 of 3 met.\n",
        encoding="utf-8",
    )

    status = design.workflow_status(design.DesignSystem.resolve())
    assert status["next"] == "done"
    assert status["complete"] is True
    assert status["verified"] is True
    assert status["phases"]["verify"] == "done"


def test_verification_does_not_skip_an_open_finding(design, project, feature):
    """A verification heading is not a way past the fix loop."""
    (feature / "spec.md").write_text("# Spec", encoding="utf-8")
    (feature / "plan.md").write_text("# Plan", encoding="utf-8")
    (feature / "tasks.md").write_text("- [x] T001\n", encoding="utf-8")
    (feature / "design-system.md").write_text(
        "## Validation round 1\n\n- [ ] DS-F-001 **violation** · raw px\n\n"
        "## Verification\n\nPremature.\n",
        encoding="utf-8",
    )

    status = design.workflow_status(design.DesignSystem.resolve())
    assert status["next"] == "fix", status["reason"]
    assert status["complete"] is False


def test_the_run_command_states_the_verification_format():
    """The heading is a contract between the command body and `workflow_status`,
    the same as the validation round heading. If the body stops teaching it, the
    phase silently stops being reachable."""
    body = (REPO / "commands" / "speckit.design.run.md").read_text(encoding="utf-8")
    assert "## Verification" in body
    assert "design-system.md" in body


# --- the format contract, against what a model actually writes ----------------
#
# Position is derived by regex from a markdown file that a language model
# writes. The existing tests feed it the exact shape the command body teaches,
# which proves the parser reads its own examples. The risk is the other case: a
# model that formats reasonably but not identically, where a missed heading
# does not error -- it silently stops the fix loop terminating.


REALISTIC_ROUND_HEADINGS = [
    "## Validation round 1 — 2026-05-14",      # as taught
    "## Validation round 1 - 2026-05-14",      # hyphen, not em dash
    "## Validation round 1",                   # no date
    "## Validation Round 1",                   # title case
    "### Validation round 1",                  # nested a level deeper
    "##  Validation round 1  ",                # loose whitespace
    "## Validation round 10 — 2026-05-14",     # two digits
]


@pytest.mark.parametrize("heading", REALISTIC_ROUND_HEADINGS)
def test_a_round_heading_is_recognised(design, heading):
    found = design.VALIDATION_ROUND.findall(heading)
    assert found, f"not recognised as a round: {heading!r}"
    assert found[0].isdigit()


REALISTIC_FINDING_LINES = [
    "- [ ] DS-F-001 **violation** · Date range · bespoke input",
    "- [ ] DS-F-001 violation: bespoke input",
    "  - [ ] DS-F-012 nested under a surface heading",
    "-   [ ] DS-F-003 extra spaces after the dash",
]


@pytest.mark.parametrize("line", REALISTIC_FINDING_LINES)
def test_an_open_finding_is_recognised(design, line):
    assert design.FINDING_OPEN.findall(line), f"open finding missed: {line!r}"


@pytest.mark.parametrize(
    "line",
    [
        "- [x] DS-F-001 fixed by using the system's focus token",
        "- [X] DS-F-002 fixed",
        "  - [x] DS-F-003 fixed",
    ],
)
def test_a_closed_finding_is_recognised(design, line):
    assert design.FINDING_CLOSED.findall(line), f"closed finding missed: {line!r}"
    assert not design.FINDING_OPEN.findall(line), "a fixed finding still reads as open"


@pytest.mark.parametrize(
    "heading",
    [
        "## Verification — 2026-05-14",
        "## Verification",
        "### Verification of the whole change",
        "## verification",
    ],
)
def test_a_verification_heading_is_recognised(design, heading):
    assert design.VERIFICATION.search(heading), f"verification missed: {heading!r}"


def test_a_finding_inside_prose_does_not_count_as_open(design):
    """`DS-F-001` mentioned in a sentence is a reference, not a finding. Only a
    checkbox at the start of a list item opens one."""
    prose = "Round 2 confirmed that DS-F-001 no longer reproduces.\n"
    assert not design.FINDING_OPEN.findall(prose)


def test_the_loop_terminates_on_a_realistically_formatted_document(
    design, project, feature
):
    """End to end on markdown written the way a model writes it rather than the
    way the example does: hyphen instead of em dash, a surface heading between
    the rounds, findings indented under it."""
    (feature / "plan.md").write_text("# Plan", encoding="utf-8")
    (feature / "tasks.md").write_text("- [x] T001\n", encoding="utf-8")
    (feature / "design-system.md").write_text(
        "# Design System\n\n"
        "## Surface: a control for picking a date range\n\n"
        "**Resolution**: Compose (components)\n\n"
        "### Validation round 1 - 2026-05-14\n\n"
        "  - [x] DS-F-001 raw padding, fixed with space.3\n\n"
        "### Validation round 2 - 2026-05-15\n\n"
        "No findings.\n\n"
        "## Verification\n\nRFC criteria: 3 of 3 met.\n",
        encoding="utf-8",
    )

    status = design.workflow_status(design.DesignSystem.resolve())
    assert status["validation_rounds_used"] == 2
    assert status["closed_findings"] == ["DS-F-001"]
    assert status["open_findings"] == []
    assert status["next"] == "done", status["reason"]
