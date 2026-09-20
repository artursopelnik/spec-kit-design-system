"""The benchmark harness, and the cases it scores against.

Two things are under test here. The scorer, which has to be deterministic and
arm-neutral or the numbers it produces are worthless. And the cases, which have
to keep describing the design systems they name: a `satisfied_by` entry that no
longer exists in the inventory silently turns a good run into a failing one.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
BENCHMARKS = REPO / "benchmarks"
CASES = sorted((BENCHMARKS / "cases").glob("*/case.yml"))


@pytest.fixture(scope="session")
def harness():
    spec = importlib.util.spec_from_file_location("bench_score", BENCHMARKS / "harness" / "score.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_score"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def report_module():
    spec = importlib.util.spec_from_file_location(
        "bench_report", BENCHMARKS / "harness" / "report.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_report"] = module
    spec.loader.exec_module(module)
    return module


def score_sample(harness, name: str) -> dict:
    run_dir = BENCHMARKS / "samples" / name
    manifest = json.loads((run_dir / "benchmark.json").read_text(encoding="utf-8"))
    case = harness.load_case(manifest["case"], BENCHMARKS / "cases")
    system = harness.load_system(case["design_system"], BENCHMARKS / "systems")
    return harness.score_run(
        run_dir / manifest["workspace"], case, system, manifest.get("provided"), manifest
    )


def metric(result: dict, metric_id: str) -> dict:
    return next(m for m in result["metrics"] if m["id"] == metric_id)


# --- the cases describe the systems they name --------------------------------


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_case_only_expects_components_the_system_has(harness, path):
    """The expensive failure: a case that asks for a component nobody ships."""
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    system = harness.load_system(case["design_system"], BENCHMARKS / "systems")
    known, _, _ = harness.known_names(system["_inventory"])

    for surface in case["surfaces"]:
        for candidate in surface["satisfied_by"]:
            for name in candidate:
                assert harness.normalize(name) in known, (
                    f"{case['id']}/{surface['id']} expects {name}, which "
                    f"{case['design_system']} does not offer"
                )


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_case_is_well_formed(path):
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    directory = path.parent

    assert (directory / case.get("rfc", "rfc.md")).exists()
    assert case["kind"] in {"ui-feature", "ui-change", "ui-bug"}
    assert case["surfaces"], "a case with no surfaces scores nothing"

    for surface in case["surfaces"]:
        assert surface["expected_resolution"] in {
            "reuse", "compose-pattern", "compose-components", "extend", "create",
        }
        assert surface.get("rationale"), f"{surface['id']} rejects rungs without saying why"
        for rule in surface.get("forbidden") or []:
            re.compile(rule["pattern"])
            assert rule["because"]

    for group in case["guidelines"] + case["criteria"]:
        assert group["evidence"], "a rule with no evidence can never be shown to be carried"
        for pattern in group["evidence"]:
            re.compile(pattern)

    for subject in case.get("always_score") or []:
        assert (directory / "seed" / subject).exists(), f"{subject} is not in the seed"


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_rfc_names_no_components(harness, path):
    """An RFC that names a component has already walked the ladder for the agent."""
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    system = harness.load_system(case["design_system"], BENCHMARKS / "systems")
    rfc = (path.parent / case.get("rfc", "rfc.md")).read_text(encoding="utf-8")

    names = {
        entry["name"]
        for kind in ("components", "patterns")
        for entry in system["_inventory"].get(kind) or []
    }
    leaked = {name for name in names if re.search(rf"\b{re.escape(name)}\b", rfc)}
    assert not leaked, f"{case['id']}'s RFC names {sorted(leaked)}"


# --- the scorer ---------------------------------------------------------------


def test_strong_sample_scores_at_the_top(harness):
    result = score_sample(harness, "date-range-filter/strong")
    assert result["score"] >= 0.9
    assert result["metrics_applicable"] == 5


def test_weak_sample_scores_at_the_bottom(harness):
    result = score_sample(harness, "date-range-filter/weak")
    assert result["score"] <= 0.2


def test_every_metric_separates_the_two_samples(harness):
    strong = score_sample(harness, "date-range-filter/strong")
    weak = score_sample(harness, "date-range-filter/weak")
    for metric_id in (m["id"] for m in strong["metrics"]):
        assert metric(strong, metric_id)["score"] > metric(weak, metric_id)["score"], (
            f"{metric_id} does not separate a good run from a bad one"
        )


def test_invented_component_is_reported_by_name(harness):
    result = score_sample(harness, "date-range-filter/weak")
    unknown = metric(result, "inventory_fidelity")["detail"]["unknown_references"]
    assert "DateRangePicker" in unknown


def test_variant_the_component_does_not_have_is_a_finding(harness):
    result = score_sample(harness, "date-range-filter/weak")
    invalid = metric(result, "inventory_fidelity")["detail"]["invalid_variants"]
    assert any(
        entry["component"] == "Button" and entry["variant"] == "danger" for entry in invalid
    ), invalid


def test_type_parameters_are_not_components(harness, tmp_path):
    """`useRef<HTMLButtonElement>` is a generic. Counting it as an invented
    component would make every TypeScript run look like a hallucinating one."""
    workspace = tmp_path / "ws"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "thing.tsx").write_text(
        'import { Button } from "@/components/ui/button";\n'
        "const ref = useRef<HTMLButtonElement>(null);\n"
        "const rows = new Map<string, Booking>();\n"
        "export const Thing = () => <Button>ok</Button>;\n",
        encoding="utf-8",
    )
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    result = harness.score_run(workspace, case, system)
    assert metric(result, "inventory_fidelity")["detail"]["unknown_references"] == {}


def test_a_documented_gap_earns_part_of_the_credit_not_all(harness):
    result = score_sample(harness, "destructive-confirm/documented-gap")
    surfaces = {s["surface"]: s for s in metric(result, "ladder_outcome")["detail"]["surfaces"]}
    confirmation = surfaces["confirmation"]
    assert confirmation["satisfied_by"] is None
    assert confirmation["documented_gap"] is True
    assert 0 < confirmation["score"] < 1


def test_a_rejected_candidate_named_in_a_document_is_not_a_breach(harness, tmp_path):
    """Design docs list what was rejected. Reading those as violations would
    punish exactly the runs that argued their case."""
    workspace = tmp_path / "ws"
    (workspace / "specs" / "001-x").mkdir(parents=True)
    (workspace / "src").mkdir(parents=True)
    (workspace / "specs" / "001-x" / "design-system.md").write_text(
        "| window.confirm | rejected | unstyled, cannot carry the consequence |\n",
        encoding="utf-8",
    )
    (workspace / "src" / "Row.tsx").write_text(
        'import * as AlertDialog from "@radix-ui/react-alert-dialog";\n'
        'import * as Toast from "@radix-ui/react-toast";\n'
        "export const Row = () => (<AlertDialog.Root><Toast.Root /></AlertDialog.Root>);\n",
        encoding="utf-8",
    )
    case = harness.load_case("destructive-confirm", BENCHMARKS / "cases")
    system = harness.load_system("radix", BENCHMARKS / "systems")
    result = harness.score_run(workspace, case, system)
    surfaces = metric(result, "ladder_outcome")["detail"]["surfaces"]
    assert all(not surface["breaches"] for surface in surfaces)
    assert metric(result, "ladder_outcome")["score"] == 1.0


def test_files_the_harness_provided_are_not_the_runs_work(harness, tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "src").mkdir(parents=True)
    seeded = workspace / "src" / "seeded.tsx"
    seeded.write_text('const c = "#ff8a8a";\n', encoding="utf-8")
    provided = {"src/seeded.tsx": hashlib.sha256(seeded.read_bytes()).hexdigest()}

    case = harness.load_case("login-error-unreadable", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")

    untouched = harness.score_run(workspace, case, system, provided)
    assert untouched["observations"]["files_written"] == 0

    seeded.write_text('const c = "#ff8a8a";\nconst d = "#00ff00";\n', encoding="utf-8")
    touched = harness.score_run(workspace, case, system, provided)
    assert touched["observations"]["files_written"] == 1
    assert metric(touched, "token_discipline")["detail"]["literal_values"] == 2


def test_an_empty_run_is_unscored_rather_than_scored_zero(harness, tmp_path):
    """A run that produced nothing and a run that produced something bad are
    different failures, and the report has to be able to tell them apart."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    result = harness.score_run(workspace, case, system)
    assert result["metrics_applicable"] == 0
    assert result["observations"]["files_written"] == 0


