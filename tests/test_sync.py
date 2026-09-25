"""`ds.sh sync`: when the design system ships, what is now out of date.

The snapshot is what was true; the diff is what moved; the references are the
specs, decisions and code that still name it. Stated, never judged, and never
"nothing changed" when the design system could not be asked.
"""

from __future__ import annotations

import json

import pytest


def write_inventory(project, components, tokens=None):
    path = project / ".design-system" / "inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"components": components}
    if tokens is not None:
        body["tokens"] = tokens
    path.write_text(json.dumps(body), encoding="utf-8")


BEFORE = [
    {"name": "Button", "description": "Triggers an action"},
    {"name": "Popover", "description": "Floating container"},
    {"name": "DatePicker", "description": "Single date"},
]
TOKENS = {"color": {"text": "#172b4d", "brand": "#0052cc"}, "space": {"3": "12px"}}


@pytest.fixture
def system(project, write_config):
    write_inventory(project, BEFORE, TOKENS)
    write_config({
        "adapter": "static-json",
        "design_system_version": "1.0.0",
        "validation": {"source_globs": ["src/**/*"]},
    })
    return project


def sync(design, record=False, paths=None):
    return design.sync_design_system(design.DesignSystem.resolve(), record, paths)


def test_without_a_snapshot_it_says_so_and_record_takes_one(design, system):
    first = sync(design)
    assert first["snapshot_exists"] is False and first["changes"] is None
    assert any("sync record" in note for note in first["notes"])

    taken = sync(design, record=True)
    assert taken["recorded"] is True
    snapshot = json.loads((system / ".specify" / "memory" / "design-system-snapshot.json").read_text())
    assert snapshot["version"] == "1.0.0"
    assert set(snapshot["components"]) == {"Button", "Popover", "DatePicker"}
    assert snapshot["tokens"]["color.brand"] == "#0052cc"


def test_an_unchanged_system_reports_nothing_to_do(design, system):
    sync(design, record=True)
    result = sync(design)
    assert result["change_count"] == 0 and result["references"] == []


def test_what_moved_and_what_still_names_it(design, system, feature, write_config):
    sync(design, record=True)

    (feature / "design-system.md").write_text(
        "## Surface: date filter\n**Decision**: DatePicker inside Popover, text in `color.brand`.\n",
        encoding="utf-8",
    )
    src = system / "src" / "Filter.tsx"
    src.parent.mkdir(parents=True)
    src.write_text(
        "import { DatePicker } from '@acme/ds';\nconst s = 'var(--color-brand)';\n",
        encoding="utf-8",
    )
    ledger = system / ".specify" / "memory" / "design-decisions.yml"
    ledger.write_text(
        "schema_version: '1.0'\ndecisions:\n"
        "- id: dd-001\n  capability: selection of a date\n  resolution: reuse\n"
        "  decision: DatePicker\n  design_system_version: 1.0.0\n",
        encoding="utf-8",
    )

    write_inventory(
        system,
        [
            {"name": "Button", "description": "Triggers an action"},
            {"name": "Popover", "description": "Floating container", "status": "deprecated"},
            {"name": "DateRangePicker", "description": "From-to dates"},
        ],
        {"color": {"text": "#172b4d", "brand": "#0055cc"}, "space": {"3": "12px"}},
    )
    write_config({
        "adapter": "static-json",
        "design_system_version": "2.0.0",
        "validation": {"source_globs": ["src/**/*"]},
    })

    result = sync(design)
    components = result["changes"]["components"]
    assert components["added"] == ["DateRangePicker"]
    assert components["removed"] == ["DatePicker"]
    assert components["deprecated"] == ["Popover"]
    assert result["changes"]["tokens"]["changed"] == ["color.brand"]
    assert result["snapshot_version"] == "1.0.0" and result["current_version"] == "2.0.0"

    seen = {(r["file"], r["name"], r["change"]) for r in result["references"]}
    contract = "specs/001-booking-filters/design-system.md"
    assert (contract, "DatePicker", "removed") in seen
    assert (contract, "Popover", "deprecated") in seen
    assert (contract, "color.brand", "changed") in seen
    assert ("src/Filter.tsx", "DatePicker", "removed") in seen
    assert ("src/Filter.tsx", "color.brand", "changed") in seen
    # Nothing written before an addition names it.
    assert not any(r["name"] == "DateRangePicker" for r in result["references"])

    assert result["affected_decisions"][0]["id"] == "dd-001"
    assert result["stale_decisions"] == ["dd-001"]


