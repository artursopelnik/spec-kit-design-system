"""Focused context, and the line it must never cross.

Two properties, and the second is the one worth guarding:

1. A phase is not handed the whole design system. Less noise, fewer tokens,
   less for the agent to pattern-match against by accident.
2. A phase can still reach everything. Focused context is about what arrives
   first, never about what is reachable. A context that hid information would
   make the agent confidently wrong, which is worse than slow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def context(design, phase, **kwargs):
    return design.build_context(design.DesignSystem.resolve(), phase, **kwargs)


def test_implement_does_not_receive_the_whole_design_system(
    design, project, write_config, inventory, defaults_installed
):
    write_config({"adapter": "static-json"})
    payload = context(design, "implement")

    assert payload["components"] == {}
    # The inventory has components; none of them arrived unasked for.
    blob = json.dumps(payload)
    assert "Popover" not in blob
    assert "Month grid for date display" not in blob


def test_implement_receives_exactly_the_components_it_named(
    design, project, write_config, inventory, defaults_installed
):
    write_config({"adapter": "static-json"})
    payload = context(design, "implement", components=["Calendar"])

    assert payload["components"]["Calendar"]["description"] == "Month grid for date display"
    assert "Popover" not in json.dumps(payload["components"])


def test_a_named_pattern_resolves_too(
    design, project, write_config, inventory, defaults_installed
):
    """Surfaces are named by capability, and what covers one is as often a
    pattern as a component."""
    write_config({"adapter": "static-json"})
    payload = context(design, "implement", components=["FilterBar"])
    assert payload["components"]["FilterBar"]["name"] == "FilterBar"


def test_everything_else_stays_one_call_away(
    design, project, write_config, inventory, defaults_installed
):
    """The critical property: nothing is withheld, and the agent is told how to
    ask. A focused context that did not say this would read as a limit."""
    write_config({"adapter": "static-json"})
    payload = context(design, "implement")

    assert "component" in payload["available_on_demand"]
    assert "search" in payload["available_on_demand"]
    assert payload["retrieval"]["component"] == "ds.sh query component [args]"
    assert any("query component" in note for note in payload["notes"])


def test_what_was_not_handed_over_can_still_be_retrieved(
    design, project, write_config, inventory, defaults_installed
):
    """Follow the advertised route and the withheld component arrives."""
    write_config({"adapter": "static-json"})
    payload = context(design, "implement")
    assert "Popover" not in json.dumps(payload)

    root = Path.cwd()
    later = design.DesignSystem.resolve().ask("component", name="Popover")

    assert later["found"] is True
    assert later["data"]["name"] == "Popover"


def test_clarify_is_the_leanest_phase(
    design, project, write_config, inventory, defaults_installed
):
    """Clarifying an RFC needs the principles and the RFC. Pulling components in
    would be guessing at an answer the ladder has not reached yet."""
    payload = context(design, "clarify")

    assert payload["components"] == {}
    assert payload["tokens"] is None
    assert payload["candidates"] is None
    assert payload["principles"]["principle_count"] > 0


def test_plan_gets_the_vocabulary_it_must_write_with(
    design, project, write_config, inventory, defaults_installed
):
    """Token and breakpoint names are the one thing an agent reliably invents
    when it does not have them, so planning gets them up front."""
    write_config({"adapter": "static-json"})
    payload = context(design, "plan", components=["Calendar"])

    assert payload["tokens"] == {"space": {"3": "12px"}}
    assert payload["breakpoints"] == {"sm": "640px", "md": "768px"}


def test_candidates_arrive_only_when_something_is_searched_for(
    design, project, write_config, inventory, defaults_installed
):
    write_config({"adapter": "static-json"})
    assert context(design, "specify")["candidates"] is None

    hits = context(design, "specify", query="floating container")["candidates"]
    assert [hit["name"] for hit in hits][0] == "Popover"


def test_principles_are_filtered_to_the_surfaces_in_play(
    design, project, write_config, inventory, defaults_installed
):
    write_config({"adapter": "static-json"})
    every = context(design, "validate")["principles"]["principle_count"]
    text = context(design, "validate", kinds=["text"])["principles"]["principle_count"]
    assert text < every


def test_an_unreachable_design_system_is_reported_not_faked(
    design, project, write_config, defaults_installed
):
    write_config({"adapter": "example", "bin": "./not-installed"})
    payload = context(design, "implement", components=["Button"])

    assert payload["reachable"] is False
    assert payload["available_on_demand"] == []
    assert payload["components"] == {}
    assert payload["notes"]


def test_an_unknown_phase_is_an_error(design, project, write_config, inventory):
    try:
        context(design, "refactor")
    except SystemExit as exit_:
        assert exit_.code == 1
    else:
        raise AssertionError("an unknown phase must not silently produce empty context")


# --- what the context costs ---------------------------------------------------
#
# "Focused" is a claim about size, and an unmeasured claim drifts. A capability
# that quietly answers with 50 KB looks exactly like one that answers with 50
# until somebody counts, so the context counts.


def test_the_context_says_what_each_section_costs(
    design, project, write_config, inventory, defaults_installed
):
    write_config({"adapter": "static-json"})
    payload = context(design, "plan", components=["Calendar"])

    sizes = payload["sizes"]
    assert sizes["tokens"] == len(json.dumps(payload["tokens"], separators=(",", ":")).encode())
    assert sizes["components"] > 0
    assert sizes["total"] >= sum(
        sizes[name] for name in ("principles", "components", "tokens", "breakpoints")
    )


def test_an_unnarrowed_shared_payload_is_called_out(
    design, project, write_config, fake_cli, defaults_installed
):
    """The adapter-quality failure this is aimed at: `breakpoints` mapped onto
    the token command with a slice that matches nothing. The capability answers,
    so nothing looks broken - the whole token payload just arrives twice, every
    plan, forever. Say so where the person tuning the adapter will read it."""
    write_config(
        {
            "adapter": "fake",
            "capabilities": {"breakpoints": {"args": ["tokens"], "result_paths": ["data.nope"]}},
        }
    )
    payload = context(design, "plan")

    assert any(
        note.startswith("breakpoints:") and "result_path" in note for note in payload["notes"]
    )


def test_a_narrowed_capability_draws_no_complaint(
    design, project, write_config, fake_cli, defaults_installed
):
    """The fixture adapter maps breakpoints onto the token command correctly, so
    the note must not fire on a mapping that is doing its job."""
    write_config({"adapter": "fake"})
    payload = context(design, "plan")

    assert payload["breakpoints"] == {"sm": "640px", "md": "768px", "lg": "1024px"}
    assert not any(note.startswith("breakpoints:") for note in payload["notes"])


def test_a_large_answer_is_reported_but_never_trimmed(design):
    """Reported, not filtered: the cost is stated and the payload arrives whole.
    A context that silently dropped half a token set would make the agent
    confidently wrong, which is the one outcome worse than an expensive run."""
    big = {"tokens": {str(n): "x" * 64 for n in range(400)}}
    note = design.cost_note("tokens", {"bytes": design.payload_bytes(big), "data": big})

    assert note and "bytes" in note
    assert design.cost_note("breakpoints", {"bytes": 120}) is None


def test_breakpoints_answering_with_the_token_set_is_named_as_such(
    design, project, write_config, fake_cli, defaults_installed
):
    """Mapped onto the token command and never narrowed, `breakpoints` answers
    with everything `tokens` just answered with. Nothing fails - the breakpoint
    names really are in there - so the only way this surfaces is if the context
    says it."""
    write_config(
        {
            "adapter": "fake",
            "capabilities": {"breakpoints": {"args": ["tokens"], "result_path": "data",
                                             "result_paths": []}},
        }
    )
    payload = context(design, "plan")

    assert payload["breakpoints"] == payload["tokens"]
    assert any("same payload as tokens" in note for note in payload["notes"])


# --- the contract has to describe the object it is attached to ----------------


@pytest.mark.parametrize("phase", ["clarify", "specify", "plan", "implement", "validate", "verify"])
def test_includes_names_only_keys_that_are_there(
    design, project, write_config, inventory, defaults_installed, phase
):
    """`includes` listed `rfc`, `spec` and `plan` — files this command has no
    business inlining and never did — and `named_components` for a section
    delivered under `components`. A caller reading the contract and finding
    nothing under the name reads it as the design system having nothing."""
    write_config({"adapter": "static-json"})
    payload = context(design, phase)
    missing = [name for name in payload["includes"] if name not in payload]
    assert missing == [], f"{phase}: advertised but absent -> {missing}"


@pytest.mark.parametrize("phase", ["clarify", "plan", "implement"])
def test_the_artifacts_a_phase_reads_are_named_separately(
    design, project, write_config, inventory, defaults_installed, phase
):
    """Dropping them from `includes` must not lose them: the whole input to a
    phase should still be visible in one place."""
    write_config({"adapter": "static-json"})
    payload = context(design, phase)
    assert payload["read_from_artifacts"], phase
    assert not set(payload["read_from_artifacts"]) & set(payload["includes"])


def test_every_phase_declares_both_halves_of_its_input(design):
    assert set(design.PHASE_ARTIFACTS) == set(design.PHASE_CONTEXT)
