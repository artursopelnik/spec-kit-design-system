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


@pytest.fixture
def status(design, project):
    def _status():
        root = Path.cwd()
        return design.workflow_status(root, design.load_config(root))

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

    assert seen == ["plan", "implement", "validate", "done"]


def test_a_clean_first_validation_finishes_the_run(status, feature):
    plan_and_tasks(feature)
    validation_round(feature, 1, [])
    result = status()

    assert result["open_findings"] == []
    assert result["phases"]["verify"] == "done"
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
    second = design.workflow_status(Path.cwd(), design.load_config(Path.cwd()))
    assert first == second


def test_no_state_file_is_created(status, feature, project):
    """A run-state file would be a second source of truth about work the
    artifacts already describe."""
    plan_and_tasks(feature)
    validation_round(feature, 1, [])
    status()

    files = {path.name for path in feature.iterdir()}
    assert files == {"spec.md", "plan.md", "tasks.md", "design-system.md"}
