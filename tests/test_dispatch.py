"""Capability dispatch, and the failure semantics the gate depends on.

The rule under test throughout: a failure to *ask* the design system must never
be reported as the design system *answering* that it has nothing. That confusion
would push the reuse ladder toward Create, the outcome this extension exists to
prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def run(design, capability, **params):
    return design.DesignSystem.resolve().ask(capability, **params)


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
    probe = design.DesignSystem.resolve().probe
    assert probe["reachable"] is True
    assert "component" in probe["capabilities"]


def test_probe_fails_closed_when_the_design_system_is_unreachable(
    design, project, write_config
):
    """The gate keys on CAPABILITIES. Trusting the adapter file instead of the
    CLI would report a full set for a design system that is not installed, and
    the commands' fail-closed guard could never fire."""
    write_config({"adapter": "example", "bin": "./definitely-not-here"})
    ds = design.DesignSystem.resolve()

    # The template adapter maps the whole contract, so the gap between what is
    # declared and what is reachable is as wide as it can get.
    assert design.mapped_capabilities(ds.adapter) == design.CAPABILITIES
    probe = ds.probe
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
    "args", "bin", "read_file", "result_path", "result_paths", "pick", "key_field",
    "search_keys", "match_fields", "defaults", "not_found_codes",
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
    result = run(design, "principles")

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


# --- one command, two questions ----------------------------------------------
#
# Most design systems have no breakpoint command: breakpoints come back inside
# the token payload. Mapping `breakpoints` onto the token command then makes the
# two capabilities identical, and the larger of the two answers is the one
# every phase pays for. The adapter is where that is carved apart, because the
# adapter is the only layer that knows the shape of this system's response.


def test_a_capability_can_carve_its_answer_out_of_a_shared_command(
    design, project, write_config, fake_cli
):
    write_config({"adapter": "fake"})
    tokens = run(design, "tokens")
    breakpoints = run(design, "breakpoints")

    assert breakpoints["found"] is True
    assert breakpoints["data"] == {"sm": "640px", "md": "768px", "lg": "1024px"}
    # Same call, a focused answer: the whole point of the mapping.
    assert breakpoints["command"] == tokens["command"]
    assert breakpoints["bytes"] < tokens["bytes"]


def test_result_paths_try_each_candidate_in_order(design, project, write_config, fake_cli):
    """`data.screens` first, `data.breakpoints` second. Systems disagree on the
    name and adapters should not have to guess right on the first try."""
    write_config({"adapter": "fake"})
    result = run(design, "breakpoints")
    assert result["result_path_missed"] is False
    assert "sm" in result["data"]


def test_pick_narrows_to_named_keys(design, project, write_config, fake_cli):
    write_config(
        {
            "adapter": "fake",
            "capabilities": {"tokens": {"args": ["tokens"], "result_path": "data",
                                        "pick": ["color", "space"]}},
        }
    )
    result = run(design, "tokens")
    assert set(result["data"]) == {"color", "space"}


def test_a_slice_that_resolves_to_nothing_is_a_miss_not_an_answer(
    design, project, write_config, fake_cli
):
    """The failure this makes visible: a mapping that matches nothing quietly
    hands back the entire payload, which reads as a working capability and
    costs context on every run."""
    write_config(
        {
            "adapter": "fake",
            "capabilities": {"breakpoints": {"args": ["tokens"],
                                             "result_paths": ["data.nope", "data.also_nope"]}},
        }
    )
    result = run(design, "breakpoints")
    assert result["result_path_missed"] is True
    # Handed back whole rather than as a null that would read as "no breakpoints".
    assert "color" in result["data"]["data"]


def test_every_answer_reports_what_it_costs(design, project, write_config, inventory):
    """Focused context is a claim about size. Sizes are reported so the claim
    can be checked against a real design system rather than assumed."""
    write_config({"adapter": "static-json"})
    result = run(design, "tokens")
    assert result["bytes"] == len(json.dumps(result["data"], separators=(",", ":")).encode())


# --- the caller's own trim ----------------------------------------------------


