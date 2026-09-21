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

    # Skip sequence cases (they have different structure)
    if "features" in case:
        return

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
    is_sequence = "features" in case

    if is_sequence:
        # Sequence cases have features array
        assert case["kind"] in {"ledger-test"}
        assert "features" in case and len(case["features"]) >= 2
        for feature in case["features"]:
            rfc_path = directory / feature.get("rfc", "rfc.md")
            assert rfc_path.exists(), f"RFC not found for {feature['id']}: {rfc_path}"
            seed_path = directory / feature["id"] / "seed"
            assert seed_path.exists(), f"Seed not found for {feature['id']}: {seed_path}"
    else:
        # Single cases have rfc and surfaces
        assert (directory / case.get("rfc", "rfc.md")).exists()
        assert case["kind"] in {"ui-feature", "ui-change", "ui-bug"}
        assert case["surfaces"], "a case with no surfaces scores nothing"

        for surface in case["surfaces"]:
            assert surface["expected_resolution"] in {
                "reuse", "compose-pattern", "compose-components", "extend", "create",
                "reuse-from-ledger",
            }
            assert surface.get("rationale"), f"{surface['id']} rejects rungs without saying why"
            for rule in surface.get("forbidden") or []:
                re.compile(rule["pattern"])
                assert rule["because"]

        for group in case.get("principles", []) + case.get("criteria", []):
            assert group["evidence"], "a rule with no evidence can never be shown to be carried"
            for pattern in group["evidence"]:
                re.compile(pattern)

        for subject in case.get("always_score") or []:
            assert (directory / "seed" / subject).exists(), f"{subject} is not in the seed"

    # Both sequence and single cases have always_score
    for subject in case.get("always_score") or []:
        if is_sequence:
            # For sequences, check in both feature seeds
            found = False
            for feature in case["features"]:
                seed_file = directory / feature["id"] / "seed" / subject
                if seed_file.exists():
                    found = True
                    break
            assert found, f"{subject} is not in any feature seed"
        else:
            assert (directory / "seed" / subject).exists(), f"{subject} is not in the seed"


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_rfc_names_no_components(harness, path):
    """An RFC that names a component has already walked the ladder for the agent."""
    case = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Skip sequence cases (they have different structure)
    if "features" in case:
        return

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
    for m in strong["metrics"]:
        # Skip metrics that don't apply to this case type
        if not m.get("applicable", True):
            continue
        metric_id = m["id"]
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
                    "checks": {
                        "used_the_system": arm == "extension",
                        "avoided_the_shortcuts": True,
                        "invented_nothing": True,
                        "no_literal_values": True,
                        "every_principle_carried": True,
                        "every_criterion_traced": True,
                        "clean_sweep": arm == "extension",
                    },
                    "metrics": [
                        {"id": "ladder_outcome", "score": score, "applicable": True, "weight": 1.0}
                    ],
                    "observations": {"files_written": 3, "gap_records": []},
                    "run": {
                        "duration_s": 60,
                        "usage": {
                            "total_tokens": 100_000 if arm == "speckit" else 250_000,
                            "output_tokens": 9_000,
                            "cost_usd": 0.5 if arm == "speckit" else 1.25,
                            "turns": 8,
                        },
                    },
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

    # The quotable form: a rate, with the denominator next to it.
    assert "| Used what the system already has | 0/3 (0%) | 3/3 (100%) |" in markdown
    # And the price of it, which is the half a benchmark is tempted to omit.
    assert "| extension | 3 | 250,000 |" in markdown
    assert "**2.50×** the tokens of the speckit arm" in markdown


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

    # Skip sequence cases (they have different structure)
    if "features" in case:
        return

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
    if system.get("principles"):
        published = yaml.safe_load(
            (Path(system["_dir"]) / system["principles"]).read_text(encoding="utf-8")
        )
        return {rule["id"] for rule in published["principles"]}
    defaults = yaml.safe_load((REPO / "principles" / "default.yml").read_text(encoding="utf-8"))
    return {rule["id"] for rule in defaults["principles"]}


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.parent.name)
def test_case_cites_rules_that_are_actually_in_force(harness, path):
    case = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Skip sequence cases (they have different structure)
    if "features" in case:
        return

    available = rules_in_force(harness, case["design_system"])
    cited = {rule["id"] for rule in case["principles"]}
    assert cited <= available, (
        f"{case['id']} cites {sorted(cited - available)}, which nothing in force defines"
    )