def test_a_name_inside_a_longer_name_is_not_a_reference(design, system, feature, write_config):
    sync(design, record=True)
    write_inventory(system, [c for c in BEFORE if c["name"] != "Button"], TOKENS)
    (feature / "spec.md").write_text("Uses IconButton and ButtonGroup.\n", encoding="utf-8")
    result = sync(design)
    assert result["changes"]["components"]["removed"] == ["Button"]
    assert result["references"] == []


def test_a_system_that_cannot_be_asked_has_not_stood_still(design, system):
    """Fail closed: a missing inventory must never read as "nothing changed",
    or as every component having been removed."""
    sync(design, record=True)
    (system / ".design-system" / "inventory.json").unlink()
    result = sync(design)
    assert result["available"] is False and result["changes"] is None
    record = sync(design, record=True)
    assert "recorded" not in record
    snapshot = json.loads((system / ".specify" / "memory" / "design-system-snapshot.json").read_text())
    assert len(snapshot["components"]) == 3


def run_cli(design, capsys, monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["design", *argv])
    code = 0
    try:
        design.main()
    except SystemExit as exc:
        code = exc.code
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    return code, json.loads(lines[0])


def test_strict_sync_fails_ci_until_there_is_a_snapshot(design, system, capsys, monkeypatch):
    code, _ = run_cli(design, capsys, monkeypatch, ["sync", "--strict"])
    assert code == 1
    code, _ = run_cli(design, capsys, monkeypatch, ["sync", "record"])
    assert code == 0
    code, result = run_cli(design, capsys, monkeypatch, ["sync", "check", "--strict"])
    assert code == 0 and result["failed"] is False


def test_strict_sync_fails_ci_when_the_project_names_something_that_moved(
    design, system, feature, capsys, monkeypatch
):
    run_cli(design, capsys, monkeypatch, ["sync", "record"])
    (feature / "spec.md").write_text("The filter opens a Popover.\n", encoding="utf-8")
    write_inventory(system, [c for c in BEFORE if c["name"] != "Popover"], TOKENS)
    code, result = run_cli(design, capsys, monkeypatch, ["sync", "--strict"])
    assert code == 1 and result["reference_count"] == 1


def test_the_gate_carries_the_version_and_the_snapshot(design, system, capsys, monkeypatch):
    run_cli(design, capsys, monkeypatch, ["sync", "record"])
    _, gate = run_cli(design, capsys, monkeypatch, ["gate"])
    assert gate["DESIGN_SYSTEM_VERSION"] == "1.0.0"
    assert gate["DESIGN_SYSTEM_VERSION_SOURCE"] == "config"
    assert gate["SYNC_SNAPSHOT_VERSION"] == "1.0.0"


# --- the version, read rather than remembered ----------------------------------


def test_the_installed_package_knows_its_version(design, project, write_config, inventory):
    (project / "package.json").write_text(json.dumps({"dependencies": {"@mui/material": "^5.0.0"}}))
    installed = project / "node_modules" / "@mui" / "material" / "package.json"
    installed.parent.mkdir(parents=True)
    installed.write_text(json.dumps({"name": "@mui/material", "version": "5.15.2"}))
    write_config({})
    ds = design.DesignSystem.resolve()
    assert (ds.version, ds.version_source) == ("5.15.2", "node_modules/@mui/material")


def test_without_node_modules_the_declared_range_is_the_version(design, project, write_config):
    (project / "package.json").write_text(json.dumps({"dependencies": {"@acme/ds": "~2.1.0"}}))
    write_config({"adapter": "static-json", "design_system_package": "@acme/ds"})
    ds = design.DesignSystem.resolve()
    assert (ds.version, ds.version_source) == ("~2.1.0", "package.json (dependencies)")


def test_config_wins_and_nothing_known_is_empty(design, project, write_config):
    write_config({"adapter": "static-json", "design_system_version": "9"})
    assert design.DesignSystem.resolve().version == "9"
    write_config({"adapter": "static-json"})
    assert design.DesignSystem.resolve().version == ""


def test_a_recorded_decision_carries_the_detected_version(
    design, project, write_config, capsys, monkeypatch
):
    (project / "package.json").write_text(json.dumps({"dependencies": {"@acme/ds": "3.0.0"}}))
    write_config({"adapter": "static-json", "design_system_package": "@acme/ds"})
    payload = json.dumps({"capability": "a date", "resolution": "reuse", "decision": "DatePicker"})
    run_cli(design, capsys, monkeypatch, ["ledger", "record", payload])
    _, listed = run_cli(design, capsys, monkeypatch, ["ledger", "list"])
    assert listed["decisions"][0]["design_system_version"] == "3.0.0"
    _, lookup = run_cli(design, capsys, monkeypatch, ["ledger", "lookup", "a date"])
    assert lookup["staleness_checked"] is True and lookup["matches"][0]["stale"] is False
