"""The Definition of Done: optional, authored, and never invented.

The DoD is the one thing here that does not come from the design system and has
no fallback. A team either wrote one down or did not, and both have to work: the
absent case is the normal case, and it stays completely silent rather than
degrading into a nag or into a default set of somebody else's rules.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def dod(design, project):
    def _dod():
        root = Path.cwd()
        return design.resolve_dod(root, design.load_config(root))

    return _dod


@pytest.fixture
def gate(design, project, capsys):
    def _gate():
        design.cmd_gate(None)
        return json.loads(capsys.readouterr().out)

    return _gate


@pytest.fixture
def write_dod(project):
    """A DoD as a team would actually write it: a markdown list, no schema."""

    def _write(body: str, name: str = ".specify/extensions/design/definition-of-done.md"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return path

    return _write


# --- the file is there --------------------------------------------------------


def test_bullets_become_items(write_dod, dod):
    write_dod(
        """\
        # Definition of Done

        Agreed in the design system guild, revisit each quarter.

        - Unit tests for every new component
        - A Storybook story per variant
        - Changelog entry
        """
    )
    resolved = dod()
    assert resolved["items"] == [
        "Unit tests for every new component",
        "A Storybook story per variant",
        "Changelog entry",
    ]
    assert resolved["source"].endswith("definition-of-done.md")
    assert resolved["error"] == ""


def test_prose_around_the_list_is_not_an_item(write_dod, dod):
    """Teams put headings, dates and rationale in this file. Only the list binds."""
    write_dod(
        """\
        # Definition of Done

        This is what we agreed in the guild.

        - Changelog entry

        Questions to @team-ds.
        """
    )
    assert dod()["items"] == ["Changelog entry"]


def test_checkbox_and_asterisk_lists_read_the_same(write_dod, dod):
    """A DoD written as a checklist is still a DoD. The marker is not the content."""
    write_dod(
        """\
        * Changelog entry
        - [ ] Design review signed off
        - [x] Visual regression snapshots updated
        """
    )
    assert dod()["items"] == [
        "Changelog entry",
        "Design review signed off",
        "Visual regression snapshots updated",
    ]


def test_a_configured_source_resolves_from_the_repo_root(write_dod, write_config, dod):
    """Same resolution as principles.source, so a shared file in a monorepo works."""
    write_dod("- Changelog entry\n", name="docs/dod.md")
    write_config({"dod": {"source": "docs/dod.md"}})
    resolved = dod()
    assert resolved["items"] == ["Changelog entry"]
    assert resolved["source"].endswith("docs/dod.md")


def test_the_gate_carries_the_items(write_dod, gate):
    write_dod("- Changelog entry\n")
    payload = gate()
    assert payload["DOD_ITEMS"] == ["Changelog entry"]
    assert payload["DOD_SOURCE"].endswith("definition-of-done.md")
    assert payload["DOD_ERROR"] == ""


# --- the file is not there ----------------------------------------------------


def test_no_file_is_silent_and_not_an_error(gate):
    """The normal case. No DoD, no complaint, nothing for a command to report."""
    payload = gate()
    assert payload["DOD_ITEMS"] == []
    assert payload["DOD_SOURCE"] == ""
    assert payload["DOD_ERROR"] == ""


def test_nothing_is_ever_supplied_as_a_default(defaults_installed, gate):
    """No DoD ships with this extension, and the principles default set is not one.

    The default principles are defensible because they cite WCAG and carry no
    values of their own. There is no equivalent authority for what a team calls
    done, so the DoD stays empty even where everything else fell back to a default.
    """
    payload = gate()
    assert payload["PRINCIPLES_SOURCE"] == "default"
    assert payload["DOD_ITEMS"] == []


def test_a_configured_path_that_does_not_resolve_is_reported(write_config, gate):
    """Silence here would leave a team believing their rules are being enforced."""
    write_config({"dod": {"source": "docs/nope.md"}})
    payload = gate()
    assert payload["DOD_ITEMS"] == []
    assert "docs/nope.md" in payload["DOD_ERROR"]


def test_the_list_written_inline_in_config_is_redirected_not_crashed(write_config, gate):
    """A natural wrong guess. The gate says where the list goes; it does not blow up."""
    write_config({"dod": ["Changelog entry"]})
    payload = gate()
    assert payload["DOD_ITEMS"] == []
    assert "definition-of-done.md" in payload["DOD_ERROR"]


def test_an_empty_file_is_not_an_error(write_dod, gate):
    """A heading written and the list still to come is a team mid-decision, not a fault."""
    write_dod("# Definition of Done\n\nTBD at the next guild.\n")
    payload = gate()
    assert payload["DOD_ITEMS"] == []
    assert payload["DOD_ERROR"] == ""


def test_no_dod_ships_in_this_repository():
    """The guard against someone helpfully adding best practices from the internet."""
    assert not list(REPO.glob("**/definition-of-done.md"))


# --- what it is not -----------------------------------------------------------


def test_the_dod_is_never_asked_of_the_design_system(design):
    """No capability, no adapter mapping, no CLI call. It is not the system's to answer."""
    assert "dod" not in design.CAPABILITIES
    for adapter in (REPO / "adapters").glob("*.yml"):
        assert "dod" not in adapter.read_text(encoding="utf-8").lower()


def test_the_dod_does_not_live_in_memory(design, project, write_dod):
    """`.specify/memory/` holds derived state that may be cleared and rebuilt.

    The ledger there can be re-derived from the design system; a DoD cannot be
    re-derived from anything, so clearing memory must not take it along.
    """
    write_dod("- Changelog entry\n")
    root = Path.cwd()
    assert design.ledger_path(root).parent.name == "memory"
    source = Path(design.resolve_dod(root, design.load_config(root))["source"])
    assert "memory" not in source.relative_to(root).parts
