"""Capability dispatch, and the failure semantics the gate depends on.

The rule under test throughout: a failure to *ask* the design system must never
be reported as the design system *answering* that it has nothing. That confusion
would push the reuse ladder toward Create, the outcome this extension exists to
prevent.
"""

from __future__ import annotations

from pathlib import Path


def run(design, capability, **params):
    root = Path.cwd()
    config = design.load_config(root)
    adapter = design.load_adapter(root, config)
    return design.run_capability(root, config, adapter, capability, params)


# --- static inventory --------------------------------------------------------


def test_static_inventory_returns_one_component(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(design, "component", name="Calendar")
    assert result["found"] is True
    assert result["data"]["name"] == "Calendar"


def test_static_inventory_reports_a_real_miss(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(design, "component", name="Nonexistent")
    assert result["available"] is True and result["found"] is False


def test_static_inventory_search_ranks_by_overlap(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(design, "search", query="floating container date")
    assert [hit["name"] for hit in result["data"]][0] == "Popover"


def test_missing_inventory_is_unavailable_not_empty(design, project, write_config):
    write_config({"adapter": "static-json"})
    assert run(design, "component", name="Calendar")["available"] is False


def test_read_file_honours_cwd(design, project, write_config, inventory):
    """`cwd` exists for monorepos; file lookups must respect it like subprocesses do."""
    nested = project / "apps" / "web" / ".design-system"
    nested.mkdir(parents=True)
    (nested / "inventory.json").write_text(inventory.read_text(), encoding="utf-8")

    write_config({"adapter": "static-json", "cwd": "apps/web"})
    result = run(design, "component", name="Calendar")
    assert result["available"] is True
    assert "apps/web" in result["source"]


def test_unmapped_capability_degrades(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(design, "report_gap", title="T", body="B")
    assert result["available"] is False and "does not map" in result["reason"]


# --- subprocess dispatch -----------------------------------------------------


def test_nonzero_exit_is_unavailable_even_with_parseable_json(
    design, project, write_config, fake_cli
):
    write_config({"adapter": "fake"})
    result = run(design, "component", name="boom")
    assert result["available"] is False
    assert result["exit_code"] == 3


def test_undeclared_error_code_is_unavailable(design, project, write_config, fake_cli):
    """A registry outage must not read as 'the design system has nothing'."""
    write_config({"adapter": "fake"})
    result = run(design, "component", name="unknown")
    assert result["available"] is False
    assert result["error_code"] == "ERR_REGISTRY_DOWN"


def test_declared_not_found_code_is_a_real_answer(design, project, write_config, fake_cli):
    write_config({"adapter": "fake"})
    result = run(design, "component", name="missing")
    assert result["available"] is True and result["found"] is False


def test_registries_reach_the_cli_as_separate_arguments(
    design, project, write_config, fake_cli
):
    write_config({"adapter": "fake"})
    argv = run(design, "search", query="btn")["data"]
    assert "@one" in argv and "@two" in argv
    assert "@one @two" not in argv


def test_absent_placeholder_drops_its_flag(design, project, write_config, fake_cli):
    """Dropping only the value leaves a dangling flag that eats the next arg."""
    write_config({"adapter": "fake"})
    argv = run(design, "report_gap", title="MyTitle")["data"]
    assert "--body" not in argv
    assert "--json" in argv
    assert "MyTitle" in argv


def test_missing_binary_is_unavailable(design, project, write_config, fake_cli):
    write_config({"adapter": "fake", "bin": "./definitely-not-here"})
    result = run(design, "search", query="btn")
    assert result["available"] is False and "not found" in result["reason"]


# --- the probe ---------------------------------------------------------------


def test_probe_reports_capabilities_when_reachable(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    root = Path.cwd()
    config = design.load_config(root)
    probe = design.probe_adapter(root, config, design.load_adapter(root, config))
    assert probe["reachable"] is True
    assert "component" in probe["capabilities"]


def test_probe_fails_closed_when_the_design_system_is_unreachable(
    design, project, write_config
):
    """The gate keys on CAPABILITIES. Trusting the adapter file instead of the
    CLI would report a full set for a design system that is not installed, and
    the commands' fail-closed guard could never fire."""
    write_config({"adapter": "example", "bin": "./definitely-not-here"})
    root = Path.cwd()
    config = design.load_config(root)
    adapter = design.load_adapter(root, config)

    # The template adapter maps the whole contract, so the gap between what is
    # declared and what is reachable is as wide as it can get.
    assert design.mapped_capabilities(adapter) == design.CAPABILITIES
    probe = design.probe_adapter(root, config, adapter)
    assert probe["reachable"] is False
    assert probe["capabilities"] == []


# --- gate payload ------------------------------------------------------------


def test_gate_resolves_the_active_feature(design, project, write_config, inventory, feature):
    write_config({"adapter": "static-json"})
    root = Path.cwd()
    assert design.feature_dir(root) == feature
    assert design.detect_ui_bearing(feature / "spec.md") is True


def test_backend_spec_is_not_ui_bearing(design, project, tmp_path):
    spec = tmp_path / "backend.md"
    spec.write_text(
        "# Nightly reconciliation job\n\nAggregate ledger entries and write a report row.\n",
        encoding="utf-8",
    )
    assert design.detect_ui_bearing(spec) is False


# --- search ranking, found by walking the example end to end -----------------


def test_camelcase_names_are_tokenized(design):
    """Component names are CamelCase. Lowercasing before splitting would make
    `DateRangePicker` one token that "date range picker" can never match, which
    breaks both component search and the ledger's alias recall."""
    assert design.normalize("DateRangePicker") == ["date", "range", "picker"]
    assert design.normalize("ConfirmDialog") == ["confirm", "dialog"]
    assert design.normalize("FilterBar") == ["filter", "bar"]


def test_search_ranks_name_matches_above_prose(
    design, project, write_config, inventory
):
    """A raw overlap count ties every candidate at 1 on short descriptions, so
    results come back in insertion order and "the strongest hits" means nothing."""
    write_config({"adapter": "static-json"})
    hits = run(design, "search", query="calendar")["data"]

    assert hits[0]["name"] == "Calendar"
    assert hits[0]["score"] > (hits[1]["score"] if len(hits) > 1 else 0)


def test_search_scores_are_not_all_equal(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    hits = run(design, "search", query="floating container anchored")["data"]
    assert len({hit["score"] for hit in hits}) > 1 or len(hits) == 1


# --- the adapter stays thin ---------------------------------------------------

ADAPTER_KEYS = {
    "id", "name", "bin", "global_args", "envelope", "source", "registries", "capabilities",
}
CAPABILITY_KEYS = {
    "args", "read_file", "result_path", "key_field", "search_keys", "match_fields",
    "defaults", "not_found_codes",
}


def test_adapters_only_map_and_never_model(design):
    """An adapter is a bridge, not a second design system. The moment one can
    carry rules, guidance or component knowledge of its own, the design system
    stops being the source of truth and starts having a rival."""
    import yaml

    from pathlib import Path as P

    for path in (P(__file__).resolve().parents[1] / "adapters").glob("*.yml"):
        adapter = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert set(adapter) <= ADAPTER_KEYS, f"{path.name} carries {set(adapter) - ADAPTER_KEYS}"
        for name, spec in (adapter.get("capabilities") or {}).items():
            assert name in design.CAPABILITIES, f"{path.name}: unknown capability {name}"
            assert set(spec) <= CAPABILITY_KEYS, f"{path.name}:{name} {set(spec) - CAPABILITY_KEYS}"


def test_every_shipped_adapter_maps_the_two_required_capabilities(design):
    """`search` and `component` are what the reuse ladder cannot run without."""
    import yaml

    from pathlib import Path as P

    for path in (P(__file__).resolve().parents[1] / "adapters").glob("*.yml"):
        mapped = set(yaml.safe_load(path.read_text(encoding="utf-8")).get("capabilities") or {})
        assert {"search", "component"} <= mapped, f"{path.name} maps only {mapped}"


def test_a_missed_envelope_returns_what_the_cli_said(
    design, project, write_config, fake_cli
):
    """A shipped adapter guesses at a CLI's envelope. When the guess misses, the
    raw payload is worth more than a null that reads as "nothing found"."""
    write_config({"adapter": "fake"})
    result = run(design, "component", name="envelopeless")

    assert result["available"] is True
    assert result["result_path_missed"] is True
    assert result["data"] == {"loose": "payload"}


def test_a_file_backed_adapter_does_not_guess(
    design, project, write_config, inventory
):
    """The opposite case: an adapter that points at a file knows that file's
    shape, so a missing section means the section is missing, not mismapped."""
    write_config({"adapter": "static-json"})
    result = run(design, "guidelines")

    assert result["available"] is True
    assert result["found"] is False
    assert result["data"] is None


# --- nothing is mandatory that the design system cannot supply -----------------


def test_a_system_without_tokens_is_not_required_to_answer_for_them(
    design, project, write_config, inventory
):
    import json

    data = json.loads(inventory.read_text())
    data.pop("tokens")
    inventory.write_text(json.dumps(data), encoding="utf-8")
    write_config(
        {"adapter": "static-json", "capabilities": {"tokens": {"read_file": "", "args": []}}}
    )
    root = Path.cwd()
    config = design.load_config(root)
    assert "tokens" in design.effective_dimensions(config, ["search", "component", "tokens"])
    assert "tokens" not in design.effective_dimensions(config, ["search", "component"])


# --- failure modes found by running the adapters against real-shaped output --


def _script(project: Path, body: str) -> str:
    path = project / "fakebin.sh"
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return "./fakebin.sh"


def test_prose_from_a_json_adapter_is_unavailable(design, project, write_config, fake_cli):
    """A changed flag that turns JSON into prose must not read as an answer."""
    write_config({"adapter": "fake", "bin": _script(project, "echo '<html>oops</html>'")})
    result = run(design, "search", query="btn")
    assert result["available"] is False and "expected JSON" in result["reason"]


def test_empty_cli_output_is_not_found(design, project, write_config, fake_cli):
    write_config({"adapter": "fake", "bin": _script(project, "exit 0")})
    result = run(design, "search", query="btn")
    assert result["available"] is True and result["found"] is False


def test_inventory_that_is_not_a_mapping_is_unavailable(
    design, project, write_config, inventory
):
    inventory.write_text("[]", encoding="utf-8")
    write_config({"adapter": "static-json"})
    result = run(design, "search", query="date")
    assert result["available"] is False and "mapping" in result["reason"]


def test_search_without_a_query_does_not_dump_the_inventory(
    design, project, write_config, inventory
):
    write_config({"adapter": "static-json"})
    result = run(design, "search")
    assert result["available"] is False and "query" in result["reason"]
