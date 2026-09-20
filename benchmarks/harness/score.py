#!/usr/bin/env python3
"""Score one benchmark run against the case it was given.

Deterministic on purpose: the agent run is the only stochastic part of a
benchmark, so everything after it is a pure function of the files on disk. Run
the same workspace through this twice and you get the same numbers, which is
what makes a with/without comparison worth quoting.

Every metric is arm-neutral. Nothing here looks for an artifact only the
extension can produce, because a metric that does that measures which arm ran
rather than what came out of it. `artifacts` records those observations
separately, unscored.

    python benchmarks/harness/score.py --run benchmarks/results/<...>/
    python benchmarks/harness/score.py --workspace path/to/ws --case date-range-filter --arm speckit

One JSON object on stdout, like the rest of this repo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - same failure mode as design.py
    print(json.dumps({"error": "PyYAML is required: pip install pyyaml"}))
    sys.exit(1)

HARNESS = Path(__file__).resolve().parent
BENCHMARKS = HARNESS.parent

DOC_EXT = {".md", ".mdx"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}
SKIP_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", ".venv", "__pycache__",
    ".specify", ".claude", ".design-system", "coverage", ".turbo", ".cache",
}
# Files that define the theme are where literal values are supposed to live.
THEME_FILES = re.compile(
    r"(?:globals|theme|tokens|tailwind\.config|design-tokens)[.\w-]*\.(?:css|scss|ts|js|json)$"
)
TEST_PATH = re.compile(r"(?:^|/)(?:tests?|__tests__|e2e)/|\.(?:test|spec)\.[jt]sx?$")

# Names that turn up in React code and are nobody's design system component.
BUILTIN_IGNORED = {
    "react", "fragment", "suspense", "strictmode", "errorboundary", "profiler",
    "app", "main", "root", "layout", "page", "provider", "providers", "children",
}

# The lookbehind is what separates a JSX element from a type parameter:
# `useRef<HTMLButtonElement>` has an identifier character before the angle
# bracket, `<Button ...>` does not.
TAG = re.compile(
    r"(?<![A-Za-z0-9_$])<\s*([A-Z][A-Za-z0-9_]*)(?:\.([A-Z][A-Za-z0-9_]*))?([^>]*)>",
    re.DOTALL,
)
DOM_TYPE = re.compile(r"^(?:HTML|SVG)[A-Za-z]*Element$")
INLINE_CODE = re.compile(r"`([A-Za-z][A-Za-z0-9_.]*)`")
IMPORT = re.compile(
    r"""import\s+(?P<clause>[^'";]+?)\s+from\s+['"](?P<module>[^'"]+)['"]""", re.DOTALL
)
NAMESPACE_IMPORT = re.compile(
    r"""import\s+\*\s+as\s+(?P<name>[A-Za-z_$][\w$]*)\s+from\s+['"](?P<module>[^'"]+)['"]"""
)
DEFINED = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function|class|const|let|var)\s+([A-Z][A-Za-z0-9_]*)",
    re.MULTILINE,
)
VARIANT_ATTR = re.compile(r"""\bvariant\s*=\s*["']([A-Za-z0-9_-]+)["']""")

HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
FUNC_COLOR = re.compile(r"\b(?:rgba?|hsla?)\(\s*\d")
PX = re.compile(r"(?<![\w.-])(\d+(?:\.\d+)?)px\b")
CAMEL = re.compile(r"^[A-Z][A-Za-z0-9]*$")

DEFAULT_WEIGHTS = {
    "inventory_fidelity": 1.0,
    "ladder_outcome": 1.0,
    "token_discipline": 1.0,
    "guideline_coverage": 1.0,
    "criteria_traceability": 1.0,
}


# --- loading ------------------------------------------------------------------


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def content_words(phrase: str) -> set[str]:
    stop = {
        "a", "an", "the", "of", "for", "and", "or", "to", "in", "on", "it", "is",
        "that", "this", "with", "by", "at", "as", "its", "into", "from", "they",
    }
    return {w for w in re.findall(r"[a-z]+", phrase.lower()) if w not in stop and len(w) > 2}