def test_fields_trim_a_listing_without_hiding_it(design, project, write_config, inventory):
    """`list_components` is the right answer to "what is there" and the most
    expensive thing the system will say. Surveying it should not cost the whole
    inventory, and the full answer stays one call away."""
    full = design.project_fields(
        [{"name": "Calendar", "description": "Month grid", "states": ["default"]}], []
    )
    trimmed = design.project_fields(
        [{"name": "Calendar", "description": "Month grid", "states": ["default"]}],
        ["name", "description"],
    )
    assert full[0]["states"] == ["default"]
    assert trimmed == [{"name": "Calendar", "description": "Month grid"}]


def test_fields_on_a_mapping_keep_named_keys(design):
    assert design.project_fields({"a": 1, "b": 2}, ["b"]) == {"b": 2}


# --- what the ladder can actually ask ----------------------------------------


def test_the_gate_reports_which_ladder_rungs_are_automated(design):
    """Rungs 4 and 5 are the ones most often unmapped, because most CLIs have no
    extend or intake command. That is a supported degradation, not a fault - but
    an adapter author should be able to see it at gate time."""
    support = design.ladder_support(["search", "component", "pattern"])
    assert support["reuse"]["automated"] is True
    assert support["compose"]["automated"] is True
    assert support["extend"]["automated"] is False
    assert support["create"]["automated"] is False

    full = design.ladder_support(["search", "component", "pattern", "extend", "report_gap"])
    assert all(rung["automated"] for rung in full.values())


# --- the top of the ladder usually belongs to another tool --------------------
#
# `extend` and `report_gap` are the two capabilities most design system CLIs do
# not have, which leaves rungs 4 and 5 unautomated on systems that could support
# them perfectly well: the gap goes to an issue tracker and the eject is a
# codegen tool. Neither is the design system's binary, and requiring a wrapper
# script to bridge that is the reason those mappings do not get written.


def test_a_capability_can_name_its_own_binary(design, project, write_config, fake_cli):
    intake = project / "intake.sh"
    intake.write_text(
        '#!/bin/sh\nprintf \'{"filed":"%s"}\\n\' "$2"\n', encoding="utf-8"
    )
    intake.chmod(0o755)

    write_config(
        {
            "adapter": "fake",
            "capabilities": {
                "report_gap": {
                    "bin": "./intake.sh",
                    "args": ["issue", "{title}", "--body", "{body}"],
                    "result_path": "",
                }
            },
        }
    )
    result = run(design, "report_gap", title="Date range", body="No range semantics")

    assert result["available"] is True
    assert result["data"] == {"filed": "Date range"}
    assert result["command"].startswith("./intake.sh")


def test_another_tools_invocation_does_not_inherit_the_cli_global_args(
    design, project, write_config, fake_cli
):
    """`global_args` is the design system CLI's flag for emitting JSON. Passing
    it to an issue tracker's CLI is a mapping error the adapter author did not
    write, and would look like the tracker rejecting the call."""
    echo = project / "argv.sh"
    echo.write_text(
        '#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n',
        encoding="utf-8",
    )
    echo.chmod(0o755)

    write_config(
        {
            "adapter": "fake",
            "capabilities": {"report_gap": {"bin": "./argv.sh", "args": ["file", "{title}"],
                                            "result_path": ""}},
        }
    )
    result = run(design, "report_gap", title="Date range", body="ignored")
    assert result["data"] == ["file", "Date range"]

    # The design system's own capabilities still get them.
    assert "--json" in run(design, "search", query="btn")["command"]


def test_a_file_backed_adapter_can_still_have_a_write_side(
    design, project, write_config, inventory
):
    """A static inventory has nothing to file a gap with, which is why the
    shipped adapters leave `report_gap` unmapped. The project can still map it,
    without the adapter gaining a binary it has no other use for."""
    intake = project / "intake.sh"
    intake.write_text('#!/bin/sh\necho \'{"ok":true}\'\n', encoding="utf-8")
    intake.chmod(0o755)

    write_config(
        {
            "adapter": "static-json",
            "capabilities": {
                "report_gap": {"bin": "./intake.sh", "args": ["{title}"], "result_path": ""}
            },
        }
    )
    result = run(design, "report_gap", title="Date range", body="...")
    assert result["data"] == {"ok": True}
    assert design.ladder_support(["search", "component", "report_gap"])["create"]["automated"]