def test_the_arm_never_changes_the_score(harness):
    """Arm-neutrality, the property that makes the comparison mean anything."""
    run_dir = BENCHMARKS / "samples" / "date-range-filter" / "strong"
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    scores = {
        arm: harness.score_run(run_dir / "workspace", case, system, {}, {"arm": arm})["score"]
        for arm in ("unaided", "speckit", "extension")
    }
    assert len(set(scores.values())) == 1, scores


def test_scoring_is_deterministic(harness):
    first = score_sample(harness, "date-range-filter/strong")
    second = score_sample(harness, "date-range-filter/strong")
    assert json.dumps(first["metrics"], sort_keys=True) == json.dumps(
        second["metrics"], sort_keys=True
    )


def test_theme_files_may_hold_the_literal_values(harness, tmp_path):
    """Somewhere has to define the tokens; that file is not a violation."""
    workspace = tmp_path / "ws"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "globals.css").write_text(
        ":root { --destructive: #b91c1c; padding: 13px; }\n", encoding="utf-8"
    )
    (workspace / "src" / "Thing.tsx").write_text(
        'export const Thing = () => <div className="bg-destructive" />;\n', encoding="utf-8"
    )
    case = harness.load_case("login-error-unreadable", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    result = harness.score_run(workspace, case, system)
    assert metric(result, "token_discipline")["detail"]["literal_values"] == 0


# --- the report ---------------------------------------------------------------


def test_report_reports_the_median_and_the_spread(report_module, tmp_path):
    def write(arm: str, index: int, score: float) -> None:
        run_dir = tmp_path / "date-range-filter" / arm / f"x-{index}"
        run_dir.mkdir(parents=True)
        (run_dir / "score.json").write_text(
            json.dumps(
                {
                    "case": "date-range-filter",
                    "arm": arm,
                    "score": score,
                    "metrics": [
                        {"id": "ladder_outcome", "score": score, "applicable": True, "weight": 1.0}
                    ],
                    "observations": {"files_written": 3, "gap_records": []},
                    "run": {"duration_s": 60},
                }
            ),
            encoding="utf-8",
        )

    for index, score in enumerate([0.2, 0.9, 0.5]):
        write("speckit", index, score)
    for index, score in enumerate([0.8, 0.95, 0.85]):
        write("extension", index, score)

    runs = report_module.load(tmp_path)
    grouped = report_module.group(runs)
    assert grouped[("date-range-filter", "speckit")]["score"]["median"] == 0.5
    assert grouped[("date-range-filter", "speckit")]["score"]["max"] == 0.9
    assert grouped[("date-range-filter", "extension")]["score"]["median"] == 0.85

    markdown = report_module.markdown(grouped, runs)
    assert "extension − speckit: **+0.35**" in markdown
    # Three runs per arm is not a measurement, and the report has to say so.
    assert "not as measurements" in markdown


# --- the fixtures are real adapter input --------------------------------------


@pytest.mark.parametrize("system_id", ["shadcn", "radix", "mui"])
def test_benchmark_inventories_answer_through_the_shipped_adapters(
    design, project, write_config, harness, system_id
):
    """The fixtures are not scorer-only data: the extension has to be able to
    read them through the adapter the case names."""
    system = harness.load_system(system_id, BENCHMARKS / "systems")
    target = project / ".design-system" / "inventory.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (Path(system["_dir"]) / system["inventory"]).read_text(encoding="utf-8"), encoding="utf-8"
    )
    write_config({"adapter": system["adapter"]})

    config = design.load_config(project)
    adapter = design.load_adapter(project, config)

    listed = design.run_capability(project, config, adapter, "list_components", {})
    assert listed["available"] is True and listed["data"]

    first = listed["data"][0]["name"]
    one = design.run_capability(project, config, adapter, "component", {"name": first})
    assert one["found"] is True and one["data"]["name"] == first

    hits = design.run_capability(project, config, adapter, "search", {"query": "dialog overlay"})
    assert hits["available"] is True and hits["data"]

    breakpoints = design.run_capability(project, config, adapter, "breakpoints", {})
    assert breakpoints["available"] is True and breakpoints["data"]


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_doing_nothing_does_not_pass_a_case(harness, tmp_path, path):
    """Every case ships a starting point, and a starting point scores something.

    That floor is what a run has to beat before its number means anything, so it
    has to stay well below a pass: a case the seed alone half-answers cannot
    tell two arms apart.
    """
    import shutil

    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    system = harness.load_system(case["design_system"], BENCHMARKS / "systems")
    workspace = tmp_path / "ws"
    shutil.copytree(path.parent / "seed", workspace)

    always = set(case.get("always_score") or [])
    provided = {
        file.relative_to(workspace).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in workspace.rglob("*")
        if file.is_file() and file.relative_to(workspace).as_posix() not in always
    }

    result = harness.score_run(workspace, harness.load_case(case["id"], BENCHMARKS / "cases"),
                               system, provided)
    assert result["score"] < 0.6, f"{case['id']} is half-answered by its own seed"
    assert metric(result, "ladder_outcome")["score"] <= 0.5