@pytest.mark.parametrize(
    "system_id,expected_source",
    [("shadcn", "docs"), ("mui", "docs"), ("radix", "default")],
)
def test_principles_resolve_from_where_the_cases_assume(
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
    if system.get("principles"):
        published = project / ".design-system" / "principles.yml"
        published.write_text(
            (Path(system["_dir"]) / system["principles"]).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        config["principles"] = {"source": ".design-system/principles.yml"}
    write_config(config)

    loaded = design.load_config(project)
    adapter = design.load_adapter(project, loaded)
    resolved = design.resolve_principles(project, loaded, adapter)

    assert resolved["principles_source"] == expected_source, resolved["principles_source"]
    assert {rule["id"] for rule in resolved["principles"]} == rules_in_force(harness, system_id)


# --- headline checks ----------------------------------------------------------


def test_checks_are_the_metrics_read_as_pass_or_fail(harness):
    strong = score_sample(harness, "date-range-filter/strong")
    weak = score_sample(harness, "date-range-filter/weak")
    assert all(strong["checks"].values()), strong["checks"]
    assert not any(weak["checks"].values()), weak["checks"]
    assert set(strong["checks"]) == set(harness.CHECK_LABELS)


def test_a_check_with_nothing_to_look_at_is_unanswered(harness, tmp_path):
    """A run that produced nothing must not count as a failing run: k/n would
    then quietly include runs that never happened."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    result = harness.score_run(workspace, case, system)
    assert set(result["checks"].values()) == {None}


def test_clean_sweep_needs_every_check_answered(harness):
    metrics = [
        {"id": "ladder_outcome", "applicable": True,
         "detail": {"surfaces": [{"satisfied_by": ["Calendar"], "breaches": []}]}, "score": 1.0},
        {"id": "inventory_fidelity", "applicable": True,
         "detail": {"unknown_count": 0, "invalid_variants": []}, "score": 1.0},
        {"id": "token_discipline", "applicable": True, "detail": {"literal_values": 0}, "score": 1.0},
        {"id": "principle_coverage", "applicable": True, "detail": {}, "score": 1.0},
        {"id": "criteria_traceability", "applicable": False, "detail": {}, "score": 0.0},
    ]
    checks = harness.headline_checks(metrics)
    assert checks["every_criterion_traced"] is None
    assert checks["clean_sweep"] is None


# --- what a run cost ----------------------------------------------------------


@pytest.fixture(scope="session")
def runner_module():
    spec = importlib.util.spec_from_file_location(
        "bench_runner", BENCHMARKS / "harness" / "runner.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_runner"] = module
    spec.loader.exec_module(module)
    return module


CLAUDE_RESULT = json.dumps(
    {
        "type": "result",
        "total_cost_usd": 0.42,
        "duration_ms": 91000,
        "num_turns": 17,
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 8400,
            "cache_read_input_tokens": 310000,
            "cache_creation_input_tokens": 22000,
        },
    }
)


def test_usage_is_read_from_the_agents_own_accounting(runner_module, tmp_path):
    usage = runner_module.extract_usage(CLAUDE_RESULT, tmp_path)
    assert usage["total_tokens"] == 1200 + 8400 + 310000 + 22000
    assert usage["cost_usd"] == 0.42
    assert usage["turns"] == 17
    assert usage["agent_duration_s"] == 91.0


def test_usage_survives_a_streaming_agent_and_chatter(runner_module, tmp_path):
    stdout = "starting\n" + json.dumps({"type": "assistant"}) + "\n" + CLAUDE_RESULT + "\n"
    usage = runner_module.extract_usage(stdout, tmp_path)
    assert usage["source"] == "agent-stream-json"
    assert usage["output_tokens"] == 8400


def test_any_agent_can_be_counted_through_a_usage_file(runner_module, tmp_path):
    (tmp_path / "usage.json").write_text(
        json.dumps({"input_tokens": 10, "output_tokens": 20, "cost_usd": 0.01, "turns": 3}),
        encoding="utf-8",
    )
    usage = runner_module.extract_usage("not json", tmp_path)
    assert usage == {
        "source": "usage.json",
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "total_tokens": 30,
        "cost_usd": 0.01,
        "turns": 3,
    }


def test_no_accounting_is_reported_as_none_rather_than_zero(runner_module, tmp_path):
    assert runner_module.extract_usage("", tmp_path) is None


# --- blind pairwise judging ---------------------------------------------------


@pytest.fixture(scope="session")
def judge_module():
    spec = importlib.util.spec_from_file_location("bench_judge", BENCHMARKS / "harness" / "judge.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_judge"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def staged_pair(judge_module, tmp_path):
    """The two committed samples, relabelled as two arms of the same case."""
    import shutil

    runs = {}
    for arm, sample in (("speckit", "weak"), ("extension", "strong")):
        target = tmp_path / arm
        shutil.copytree(BENCHMARKS / "samples" / "date-range-filter" / sample, target)
        manifest = json.loads((target / "benchmark.json").read_text(encoding="utf-8"))
        manifest["arm"] = arm
        (target / "benchmark.json").write_text(json.dumps(manifest), encoding="utf-8")
        runs[arm] = judge_module.load_run(target)
    return runs


def test_the_bundle_never_names_the_process(judge_module, harness, staged_pair):
    """Blinding is the whole experiment. One `.specify` path in the bundle and
    the judge is no longer judging the code."""
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    built = judge_module.build_pair(
        staged_pair["speckit"], staged_pair["extension"], case, system, seed="fixed"
    )
    bundle = built["bundle"].lower()
    for giveaway in ("spec-kit", "speckit", ".specify", "design-system.md", "gap record", "ds-00"):
        assert giveaway not in bundle, giveaway
    # Specifications and design documents are not shown at all.
    assert "spec.md" not in bundle
    assert "## validation round" not in bundle
    assert "Submission A" in built["bundle"] and "Submission B" in built["bundle"]


def test_both_orders_shows_the_same_pair_from_both_sides(judge_module, harness, staged_pair):
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    system = harness.load_system("shadcn", BENCHMARKS / "systems")
    first = judge_module.build_pair(
        staged_pair["speckit"], staged_pair["extension"], case, system, seed="fixed"
    )
    swapped = judge_module.build_pair(
        staged_pair["speckit"], staged_pair["extension"], case, system, seed="fixed", swap=True
    )
    assert first["key"]["A"] == swapped["key"]["B"]
    assert first["key"]["B"] == swapped["key"]["A"]
    # Same seed, same draw: the order is reproducible rather than re-rolled.
    again = judge_module.build_pair(
        staged_pair["speckit"], staged_pair["extension"], case, system, seed="fixed"
    )
    assert again["key"] == first["key"]


def test_tooling_mentioned_in_code_is_redacted(judge_module):
    text, count = judge_module.redact("// see .specify/extensions and DS-001 in the gap record\n")
    assert count >= 3
    assert ".specify" not in text and "DS-001" not in text


def test_a_verdict_is_read_from_the_last_json_object(judge_module):
    reply = (
        "Thinking about it: {\"overall\": \"A\"} was my first instinct.\n"
        '```json\n{"design_system_fit":"B","accessibility":"tie",'
        '"requirement_coverage":"B","maintainability":"b","overall":"B","why":"because"}\n```\n'
    )
    verdict = judge_module.parse_verdict(reply)
    assert verdict["overall"] == "B"
    assert verdict["maintainability"] == "B"  # case is normalised
    assert verdict["accessibility"] == "tie"
    assert judge_module.parse_verdict("no json here") is None


def test_sequence_case_loads(harness):
    """Period-filter-sequence case loads and has features array."""
    case = harness.load_case("period-filter-sequence", BENCHMARKS / "cases")
    assert "features" in case
    assert len(case["features"]) >= 2
    assert case["features"][0]["id"] == "feature1"
    assert case["features"][1]["id"] == "feature2"


def test_sequence_case_features_have_rfc_paths(harness):
    """Each feature in sequence has an RFC path."""
    case = harness.load_case("period-filter-sequence", BENCHMARKS / "cases")
    for feature in case.get("features") or []:
        rfc_path = Path(case["_dir"]) / feature["rfc"]
        assert rfc_path.exists(), f"RFC not found: {rfc_path}"


def test_recall_metric_not_applicable_to_single_cases(harness):
    """Recall metric only applies to sequence cases."""
    case = harness.load_case("date-range-filter", BENCHMARKS / "cases")
    result = harness.metric_recall([], case, {})
    assert result["applicable"] is False


def test_recall_metric_applicable_to_sequence_cases(harness):
    """Recall metric applies to sequence cases."""
    case = harness.load_case("period-filter-sequence", BENCHMARKS / "cases")
    result = harness.metric_recall([], case, {})
    # Will be applicable but not scoring without content
    assert "applicable" in result


def test_the_tally_unblinds_by_the_key_and_keeps_empty_arms(judge_module, tmp_path):
    (tmp_path / "keys").mkdir()
    (tmp_path / "pairs").mkdir()

    def pair(name: str, key: dict, verdict: dict | None) -> None:
        (tmp_path / "keys" / f"{name}.json").write_text(
            json.dumps({"pair": name, "case": "date-range-filter", "key": key}), encoding="utf-8"
        )
        directory = tmp_path / "pairs" / name
        directory.mkdir()
        if verdict:
            (directory / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")

    won_by_a = {c: "A" for c in judge_module.CRITERIA} | {"judge": "some-model"}
    won_by_b = {c: "B" for c in judge_module.CRITERIA} | {"judge": "some-model"}
    pair("one", {"A": "extension", "B": "speckit"}, won_by_a)
    pair("two", {"A": "speckit", "B": "extension"}, won_by_b)  # same winner, sides swapped
    pair("three", {"A": "extension", "B": "speckit"}, None)

    result = judge_module.tally(tmp_path)
    assert result["pairs"] == 2 and result["unjudged"] == 1
    assert result["criteria"]["overall"] == {"extension": 2}
    # The losing arm keeps its column, because "won nothing" is the finding.
    assert result["arms"] == ["extension", "speckit"]