def test_another_tools_response_is_not_read_through_this_cli_envelope(
    design, project, write_config, fake_cli
):
    """The fake adapter declares `code` as its error key. An issue tracker that
    happens to return a `code` field has not failed, and reporting it as an
    outage would lose a gap record that was actually filed."""
    intake = project / "intake.sh"
    intake.write_text('#!/bin/sh\necho \'{"code":"CREATED","url":"http://x/1"}\'\n', encoding="utf-8")
    intake.chmod(0o755)

    write_config(
        {
            "adapter": "fake",
            "capabilities": {"report_gap": {"bin": "./intake.sh", "args": ["{title}"],
                                            "result_path": ""}},
        }
    )
    result = run(design, "report_gap", title="Date range", body="...")
    assert result["available"] is True
    assert result["data"]["url"] == "http://x/1"


# --- the seams the refactor introduced ----------------------------------------
#
# Dispatch was one 234-line function with five jobs in it: routing, two
# transports, three query strategies and envelope construction. The value of
# splitting it is only real if a new transport is a class and a registry entry,
# so that is what these check.


def test_every_transport_answers_the_protocol(design):
    for transport in design.TRANSPORTS:
        assert hasattr(transport, "handles") and hasattr(transport, "fetch")


def test_every_strategy_answers_the_protocol(design):
    for strategy in design.STRATEGIES:
        assert hasattr(strategy, "handles") and hasattr(strategy, "answer")


def test_the_last_strategy_always_handles(design):
    """Selection uses `next(...)` without a default, so the fallback has to be
    total or an unusual mapping raises StopIteration instead of answering."""
    request = design.Request("tokens", {}, {}, Path.cwd(), {}, 30)
    assert design.STRATEGIES[-1].handles(request) is True


def test_a_transport_is_chosen_by_the_mapping_not_by_order(design):
    base = Path.cwd()
    file_spec = design.Request("tokens", {"read_file": "x.json"}, {}, base, {}, 30)
    mcp_spec = design.Request("search", {"mcp": {"tool": "t"}}, {}, base, {}, 30)
    cli_spec = design.Request("search", {"args": ["search"]}, {"bin": "ds"}, base, {}, 30)

    picked = lambda req: type(  # noqa: E731
        next(t for t in design.TRANSPORTS if t.handles(req))
    ).__name__
    assert picked(file_spec) == "FileTransport"
    assert picked(mcp_spec) == "McpTransport"
    assert picked(cli_spec) == "ProcessTransport"


def test_an_unmapped_capability_reaches_no_transport(design, project, write_config):
    write_config({"adapter": "static-json"})
    result = run(design, "report_gap", title="t", body="b")
    assert result["available"] is False and "does not map" in result["reason"]


# --- Answer keeps the invariant in one place ----------------------------------


def test_unavailable_never_claims_an_answer(design):
    envelope = design.Answer.unavailable("search", "CLI not installed")
    assert envelope["available"] is False
    assert "found" not in envelope, (
        "a failure to ask must not carry `found`: a caller reading found=False "
        "would take it for the design system saying it has nothing"
    )


def test_answered_reports_its_own_size(design):
    envelope = design.Answer.answered("tokens", {"space": {"3": "12px"}})
    assert envelope["available"] is True and envelope["found"] is True
    assert envelope["bytes"] == design.payload_bytes(envelope["data"])
    assert envelope["result_path_missed"] is False


@pytest.mark.parametrize("empty", [None, [], {}])
def test_an_empty_answer_is_still_an_answer(design, empty):
    envelope = design.Answer.answered("pattern", empty)
    assert envelope["available"] is True and envelope["found"] is False


# --- MCP: the transport the README has always promised ------------------------


def test_mcp_without_a_client_is_unavailable_not_empty(design, project, write_config):
    """The failure mode that matters: an MCP mapping nobody can call must read
    as a failure to ask, never as a design system with nothing in it."""
    write_config(
        {
            "adapter": "custom",
            "capabilities": {"search": {"mcp": {"server": "ds", "tool": "search"}}},
        }
    )
    result = run(design, "search", query="date range")
    assert result["available"] is False
    assert "found" not in result
    assert "MCP client" in result["reason"]


def test_mcp_mapping_without_a_tool_is_rejected(design, project, write_config):
    write_config(
        {"adapter": "custom", "capabilities": {"search": {"mcp": {"server": "ds"}}}}
    )
    result = run(design, "search", query="x")
    assert result["available"] is False and "tool" in result["reason"]