# --- the rules a case cites have to exist ------------------------------------


def rules_in_force(harness, system_id: str) -> set[str]:
    """The ids a case on this system may cite: its own file, or the defaults."""
    system = harness.load_system(system_id, BENCHMARKS / "systems")
    if system.get("guidelines"):
        published = yaml.safe_load(
            (Path(system["_dir"]) / system["guidelines"]).read_text(encoding="utf-8")
        )
        return {rule["id"] for rule in published["rules"]}
    defaults = yaml.safe_load((REPO / "guidelines" / "default.yml").read_text(encoding="utf-8"))
    return {rule["id"] for rule in defaults["rules"]}


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_case_cites_rules_that_are_actually_in_force(harness, path):
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    available = rules_in_force(harness, case["design_system"])
    cited = {rule["id"] for rule in case["guidelines"]}
    assert cited <= available, (
        f"{case['id']} cites {sorted(cited - available)}, which nothing in force defines"
    )


@pytest.mark.parametrize(
    "system_id,expected_source",
    [("shadcn", "adapter"), ("mui", "adapter"), ("radix", "default")],
)
def test_guidelines_resolve_from_where_the_cases_assume(
    design, project, write_config, defaults_installed, harness, system_id, expected_source
):
    """One of the three systems publishes nothing, so the extension's own set
    applies there. The cases are written against that split, so it is a contract
    rather than an accident."""
    system = harness.load_system(system_id, BENCHMARKS / "systems")
    inventory = project / ".design-system" / "inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(
        (Path(system["_dir"]) / system["inventory"]).read_text(encoding="utf-8"), encoding="utf-8"
    )

    config = {"adapter": system["adapter"]}
    if system.get("guidelines"):
        published = project / ".design-system" / "guidelines.yml"
        published.write_text(
            (Path(system["_dir"]) / system["guidelines"]).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        config["guidelines"] = {"source": ".design-system/guidelines.yml"}
    write_config(config)

    loaded = design.load_config(project)
    adapter = design.load_adapter(project, loaded)
    resolved = design.resolve_guidelines(project, loaded, adapter)

    assert resolved["source"] == expected_source, resolved["source"]
    assert {rule["id"] for rule in resolved["rules"]} == rules_in_force(harness, system_id)