def load_case(case_id: str, cases_dir: Path) -> dict:
    path = cases_dir / case_id / "case.yml"
    if not path.exists():
        raise FileNotFoundError(f"no such case: {path}")
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    case["_dir"] = str(path.parent)
    return case


def load_system(system_id: str, systems_dir: Path) -> dict:
    directory = systems_dir / system_id
    meta = yaml.safe_load((directory / "system.yml").read_text(encoding="utf-8"))
    inventory = json.loads((directory / meta["inventory"]).read_text(encoding="utf-8"))
    meta["_dir"] = str(directory)
    meta["_inventory"] = inventory
    return meta


def known_names(inventory: dict) -> tuple[set[str], dict[str, str], dict[str, dict]]:
    """Everything the design system offers, and which parent each part belongs to."""
    known: set[str] = set()
    parent: dict[str, str] = {}
    detail: dict[str, dict] = {}
    for kind in ("components", "patterns"):
        for entry in inventory.get(kind) or []:
            name = entry.get("name")
            if not name:
                continue
            key = normalize(name)
            known.add(key)
            parent[key] = name
            detail[key] = entry
            for part in entry.get("parts") or []:
                part_key = normalize(part)
                known.add(part_key)
                parent[part_key] = name
    return known, parent, detail


# --- file collection ----------------------------------------------------------


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(workspace: Path, provided: dict[str, str] | None) -> list[dict]:
    """Every file the run produced or changed, classified.

    Files the harness itself put in the workspace are skipped while they are
    untouched, so the design system inventory and the RFC never count as the
    run's own work. A provided file that was edited is scored: changing it was
    the run's decision.
    """
    provided = provided or {}
    files: list[dict] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(workspace).parts[:-1]):
            continue
        suffix = path.suffix.lower()
        if suffix not in DOC_EXT and suffix not in CODE_EXT:
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel in provided and provided[rel] == digest(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        files.append(
            {
                "path": rel,
                "text": text,
                "kind": "doc" if suffix in DOC_EXT else "code",
                "is_test": bool(TEST_PATH.search(rel)),
                "is_theme": bool(THEME_FILES.search(rel)),
                "is_gap_record": "gap" in Path(rel).name.lower() and suffix in DOC_EXT,
            }
        )
    return files


def joined(files: Iterable[dict], **filters: Any) -> str:
    return "\n".join(
        f["text"] for f in files if all(f.get(k) == v for k, v in filters.items())
    )


# --- references ---------------------------------------------------------------


def imports(text: str) -> dict[str, str]:
    """identifier -> module it was imported from."""
    found: dict[str, str] = {}
    for match in NAMESPACE_IMPORT.finditer(text):
        found[match.group("name")] = match.group("module")
    for match in IMPORT.finditer(text):
        module = match.group("module")
        clause = match.group("clause")
        if clause.strip().startswith("*"):
            continue
        braced = re.search(r"\{(.+?)\}", clause, re.DOTALL)
        names: list[str] = []
        if braced:
            names += [part.split(" as ")[-1].strip() for part in braced.group(1).split(",")]
        default = clause.split("{")[0].strip().rstrip(",").strip()
        if default and re.fullmatch(r"[A-Za-z_$][\w$]*", default):
            names.append(default)
        for name in names:
            if name:
                found[name] = module
    return found


def references(files: list[dict]) -> tuple[dict[str, int], dict[str, str], set[str], dict[str, str]]:
    """Component-ish names the run refers to, with where each was imported from."""
    refs: dict[str, int] = {}
    origin: dict[str, str] = {}
    defined: set[str] = set()
    compound: dict[str, str] = {}

    def note(raw: str) -> None:
        refs[raw] = refs.get(raw, 0) + 1

    for entry in files:
        text = entry["text"]
        if entry["kind"] == "code":
            found = imports(text)
            for name, module in found.items():
                origin.setdefault(name, module)
            for name in DEFINED.findall(text):
                defined.add(normalize(name))
            defined.add(normalize(Path(entry["path"]).stem))
        for match in TAG.finditer(text):
            root, member, _ = match.groups()
            note(root)
            if member:
                note(f"{root}{member}")
                compound[f"{root}{member}"] = root
        if entry["kind"] == "doc":
            for token in INLINE_CODE.findall(text):
                head = token.split(".")[0]
                if CAMEL.match(head):
                    note(head)
                    if "." in token and CAMEL.match(token.split(".")[1] or "x"):
                        note(token.replace(".", ""))
                        compound[token.replace(".", "")] = head
    return refs, origin, defined, compound


def ds_module(module: str, pattern: re.Pattern | None) -> bool:
    return bool(pattern.search(module)) if pattern else False


# --- metrics ------------------------------------------------------------------


def metric_inventory_fidelity(files, case, system) -> dict:
    inventory = system["_inventory"]
    known, parent, detail = known_names(inventory)
    refs, origin, defined, compound = references(files)
    ignored = {normalize(n) for n in (system.get("ignore_refs") or [])}
    ignored |= {normalize(n) for n in (case.get("ignore_refs") or [])}
    ignored |= BUILTIN_IGNORED
    ds_pattern = re.compile(system["ds_module_pattern"]) if system.get("ds_module_pattern") else None

    declared_new = set()
    for entry in files:
        if entry["is_gap_record"]:
            for token in INLINE_CODE.findall(entry["text"]) + re.findall(
                r"^#\s+(?:Gap(?:\srecord)?:\s*)?(.+)$", entry["text"], re.MULTILINE
            ):
                head = token.strip().split(".")[0]
                if CAMEL.match(head):
                    declared_new.add(normalize(head))

    total = 0
    unknown: dict[str, int] = {}
    for raw, count in refs.items():
        key = normalize(raw)
        if key in ignored or re.fullmatch(r"[a-z].*", raw) or raw.endswith("Icon"):
            continue
        if DOM_TYPE.match(raw):
            continue
        module = origin.get(raw)
        from_ds = module is None or ds_module(module, ds_pattern)
        if module is not None and not from_ds:
            # Imported from somewhere else entirely: a third-party component is
            # a dependency decision, not a claim about the design system.
            continue
        total += count
        root = compound.get(raw)
        if key in known or key in defined or key in declared_new:
            continue
        if root and normalize(root) in known:
            # `Toast.Root` under a namespace import: the system supplies the
            # component, the member is its own API.
            continue
        unknown[raw] = count

    # A variant the component does not have is the same failure with a smaller
    # blast radius: the name exists, the API does not.
    bad_variants: list[dict] = []
    for entry in files:
        if entry["kind"] != "code":
            continue
        for match in TAG.finditer(entry["text"]):
            root, member, attrs = match.groups()
            key = normalize(root if not member else f"{root}{member}")
            component = detail.get(key) or detail.get(normalize(root))
            if not component:
                continue
            allowed = component.get("variants") or []
            if not allowed:
                continue
            for value in VARIANT_ATTR.findall(attrs or ""):
                if value not in allowed:
                    bad_variants.append(
                        {"component": component["name"], "variant": value, "file": entry["path"]}
                    )

    unknown_count = sum(unknown.values())
    denominator = total + len(bad_variants)
    applicable = denominator > 0
    score = 0.0
    if applicable:
        score = 1 - (unknown_count + len(bad_variants)) / denominator
    return {
        "id": "inventory_fidelity",
        "question": "Does the work only use components and APIs the system actually has?",
        "applicable": applicable,
        "score": round(max(0.0, score), 4),
        "detail": {
            "references_scored": total,
            "unknown_references": unknown,
            "unknown_count": unknown_count,
            "invalid_variants": bad_variants,
            "declared_new": sorted(declared_new),
        },
    }


def _referenced(refs: dict[str, int], parent: dict[str, str], name: str) -> bool:
    target = normalize(name)
    for raw in refs:
        key = normalize(raw)
        if key == target or parent.get(key) and normalize(parent[key]) == target:
            return True
    return False


def _mentions(text: str, phrase: str, ratio: float = 0.6) -> bool:
    words = content_words(phrase)
    if not words:
        return False
    lowered = text.lower()
    hits = sum(1 for word in words if word in lowered)
    return hits / len(words) >= ratio


def metric_ladder_outcome(files, case, system) -> dict:
    known, parent, _ = known_names(system["_inventory"])
    refs, _, _, _ = references(files)
    code = joined(files, kind="code")
    gap_text = "\n".join(f["text"] for f in files if f["is_gap_record"])

    results = []
    for surface in case["surfaces"]:
        satisfied_by = surface.get("satisfied_by") or []
        matched: list[str] | None = None
        for candidate in satisfied_by:
            if all(_referenced(refs, parent, name) for name in candidate):
                matched = candidate
                break
        breaches = [
            {"pattern": rule["pattern"], "because": rule["because"]}
            for rule in surface.get("forbidden") or []
            if re.search(rule["pattern"], code)
        ]
        documented = bool(gap_text) and _mentions(gap_text, surface["capability"], ratio=0.5)
        base = 1.0 if matched else (0.35 if documented else 0.0)
        score = max(0.0, base - (0.5 if breaches else 0.0))
        results.append(
            {
                "surface": surface["id"],
                "expected_resolution": surface["expected_resolution"],
                "satisfied_by": matched,
                "documented_gap": documented,
                "breaches": breaches,
                "score": round(score, 4),
            }
        )

    applicable = bool(results) and bool(refs or code)
    score = sum(r["score"] for r in results) / len(results) if results and applicable else 0.0
    return {
        "id": "ladder_outcome",
        "question": "Did each surface land on what the system already offers, or below it?",
        "applicable": applicable,
        "score": round(score, 4),
        "detail": {"surfaces": results},
    }


def metric_token_discipline(files, case, system) -> dict:
    allow = set(system.get("raw_value_allow") or []) | set(
        (case.get("tokens") or {}).get("allow_raw") or []
    )
    signals = [re.compile(pattern) for pattern in system.get("token_signals") or []]

    violations: list[dict] = []
    signal_count = 0
    scanned = 0
    for entry in files:
        if entry["kind"] != "code" or entry["is_theme"]:
            continue
        scanned += 1
        text = entry["text"]
        for pattern in signals:
            signal_count += len(pattern.findall(text))
        for match in HEX.finditer(text):
            violations.append({"file": entry["path"], "value": match.group(0), "kind": "colour"})
        for match in FUNC_COLOR.finditer(text):
            violations.append({"file": entry["path"], "value": match.group(0), "kind": "colour"})
        for match in PX.finditer(text):
            value = f"{match.group(1)}px"
            if value in allow or match.group(1) in allow:
                continue
            violations.append({"file": entry["path"], "value": value, "kind": "length"})

    denominator = signal_count + len(violations)
    applicable = scanned > 0 and denominator > 0
    score = signal_count / denominator if applicable else 0.0
    return {
        "id": "token_discipline",
        "question": "Does styling go through the system's own scale, or around it?",
        "applicable": applicable,
        "score": round(score, 4),
        "detail": {
            "code_files_scanned": scanned,
            "token_signals": signal_count,
            "literal_values": len(violations),
            "examples": violations[:20],
        },
    }


def metric_guideline_coverage(files, case, system) -> dict:
    everything = joined(files)
    results = []
    for rule in case.get("guidelines") or []:
        hit = next((p for p in rule["evidence"] if re.search(p, everything)), None)
        results.append({"id": rule["id"], "covered": hit is not None, "matched": hit})
    applicable = bool(results) and bool(everything.strip())
    covered = sum(1 for r in results if r["covered"])
    return {
        "id": "guideline_coverage",
        "question": "Do the rules in force show up in the work?",
        "applicable": applicable,
        "score": round(covered / len(results), 4) if results and applicable else 0.0,
        "detail": {"covered": covered, "total": len(results), "rules": results},
    }


def metric_criteria_traceability(files, case, system) -> dict:
    scope = "\n".join(f["text"] for f in files if f["kind"] == "doc" or f["is_test"])
    fallback = False
    if not scope.strip():
        scope, fallback = joined(files), True
    results = []
    for criterion in case.get("criteria") or []:
        hit = next((p for p in criterion["evidence"] if re.search(p, scope)), None)
        results.append({"criterion": criterion["text"], "traced": hit is not None, "matched": hit})
    applicable = bool(results) and bool(scope.strip())
    traced = sum(1 for r in results if r["traced"])
    return {
        "id": "criteria_traceability",
        "question": "Did the RFC's acceptance criteria survive into the work?",
        "applicable": applicable,
        "score": round(traced / len(results), 4) if results and applicable else 0.0,
        "detail": {
            "traced": traced,
            "total": len(results),
            "scope": "code and docs" if fallback else "docs and tests",
            "criteria": results,
        },
    }


METRICS = (
    metric_inventory_fidelity,
    metric_ladder_outcome,
    metric_token_discipline,
    metric_guideline_coverage,
    metric_criteria_traceability,
)


# --- observations (never scored) ----------------------------------------------

VALIDATION_ROUND = re.compile(r"^##\s+Validation round\s+(\d+)", re.MULTILINE)
FINDING_OPEN = re.compile(r"^- \[ \]\s+(DS-F-\d+)", re.MULTILINE)
FINDING_DONE = re.compile(r"^- \[[xX]\]\s+(DS-F-\d+)", re.MULTILINE)
REQUIREMENT = re.compile(r"\bDS-\d{3}\b")


def observations(workspace: Path, files: list[dict]) -> dict:
    docs = joined(files, kind="doc")
    design_docs = [f for f in files if Path(f["path"]).name == "design-system.md"]
    design = "\n".join(f["text"] for f in design_docs)
    return {
        "files_written": len(files),
        "code_files": sum(1 for f in files if f["kind"] == "code"),
        "doc_files": sum(1 for f in files if f["kind"] == "doc"),
        "test_files": sum(1 for f in files if f["is_test"]),
        "has_spec": any(Path(f["path"]).name == "spec.md" for f in files),
        "has_plan": any(Path(f["path"]).name == "plan.md" for f in files),
        "has_tasks": any(Path(f["path"]).name == "tasks.md" for f in files),
        "has_design_doc": bool(design_docs),
        "gap_records": [f["path"] for f in files if f["is_gap_record"]],
        "ledger_entries": _ledger_entries(workspace),
        "validation_rounds": len(set(VALIDATION_ROUND.findall(design))),
        "findings_open": len(set(FINDING_OPEN.findall(design))),
        "findings_closed": len(set(FINDING_DONE.findall(design))),
        "numbered_requirements": len(set(REQUIREMENT.findall(docs))),
    }


def _ledger_entries(workspace: Path) -> int:
    path = workspace / ".specify" / "memory" / "design-decisions.yml"
    if not path.exists():
        return 0
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return 0
    return len(data.get("decisions") or [])


# --- scoring ------------------------------------------------------------------


# --- headline checks ----------------------------------------------------------
#
# The metrics are continuous, which is right for scoring and useless for saying
# anything out loud. These are the same evidence read as pass or fail, because
# "used what the system already had in 9 of 10 runs" is a claim someone can
# check, and "0.82 on the ladder metric" is not.
#
# A check is None when the evidence for it is not there at all, so a run that
# produced nothing never counts as a pass or as a failure.

CHECK_LABELS = {
    "used_the_system": "Every surface resolved to something the system already offers",
    "avoided_the_shortcuts": "No shortcut the case names as wrong",
    "invented_nothing": "No component or variant the system does not have",
    "no_literal_values": "No literal colour or length outside the theme",
    "every_guideline_carried": "Every guideline in force shows up in the work",
    "every_criterion_traced": "Every acceptance criterion survived into the work",
    "clean_sweep": "All of the above, in one run",
}


def headline_checks(metrics: list[dict]) -> dict:
    by_id = {metric["id"]: metric for metric in metrics}

    def applicable(metric_id: str) -> dict | None:
        metric = by_id.get(metric_id)
        return metric if metric and metric["applicable"] else None

    checks: dict[str, bool | None] = {}

    ladder = applicable("ladder_outcome")
    surfaces = ladder["detail"]["surfaces"] if ladder else []
    checks["used_the_system"] = (
        all(surface["satisfied_by"] for surface in surfaces) if ladder else None
    )
    checks["avoided_the_shortcuts"] = (
        not any(surface["breaches"] for surface in surfaces) if ladder else None
    )

    fidelity = applicable("inventory_fidelity")
    checks["invented_nothing"] = (
        fidelity["detail"]["unknown_count"] == 0 and not fidelity["detail"]["invalid_variants"]
        if fidelity
        else None
    )

    tokens = applicable("token_discipline")
    checks["no_literal_values"] = tokens["detail"]["literal_values"] == 0 if tokens else None

    guidelines = applicable("guideline_coverage")
    checks["every_guideline_carried"] = guidelines["score"] == 1.0 if guidelines else None

    criteria = applicable("criteria_traceability")
    checks["every_criterion_traced"] = criteria["score"] == 1.0 if criteria else None

    answered = [value for value in checks.values() if value is not None]
    checks["clean_sweep"] = all(answered) if len(answered) == len(checks) else None
    return checks


def score_run(
    workspace: Path,
    case: dict,
    system: dict,
    provided: dict[str, str] | None = None,
    meta: dict | None = None,
) -> dict:
    files = collect(workspace, provided)
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(case.get("weights") or {})

    metrics = [metric(files, case, system) for metric in METRICS]
    for metric in metrics:
        metric["weight"] = weights.get(metric["id"], 1.0)

    scored = [m for m in metrics if m["applicable"]]
    total = (
        round(
            sum(m["score"] * m["weight"] for m in scored) / sum(m["weight"] for m in scored), 4
        )
        if scored
        else 0.0
    )

    return {
        "case": case["id"],
        "design_system": case["design_system"],
        "arm": (meta or {}).get("arm", "unknown"),
        "workspace": str(workspace),
        "score": total,
        "metrics_applicable": len(scored),
        "checks": headline_checks(metrics),
        "metrics": metrics,
        "observations": observations(workspace, files),
        "run": meta or {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="a run directory written by runner.py")
    parser.add_argument("--workspace", help="score a workspace directly")
    parser.add_argument("--case", help="case id, when --workspace is used")
    parser.add_argument("--arm", default="unknown")
    parser.add_argument("--cases-dir", default=str(BENCHMARKS / "cases"))
    parser.add_argument("--systems-dir", default=str(BENCHMARKS / "systems"))
    parser.add_argument("--out", help="also write the JSON here")
    args = parser.parse_args()

    provided: dict[str, str] | None = None
    meta: dict = {"arm": args.arm}

    if args.run:
        run_dir = Path(args.run).resolve()
        manifest_path = run_dir / "benchmark.json"
        if not manifest_path.exists():
            print(json.dumps({"error": f"no benchmark.json in {run_dir}"}))
            sys.exit(1)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        workspace = (run_dir / manifest.get("workspace", "workspace")).resolve()
        provided = manifest.get("provided") or {}
        meta = {k: v for k, v in manifest.items() if k not in {"provided"}}
        case_id = manifest["case"]
    elif args.workspace and args.case:
        workspace = Path(args.workspace).resolve()
        case_id = args.case
        manifest_path = workspace.parent / "benchmark.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            provided = manifest.get("provided") or {}
    else:
        parser.error("give --run, or --workspace together with --case")

    case = load_case(case_id, Path(args.cases_dir))
    system = load_system(case["design_system"], Path(args.systems_dir))
    result = score_run(workspace, case, system, provided, meta)

    payload = json.dumps(result, indent=2, sort_keys=False)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    elif args.run:
        (Path(args.run) / "score.json").write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
