"""Baseline requirements: the ones every design system wants and no spec states.

Two properties matter most and are asserted here rather than assumed:

1. No rule carries a concrete design value. Colors, breakpoint widths and spacing
   come from the design system; a rule that hardcoded one would invent exactly
   what the baseline exists to prevent.
2. Filtering never drops an unconditional rule. A `applies_to: any` rule that
   could be filtered away would be a silently missing requirement.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
DIMENSIONS = {"accessibility", "responsive", "interaction", "states", "tokens"}
KINDS = {"interactive", "layout", "text", "media", "motion", "any"}


@pytest.fixture(scope="module")
def rules():
    return yaml.safe_load((REPO / "baseline.yml").read_text(encoding="utf-8"))["rules"]


def test_every_rule_is_well_formed(rules):
    for rule in rules:
        assert re.fullmatch(r"BL-[A-Z0-9-]+", rule["id"]), rule["id"]
        assert rule["dimension"] in DIMENSIONS, rule
        assert rule["applies_to"] in KINDS, rule
        assert rule["requirement"].strip(), rule
        assert rule["verify"].strip(), rule


def test_rule_ids_are_unique(rules):
    ids = [rule["id"] for rule in rules]
    assert len(ids) == len(set(ids))


def test_every_required_dimension_has_at_least_one_rule(rules):
    """A dimension with no baseline rule would rely entirely on someone
    remembering to write a DS- requirement for it, which is the failure this
    file exists to remove."""
    assert DIMENSIONS - {rule["dimension"] for rule in rules} == set()


def test_requirements_are_normative(rules):
    for rule in rules:
        assert re.search(r"\bMUST\b", rule["requirement"]), rule["id"]


def test_no_rule_hardcodes_a_design_value(rules):
    """The baseline states obligations, never values. `320px` and `200%` are
    allowed because they come from WCAG, not from a design system."""
    from_standards = {"320px", "200%"}
    for rule in rules:
        text = f"{rule['requirement']} {rule['verify']}"
        for literal in re.findall(r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:px|rem|em|%)\b", text):
            assert literal in from_standards, f"{rule['id']} hardcodes {literal}"


def test_standards_are_cited_not_restated(rules):
    """Where a rule points at WCAG it should reference the criterion, not
    paraphrase it, so the standard stays the source of truth."""
    for rule in rules:
        standard = rule.get("standard")
        if standard:
            assert re.match(r"WCAG \d+\.\d+\.\d+", standard), rule["id"]


# --- loading and filtering ---------------------------------------------------


def test_loads_all_rules_unfiltered(designsys, project, write_config):
    (project / ".specify" / "extensions" / "designsys" / "baseline.yml").write_text(
        (REPO / "baseline.yml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = designsys.load_baseline(Path.cwd(), {})
    assert result["enabled"] is True
    assert len(result["rules"]) == len(
        yaml.safe_load((REPO / "baseline.yml").read_text())["rules"]
    )


def test_filtering_keeps_unconditional_rules(designsys, project, baseline_installed):
    """`applies_to: any` must survive every filter. A token rule dropped because
    the feature is 'just text' is a silently missing requirement."""
    unconditional = {
        rule["id"]
        for rule in designsys.load_baseline(Path.cwd(), {})["rules"]
        if rule["applies_to"] == "any"
    }
    for kinds in (["text"], ["media"], ["motion"], ["interactive", "layout"]):
        got = {rule["id"] for rule in designsys.load_baseline(Path.cwd(), {}, kinds)["rules"]}
        assert unconditional <= got, kinds


def test_filtering_excludes_irrelevant_rules(designsys, project, baseline_installed):
    text_only = designsys.load_baseline(Path.cwd(), {}, ["text"])
    ids = {rule["id"] for rule in text_only["rules"]}
    assert "BL-A11Y-KEYBOARD" not in ids  # interactive
    assert "BL-RESP-FLUID" not in ids  # layout
    assert "BL-A11Y-CONTRAST" in ids  # text
    assert text_only["skipped_as_not_applicable"] > 0


def test_disabled_rules_are_removed_but_reported(designsys, project, baseline_installed):
    config = {"baseline": {"disabled_rules": ["BL-MOTION-REDUCED"]}}
    result = designsys.load_baseline(Path.cwd(), config)
    assert "BL-MOTION-REDUCED" not in {rule["id"] for rule in result["rules"]}
    # Reported, so a switched-off rule stays visible in the spec.
    assert result["disabled"] == ["BL-MOTION-REDUCED"]


def test_baseline_can_be_turned_off(designsys, project, baseline_installed):
    result = designsys.load_baseline(Path.cwd(), {"baseline": {"enabled": False}})
    assert result["enabled"] is False and result["rules"] == []


def test_breakpoints_is_a_capability(designsys):
    """"Use our breakpoints" is unenforceable unless they can be looked up."""
    assert "breakpoints" in designsys.CAPABILITIES
