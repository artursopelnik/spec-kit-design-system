"""Guidelines: where they come from, and what is NOT done to them.

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
    return design.resolve_guidelines(root, config, adapter, kinds)


# --- the shipped default set --------------------------------------------------


@pytest.fixture(scope="module")
def defaults():
    return yaml.safe_load((REPO / "guidelines" / "default.yml").read_text(encoding="utf-8"))["rules"]


def test_the_default_set_is_small(defaults):
    """It is a fallback, not a design system. A file that grew to a hundred
    rules would be this extension inventing what it exists to ask about."""
    assert len(defaults) <= 20, f"{len(defaults)} default guidelines is too many for a fallback"


def test_every_default_is_well_formed(defaults):
    for rule in defaults:
        assert re.fullmatch(r"GL-[A-Z0-9-]+", rule["id"]), rule["id"]
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


def test_cli_guidelines_win(design, project, write_config, fake_cli, defaults_installed):
    write_config({"adapter": "fake"})
    result = resolve(design)

    assert result["source"] == "cli"
    assert result["authoritative"] is True
    assert [rule["id"] for rule in result["rules"]] == ["CLI-ONE"]
    assert "Acme speaks for itself" in result["prose"]


def test_cli_guidelines_are_not_merged_with_the_defaults(
    design, project, write_config, fake_cli, defaults_installed
):
    """The property the whole resolution order exists for."""
    write_config({"adapter": "fake"})
    result = resolve(design)
    assert not [rule for rule in result["rules"] if rule["id"].startswith("GL-")]


def test_unreachable_cli_falls_through_to_the_defaults(
    design, project, write_config, fake_cli, defaults_installed
):
    write_config({"adapter": "fake", "bin": "./not-installed"})
    result = resolve(design)

    assert result["source"] == "default"
    assert result["authoritative"] is False
    assert any(attempt["source"] == "cli" for attempt in result["attempted"])


# --- resolution: adapter-provided static data ----------------------------------


def test_a_guidelines_file_the_design_system_ships_wins_over_the_defaults(
    design, project, write_config, write_ds_guidelines, defaults_installed
):
    path = write_ds_guidelines(
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
        {"adapter": "static-json", "guidelines": {"source": str(path.relative_to(project))}}
    )
    result = resolve(design)

    assert result["source"] == "adapter"
    assert [rule["id"] for rule in result["rules"]] == ["ACME-TARGET-SIZE"]
    assert result["prose"] == "Acme is keyboard-first."


def test_guidelines_inside_the_inventory_win_over_the_defaults(
    design, project, write_config, inventory, defaults_installed
):
    """The CLI-free path: the static-json adapter maps `guidelines` at a key in
    the inventory the design system already generates."""
    import json

    data = json.loads(inventory.read_text())
    data["guidelines"] = "Destructive confirmations use Modal, never Drawer."
    inventory.write_text(json.dumps(data), encoding="utf-8")

    write_config({"adapter": "static-json"})
    result = resolve(design)

    assert result["source"] == "adapter"
    assert "never Drawer" in result["prose"]
    assert result["rules"] == []


def test_prose_only_guidelines_are_valid(
    design, project, write_config, write_ds_guidelines, defaults_installed
):
    """A design system that publishes principles as prose has still published
    guidelines. Requiring a rule schema would push teams back to restating what
    their system already says."""
    path = write_ds_guidelines({"prose": "Prefer the smallest component that carries meaning."})
    write_config({"guidelines": {"source": str(path.relative_to(project))}})
    result = resolve(design)

    assert result["source"] == "adapter"
    assert result["rules"] == []
    assert "smallest component" in result["prose"]


def test_a_bare_rule_list_is_valid_too(
    design, project, write_config, write_ds_guidelines, defaults_installed
):
    path = write_ds_guidelines(
        [{"id": "ACME-ONE", "requirement": "Everything MUST use tokens.", "verify": "Check."}]
    )
    write_config({"guidelines": {"source": str(path.relative_to(project))}})
    assert [rule["id"] for rule in resolve(design)["rules"]] == ["ACME-ONE"]


def test_a_missing_configured_file_falls_through_and_says_so(
    design, project, write_config, defaults_installed
):
    write_config({"guidelines": {"source": "nowhere/guidelines.yml"}})
    result = resolve(design)

    assert result["source"] == "default"
    assert any("not found" in attempt["reason"] for attempt in result["attempted"])


# --- resolution: the default set ------------------------------------------------


def test_defaults_apply_when_nothing_else_answers(
    design, project, write_config, defaults_installed
):
    write_config({"adapter": "static-json"})
    result = resolve(design)

    assert result["source"] == "default"
    assert result["authoritative"] is False
    assert result["rule_count"] > 0
    assert all(rule["id"].startswith("GL-") for rule in result["rules"])


def test_defaults_can_be_switched_off_entirely(
    design, project, write_config, defaults_installed
):
    """A design system with its own guidelines should not also inherit ours, and
    a team may prefer nothing to a fallback."""
    write_config({"guidelines": {"default": False}})
    result = resolve(design)

    assert result["source"] == "none"
    assert result["rules"] == []


# --- filtering and disabling ----------------------------------------------------


def test_filtering_keeps_unconditional_guidelines(
    design, project, write_config, defaults_installed
):
    unconditional = {
        rule["id"] for rule in resolve(design)["rules"] if rule["applies_to"] == "any"
    }
    for kinds in (["text"], ["media"], ["motion"], ["interactive", "layout"]):
        got = {rule["id"] for rule in resolve(design, kinds)["rules"]}
        assert unconditional <= got, kinds


def test_filtering_excludes_irrelevant_guidelines(
    design, project, write_config, defaults_installed
):
    text_only = resolve(design, ["text"])
    ids = {rule["id"] for rule in text_only["rules"]}

    assert "GL-KEYBOARD" not in ids  # interactive
    assert "GL-RESPONSIVE" not in ids  # layout
    assert "GL-CONTRAST" in ids  # text
    assert text_only["skipped_as_not_applicable"] > 0


def test_an_unclassified_guideline_is_unconditional(
    design, project, write_config, write_ds_guidelines, defaults_installed
):
    """A design system writing free-form guidelines cannot be expected to
    classify them, and a guideline dropped because it was unclassified would be
    a silently missing requirement."""
    path = write_ds_guidelines([{"id": "ACME-LOOSE", "requirement": "Something MUST hold."}])
    write_config({"guidelines": {"source": str(path.relative_to(project))}})
    assert [rule["id"] for rule in resolve(design, ["text"])["rules"]] == ["ACME-LOOSE"]


def test_disabled_guidelines_are_removed_but_reported(
    design, project, write_config, defaults_installed
):
    write_config({"guidelines": {"disabled": ["GL-REDUCED-MOTION"]}})
    result = resolve(design)

    assert "GL-REDUCED-MOTION" not in {rule["id"] for rule in result["rules"]}
    assert result["disabled"] == ["GL-REDUCED-MOTION"]


# --- the capability contract ----------------------------------------------------


def test_guidelines_and_breakpoints_are_capabilities(design):
    """"Use our breakpoints" and "follow our principles" are both unenforceable
    unless they can be looked up."""
    assert "guidelines" in design.CAPABILITIES
    assert "breakpoints" in design.CAPABILITIES