def test_mcp_calls_the_client_with_the_tool_and_the_query(design, project, write_config):
    """A stand-in client that echoes what it was handed, so the argv the
    transport builds is observable."""
    client = project / "mcp-client.sh"
    client.write_text(
        '#!/usr/bin/env bash\n'
        'printf \'{"results":[{"name":"Calendar","argv":"%s"}]}\\n\' "$*"\n',
        encoding="utf-8",
    )
    client.chmod(0o755)
    write_config(
        {
            "adapter": "custom",
            "capabilities": {
                "search": {
                    "mcp": {"server": "design-system", "tool": "search_components",
                            "client": str(client)},
                    "args": ["--query", "{query}"],
                    "result_path": "results",
                }
            },
        }
    )
    result = run(design, "search", query="date range")

    assert result["available"] is True and result["found"] is True
    argv = result["data"][0]["argv"]
    assert "--server design-system" in argv
    assert "--tool search_components" in argv
    assert "--query date range" in argv


def test_an_mcp_server_that_fails_is_unavailable(design, project, write_config):
    client = project / "broken-client.sh"
    client.write_text('#!/usr/bin/env bash\necho "connection refused" >&2\nexit 1\n',
                      encoding="utf-8")
    client.chmod(0o755)
    write_config(
        {
            "adapter": "custom",
            "capabilities": {
                "search": {"mcp": {"tool": "search", "client": str(client)}},
            },
        }
    )
    result = run(design, "search", query="x")
    assert result["available"] is False and "found" not in result
    assert "connection refused" in result["reason"]


# --- the probe must be harmless ------------------------------------------------


def test_the_probe_never_calls_a_capability_with_side_effects(design, project, write_config):
    """Filing an issue to find out whether the design system is there would file
    one on every gate. With nothing safe to call, reach stays unproven."""
    marker = project / "filed"
    tool = project / "file-issue.sh"
    tool.write_text(f"#!/usr/bin/env bash\ntouch {marker}\necho '{{}}'\n", encoding="utf-8")
    tool.chmod(0o755)
    write_config(
        {"adapter": "custom", "capabilities": {"report_gap": {"bin": str(tool), "args": []}}}
    )
    probe = design.DesignSystem.resolve().probe

    assert probe["reachable"] is False and "safe to probe" in probe["reason"]
    assert not marker.exists()


def test_a_read_only_capability_can_prove_reach(design, project, write_config, inventory):
    write_config(
        {
            "adapter": "custom",
            "source": ".design-system/inventory.json",
            "capabilities": {"tokens": {"read_file": "{source}", "result_path": "tokens"}},
        }
    )
    probe = design.DesignSystem.resolve().probe
    assert probe["reachable"] is True and probe["probed"] == "tokens"


def test_mcp_arguments_are_expanded_once(design, project, write_config):
    """The client path is split once and the query substituted once: a space in
    the path, or braces inside the query, must arrive as written."""
    directory = project / "mcp tools"
    directory.mkdir()
    client = directory / "client.sh"
    client.write_text(
        "#!/usr/bin/env bash\n"
        "python3 -c 'import json,sys; print(json.dumps({\"argv\": sys.argv[1:]}))' \"$@\"\n",
        encoding="utf-8",
    )
    client.chmod(0o755)
    write_config(
        {
            "adapter": "custom",
            "capabilities": {
                "search": {
                    "mcp": {"tool": "search", "client": f"'{client}'"},
                    "args": ["--query", "{query}"],
                    "result_path": "argv",
                }
            },
        }
    )
    result = run(design, "search", query="{name} picker")

    assert result["available"] is True, result.get("reason")
    assert result["data"] == ["--tool", "search", "--query", "{name} picker"]


def test_a_malformed_yaml_inventory_is_unavailable(design, project, write_config):
    """One capability that cannot answer, reported as such, not the whole
    process exiting from inside a transport."""
    source = project / ".design-system" / "inventory.yml"
    source.parent.mkdir(parents=True)
    source.write_text("components: [unclosed\n", encoding="utf-8")
    write_config({"adapter": "static-json", "source": ".design-system/inventory.yml"})

    result = run(design, "list_components")
    assert result["available"] is False and "not valid YAML" in result["reason"]


def test_a_file_mapping_with_no_source_says_so(design, project, write_config):
    write_config(
        {"adapter": "custom", "capabilities": {"tokens": {"read_file": "{source}"}}}
    )
    result = run(design, "tokens")
    assert result["available"] is False and "source" in result["reason"]
