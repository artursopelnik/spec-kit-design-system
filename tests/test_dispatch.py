"""Capability dispatch, and the failure semantics the gate depends on.

The rule under test throughout: a failure to *ask* the design system must never
be reported as the design system *answering* that it has nothing. That confusion
would push the reuse ladder toward Create, the outcome this extension exists to
prevent.
"""

from __future__ import annotations

from pathlib import Path


def run(designsys, capability, **params):
    root = Path.cwd()
    config = designsys.load_config(root)
    adapter = designsys.load_adapter(root, config)
    return designsys.run_capability(root, config, adapter, capability, params)


# --- static inventory --------------------------------------------------------


def test_static_inventory_returns_one_component(designsys, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(designsys, "component", name="Calendar")
    assert result["found"] is True
    assert result["data"]["name"] == "Calendar"


def test_static_inventory_reports_a_real_miss(designsys, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(designsys, "component", name="Nonexistent")
    assert result["available"] is True and result["found"] is False


def test_static_inventory_search_ranks_by_overlap(designsys, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(designsys, "search", query="floating container date")
    assert [hit["name"] for hit in result["data"]][0] == "Popover"


def test_missing_inventory_is_unavailable_not_empty(designsys, project, write_config):
    write_config({"adapter": "static-json"})
    assert run(designsys, "component", name="Calendar")["available"] is False


def test_read_file_honours_cwd(designsys, project, write_config, inventory):
    """`cwd` exists for monorepos; file lookups must respect it like subprocesses do."""
    nested = project / "apps" / "web" / ".design-system"
    nested.mkdir(parents=True)
    (nested / "inventory.json").write_text(inventory.read_text(), encoding="utf-8")

    write_config({"adapter": "static-json", "cwd": "apps/web"})
    result = run(designsys, "component", name="Calendar")
    assert result["available"] is True
    assert "apps/web" in result["source"]


def test_unmapped_capability_degrades(designsys, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    result = run(designsys, "report_gap", title="T", body="B")
    assert result["available"] is False and "does not map" in result["reason"]


# --- subprocess dispatch -----------------------------------------------------


def test_nonzero_exit_is_unavailable_even_with_parseable_json(
    designsys, project, write_config, fake_cli
):
    write_config({"adapter": "fake"})
    result = run(designsys, "component", name="boom")
    assert result["available"] is False
    assert result["exit_code"] == 3


def test_undeclared_error_code_is_unavailable(designsys, project, write_config, fake_cli):
    """A registry outage must not read as 'the design system has nothing'."""
    write_config({"adapter": "fake"})
    result = run(designsys, "component", name="unknown")
    assert result["available"] is False
    assert result["error_code"] == "ERR_REGISTRY_DOWN"


def test_declared_not_found_code_is_a_real_answer(designsys, project, write_config, fake_cli):
    write_config({"adapter": "fake"})
    result = run(designsys, "component", name="missing")
    assert result["available"] is True and result["found"] is False


def test_registries_reach_the_cli_as_separate_arguments(
    designsys, project, write_config, fake_cli
):
    write_config({"adapter": "fake"})
    argv = run(designsys, "search", query="btn")["data"]
    assert "@one" in argv and "@two" in argv
    assert "@one @two" not in argv


def test_absent_placeholder_drops_its_flag(designsys, project, write_config, fake_cli):
    """Dropping only the value leaves a dangling flag that eats the next arg."""
    write_config({"adapter": "fake"})
    argv = run(designsys, "report_gap", title="MyTitle")["data"]
    assert "--body" not in argv
    assert "--json" in argv
    assert "MyTitle" in argv


def test_missing_binary_is_unavailable(designsys, project, write_config, fake_cli):
    write_config({"adapter": "fake", "bin": "./definitely-not-here"})
    result = run(designsys, "search", query="btn")
    assert result["available"] is False and "not found" in result["reason"]


# --- the probe ---------------------------------------------------------------


def test_probe_reports_capabilities_when_reachable(designsys, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    root = Path.cwd()
    config = designsys.load_config(root)
    probe = designsys.probe_adapter(root, config, designsys.load_adapter(root, config))
    assert probe["reachable"] is True
    assert "component" in probe["capabilities"]


def test_probe_fails_closed_when_the_design_system_is_unreachable(
    designsys, project, write_config
):
    """The gate keys on CAPABILITIES. Trusting the adapter file instead of the
    CLI would report a full set for a design system that is not installed, and
    the commands' fail-closed guard could never fire."""
    write_config({"adapter": "example", "bin": "./definitely-not-here"})
    root = Path.cwd()
    config = designsys.load_config(root)
    adapter = designsys.load_adapter(root, config)

    assert len(designsys.mapped_capabilities(adapter)) == 8
    probe = designsys.probe_adapter(root, config, adapter)
    assert probe["reachable"] is False
    assert probe["capabilities"] == []


# --- gate payload ------------------------------------------------------------


def test_gate_resolves_the_active_feature(designsys, project, write_config, inventory, feature):
    write_config({"adapter": "static-json"})
    root = Path.cwd()
    assert designsys.feature_dir(root) == feature
    assert designsys.detect_ui_bearing(feature / "spec.md") is True


def test_backend_spec_is_not_ui_bearing(designsys, project, tmp_path):
    spec = tmp_path / "backend.md"
    spec.write_text(
        "# Nightly reconciliation job\n\nAggregate ledger entries and write a report row.\n",
        encoding="utf-8",
    )
    assert designsys.detect_ui_bearing(spec) is False
