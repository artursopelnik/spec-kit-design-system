"""Principles: where they come from, and what is NOT done to them.

The resolution order is the whole feature:

    design system CLI  ->  static data it ships  ->  the default set

The first that answers wins outright. Nothing is merged, because merging would
hold a design system to rules it never wrote, and would quietly make this
extension a second design system.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
DIMENSIONS = {"accessibility", "responsive", "interaction", "states", "tokens"}
KINDS = {"interactive", "layout", "text", "media", "motion", "any"}


def resolve(design, kinds=None):
    root = Path.cwd()
    config = design.load_config(root)
    adapter = design.load_adapter(root, config)
    return design.resolve_principles(root, config, adapter, kinds)


# --- the shipped default set --------------------------------------------------


@pytest.fixture(scope="module")
def defaults():
    return yaml.safe_load((REPO / "principles" / "default.yml").read_text(encoding="utf-8"))["principles"]


def test_the_default_set_is_small(defaults):
    """It is a fallback, not a design system. A file that grew to a hundred
    rules would be this extension inventing what it exists to ask about."""
    assert len(defaults) <= 20, f"{len(defaults)} default principles is too many for a fallback"


def test_every_default_is_well_formed(defaults):
    for rule in defaults:
        assert re.fullmatch(r"PRIN-[A-Z0-9-]+", rule["id"]), rule["id"]
        assert rule["dimension"] in DIMENSIONS, rule
        assert rule["applies_to"] in KINDS, rule
        assert rule["requirement"].strip() and rule["verify"].strip(), rule
        assert re.search(r"\bMUST\b", rule["requirement"]), rule["id"]


def test_default_ids_are_unique(defaults):
    ids = [rule["id"] for rule in defaults]
    assert len(ids) == len(set(ids))


def test_every_required_dimension_has_a_default(defaults):
    assert DIMENSIONS - {rule["dimension"] for rule in defaults} == set()


def test_no_default_hardcodes_a_design_value(defaults):
    """Defaults state obligations, never values. `320px` is allowed because it
    comes from WCAG, not from a design system."""
    from_standards = {"320px", "200%"}
    for rule in defaults:
        text = f"{rule['requirement']} {rule['verify']}"
        for literal in re.findall(r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:px|rem|em|%)\b", text):
            assert literal in from_standards, f"{rule['id']} hardcodes {literal}"


def test_standards_are_cited_not_restated(defaults):
    for rule in defaults:
        standard = rule.get("standard")
        if standard:
            assert re.match(r"WCAG \d+\.\d+\.\d+", standard), rule["id"]


def test_no_baseline_terminology_survives_anywhere():
    """One concept, one name. Two names for the same thing is how documentation
    starts contradicting the code.

    A line that is explicitly about the rename is fine — migration notes and the
    code that carries an old config key forward have to say the old word. A line
    that merely uses it is not.
    """
    migration = re.compile(r"0\.1|migrat|renam|no longer|is gone|pre-0\.2|obsolete", re.IGNORECASE)
    offenders = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".idea"}
    for path in REPO.rglob("*"):
        if not path.is_file() or set(path.parts) & skip_dirs:
            continue
        if path.suffix not in {".md", ".yml", ".yaml", ".py", ".sh", ".json"}:
            continue
        # The changelog documents the rename; the migration code and its test
        # have to name the old config key in order to carry it forward.
        if path.name in {"CHANGELOG.md", "design.py", "test_config.py", Path(__file__).name}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.search(r"\bbaseline\b|\bBL-[A-Z]", line, re.IGNORECASE) and not migration.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{number}")
    assert offenders == [], f"obsolete baseline terminology in: {offenders}"


# --- resolution: CLI -----------------------------------------------------------


def test_cli_principles_win(design, project, write_config, fake_cli, defaults_installed):
    write_config({"adapter": "fake"})
    result = resolve(design)

    assert result["principles_source"] == "cli"
    assert result["authoritative"] is True
    assert [rule["id"] for rule in result["principles"]] == ["CLI-ONE"]
    assert "Acme speaks for itself" in result["prose"]


def test_cli_principles_are_not_merged_with_the_defaults(
    design, project, write_config, fake_cli, defaults_installed
):
    """The property the whole resolution order exists for."""
    write_config({"adapter": "fake"})
    result = resolve(design)
    assert not [rule for rule in result["principles"] if rule["id"].startswith("PRIN-")]


def test_unreachable_cli_falls_through_to_the_defaults(
    design, project, write_config, fake_cli, defaults_installed
):
    write_config({"adapter": "fake", "bin": "./not-installed"})
    result = resolve(design)

    assert result["principles_source"] == "default"
    assert result["authoritative"] is False
    assert any(attempt["source"] == "cli" for attempt in result["attempted"])


# --- resolution: adapter-provided static data ----------------------------------


def test_a_principles_file_the_design_system_ships_wins_over_the_defaults(
    design, project, write_config, write_ds_principles, defaults_installed
):
    path = write_ds_principles(
        {
            "prose": "Acme is keyboard-first.",
            "rules": [
                {
                    "id": "ACME-TARGET-SIZE",
                    "dimension": "accessibility",
                    "applies_to": "interactive",
                    "requirement": "Targets MUST be at least 48x48px.",
                    "verify": "Measure hit areas.",
                }
            ],
        }
    )
    write_config(
        {"adapter": "static-json", "principles": {"source": str(path.relative_to(project))}}
    )
    result = resolve(design)

    assert result["principles_source"] == "docs"
    assert [rule["id"] for rule in result["principles"]] == ["ACME-TARGET-SIZE"]
    assert result["prose"] == "Acme is keyboard-first."


def test_principles_inside_the_inventory_win_over_the_defaults(
    design, project, write_config, inventory, defaults_installed
):
    """The CLI-free path: the static-json adapter maps `principles` at a key in
    the inventory the design system already generates."""
    import json

    data = json.loads(inventory.read_text())
    data["principles"] = "Destructive confirmations use Modal, never Drawer."
    inventory.write_text(json.dumps(data), encoding="utf-8")

    write_config({"adapter": "static-json"})
    result = resolve(design)

    assert result["principles_source"] == "docs"
    assert "never Drawer" in result["prose"]
    assert result["principles"] == []


def test_prose_only_principles_are_valid(
    design, project, write_config, write_ds_principles, defaults_installed
):
    """A design system that publishes principles as prose has still published
    principles. Requiring a rule schema would push teams back to restating what
    their system already says."""
    path = write_ds_principles({"prose": "Prefer the smallest component that carries meaning."})
    write_config({"principles": {"source": str(path.relative_to(project))}})
    result = resolve(design)

    assert result["principles_source"] == "docs"
    assert result["principles"] == []
    assert "smallest component" in result["prose"]


def test_a_bare_rule_list_is_valid_too(
    design, project, write_config, write_ds_principles, defaults_installed
):
    path = write_ds_principles(
        [{"id": "ACME-ONE", "requirement": "Everything MUST use tokens.", "verify": "Check."}]
    )
    write_config({"principles": {"source": str(path.relative_to(project))}})
    assert [rule["id"] for rule in resolve(design)["principles"]] == ["ACME-ONE"]


def test_a_missing_configured_file_falls_through_and_says_so(
    design, project, write_config, defaults_installed
):
    write_config({"principles": {"source": "nowhere/principles.yml"}})
    result = resolve(design)

    assert result["principles_source"] == "default"
    assert any("not found" in attempt["reason"] for attempt in result["attempted"])


# --- resolution: the default set ------------------------------------------------


def test_defaults_apply_when_nothing_else_answers(
    design, project, write_config, defaults_installed
):
    write_config({"adapter": "static-json"})
    result = resolve(design)

    assert result["principles_source"] == "default"
    assert result["authoritative"] is False
    assert result["principle_count"] > 0
    assert all(rule["id"].startswith("PRIN-") for rule in result["principles"])


def test_defaults_can_be_switched_off_entirely(
    design, project, write_config, defaults_installed
):
    """A design system with its own principles should not also inherit ours, and
    a team may prefer nothing to a fallback."""
    write_config({"principles": {"default": False}})
    result = resolve(design)

    assert result["principles_source"] == "unavailable"
    assert result["principles"] == []


# --- filtering and disabling ----------------------------------------------------


def test_filtering_keeps_unconditional_principles(
    design, project, write_config, defaults_installed
):
    unconditional = {
        rule["id"] for rule in resolve(design)["principles"] if rule["applies_to"] == "any"
    }
    for kinds in (["text"], ["media"], ["motion"], ["interactive", "layout"]):
        got = {rule["id"] for rule in resolve(design, kinds)["principles"]}
        assert unconditional <= got, kinds


def test_filtering_excludes_irrelevant_principles(
    design, project, write_config, defaults_installed
):
    text_only = resolve(design, ["text"])
    ids = {rule["id"] for rule in text_only["principles"]}

    assert "PRIN-KEYBOARD" not in ids  # interactive
    assert "PRIN-RESPONSIVE" not in ids  # layout
    assert "PRIN-CONTRAST" in ids  # text
    assert text_only["skipped_as_not_applicable"] > 0


def test_an_unclassified_principle_is_unconditional(
    design, project, write_config, write_ds_principles, defaults_installed
):
    """A design system writing free-form principles cannot be expected to
    classify them, and a principle dropped because it was unclassified would be
    a silently missing requirement."""
    path = write_ds_principles([{"id": "ACME-LOOSE", "requirement": "Something MUST hold."}])
    write_config({"principles": {"source": str(path.relative_to(project))}})
    assert [rule["id"] for rule in resolve(design, ["text"])["principles"]] == ["ACME-LOOSE"]


def test_disabled_principles_are_removed_but_reported(
    design, project, write_config, defaults_installed
):
    write_config({"principles": {"disabled": ["PRIN-REDUCED-MOTION"]}})
    result = resolve(design)

    assert "PRIN-REDUCED-MOTION" not in {rule["id"] for rule in result["principles"]}
    assert result["disabled"] == ["PRIN-REDUCED-MOTION"]


# --- the capability contract ----------------------------------------------------


def test_principles_and_breakpoints_are_capabilities(design):
    """"Use our breakpoints" and "follow our principles" are both unenforceable
    unless they can be looked up."""
    assert "principles" in design.CAPABILITIES
    assert "breakpoints" in design.CAPABILITIES


# --- enforceable, or a statement of intent ------------------------------------
#
# The contract this extension holds a design system to: a principle binds only
# if it is normative and something can check it. MUST/SHOULD makes it normative;
# `verify` says how anyone would know. Missing either, it is worth reading and
# not worth citing as a requirement — so it is reported, never dropped, because
# what it needs is a `verify` step, not deletion.


def test_a_principle_with_a_must_and_a_verify_is_enforceable(
    design, project, write_config, write_ds_principles
):
    path = write_ds_principles(
        {
            "principles": [
                {
                    "id": "ACME-TARGETS",
                    "requirement": "Targets MUST be at least 48x48px.",
                    "verify": "Measure the hit area at every breakpoint.",
                }
            ]
        }
    )
    write_config({"principles": {"source": str(path.relative_to(Path.cwd()))}})
    resolved = resolve(design)

    assert resolved["principles"][0]["enforceable"] is True
    assert resolved["unenforceable"] == []


@pytest.mark.parametrize(
    "principle",
    [
        {"id": "ACME-VAGUE", "requirement": "Targets MUST be large enough."},
        {"id": "ACME-VAGUE", "requirement": "Targets are usually large.", "verify": "Look."},
    ],
    ids=["no-verify", "not-normative"],
)
def test_an_unenforceable_principle_is_reported_not_dropped(
    design, project, write_config, write_ds_principles, principle
):
    path = write_ds_principles({"principles": [principle]})
    write_config({"principles": {"source": str(path.relative_to(Path.cwd()))}})
    resolved = resolve(design)

    assert resolved["principle_count"] == 1, "still in force, still returned"
    assert resolved["principles"][0]["enforceable"] is False
    assert resolved["unenforceable"] == ["ACME-VAGUE"]


def test_every_default_principle_is_enforceable(design, project, write_config, defaults_installed):
    """The set shipped here is held to its own contract: if one of these could
    not be checked, it would be advice being passed off as a requirement."""
    write_config({"principles": {"disabled": []}})
    resolved = resolve(design)

    assert resolved["principle_count"] == 14
    assert resolved["unenforceable"] == []
    assert all(entry["title"] for entry in resolved["principles"])


# --- version ------------------------------------------------------------------


def test_a_version_the_source_states_is_carried(
    design, project, write_config, write_ds_principles
):
    path = write_ds_principles({"version": "2025.4", "prose": "Keyboard first."})
    write_config({"principles": {"source": str(path.relative_to(Path.cwd()))}})
    assert resolve(design)["principles_version"] == "2025.4"


def test_an_unversioned_source_says_so_rather_than_inventing_one(
    design, project, write_config, write_ds_principles
):
    """Null is the honest answer. A made-up version would make a citation taken
    against an older revision look like one that was checked."""
    path = write_ds_principles({"prose": "Keyboard first."})
    write_config({"principles": {"source": str(path.relative_to(Path.cwd()))}})
    assert resolve(design)["principles_version"] is None
