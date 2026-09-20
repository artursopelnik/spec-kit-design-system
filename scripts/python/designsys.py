#!/usr/bin/env python3
"""Design system integration for spec-kit.

All logic lives here; the bash scripts are thin shims. Callers without bash can
invoke this module directly and get identical behaviour.

Subcommands:
    gate                     prerequisites + resolved config as one JSON object
    query <capability> ...   invoke a capability against the design system CLI
    rules                    the rules in force: baseline plus project house rules
    ledger lookup <phrase>   find prior decisions for a capability
    ledger record <file>     append a decision (JSON object on disk or '-')
    ledger list              all active decisions
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

EXT_ID = "designsys"
CONFIG_NAME = "designsys-config.yml"
LOCAL_CONFIG_NAME = "designsys-config.local.yml"
LEDGER_NAME = "design-decisions.yml"
DESIGN_DOC_NAME = "design-system.md"
BASELINE_NAME = "baseline.yml"
HOUSE_RULES_NAME = "rules.yml"

# What a rule can apply to. A feature declares which of these it involves, and
# only the matching rules reach its spec.
SURFACE_KINDS = ["interactive", "layout", "text", "media", "motion", "any"]

# Capabilities the commands are written against. An adapter maps these to real
# invocations; anything unmapped is reported as unavailable rather than faked.
CAPABILITIES = [
    "describe",
    "search",
    "list_components",
    "component",
    "pattern",
    "tokens",
    # Breakpoints are their own query because "use our breakpoints" is
    # unenforceable unless the agent can find out what they actually are.
    "breakpoints",
    # The design system's own principles and guidance. Systems publish this as
    # prose rather than as rules, so it cannot be checked mechanically, but it
    # outranks anything this extension assumes on their behalf.
    "guidelines",
    "extend",
    "report_gap",
]

STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "and", "or", "with", "in", "on",
    "that", "this", "is", "are", "be", "by", "as", "at", "from", "it",
}


def die(message: str, code: int = 1) -> None:
    print(f"[designsys] {message}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj: Any) -> None:
    """One compact JSON object on stdout, per spec-kit script convention."""
    json.dump(obj, sys.stdout, separators=(",", ":"), default=str)
    sys.stdout.write("\n")


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        die(
            "PyYAML is required to read design system configuration. "
            "Install it into the interpreter running these scripts (pip install pyyaml)."
        )
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    except Exception as exc:  # malformed YAML is a real error, not an empty config
        die(f"could not parse {path}: {exc}")
    return {}


def dump_yaml(path: Path, data: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True, width=100)


# --- location ----------------------------------------------------------------


def repo_root() -> Path:
    env = os.environ.get("SPECIFY_INIT_DIR")
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".specify").is_dir():
            return candidate
    return here


def ext_dir(root: Path) -> Path:
    return root / ".specify" / "extensions" / EXT_ID


def feature_dir(root: Path) -> Path | None:
    """Resolve the active feature. `.specify/feature.json` is the source of truth;
    spec-kit does not derive this from git."""
    env = os.environ.get("SPECIFY_FEATURE_DIRECTORY")
    if env:
        return Path(env) if Path(env).is_absolute() else root / env

    pointer = root / ".specify" / "feature.json"
    if pointer.is_file():
        try:
            data = json.loads(pointer.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        value = data.get("feature_directory")
        if value:
            return Path(value) if Path(value).is_absolute() else root / value
    return None


# --- configuration -----------------------------------------------------------


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        elif value not in (None, ""):
            result[key] = value
    return result


# Environment overrides, mapped to their dotted config path. Matches spec-kit's
# own SPECKIT_<EXT>_<SETTING> convention.
ENV_OVERRIDES = {
    "SPECKIT_DESIGNSYS_ADAPTER": ("adapter", str),
    "SPECKIT_DESIGNSYS_BIN": ("bin", str),
    "SPECKIT_DESIGNSYS_CWD": ("cwd", str),
    "SPECKIT_DESIGNSYS_GATE_ENFORCE": ("gate.enforce", bool),
    "SPECKIT_DESIGNSYS_REQUIRE_GAP_REPORT": ("gate.require_gap_report", bool),
    "SPECKIT_DESIGNSYS_MIN_CANDIDATES": ("gate.min_candidates_considered", int),
    "SPECKIT_DESIGNSYS_LEDGER_ENABLED": ("ledger.enabled", bool),
    "SPECKIT_DESIGNSYS_MATCH_THRESHOLD": ("ledger.match_threshold", float),
    "SPECKIT_DESIGNSYS_FORBID_RAW_VALUES": ("audit.forbid_raw_values", bool),
}


def coerce(value: str, kind: type) -> Any:
    if kind is bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    try:
        return kind(value)
    except ValueError:
        die(f"could not read '{value}' as {kind.__name__}")


def set_path(target: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def load_config(root: Path) -> dict:
    """Resolution order: extension defaults -> project config -> local override
    -> environment. This mirrors spec-kit's own layering, so a developer can
    point at a scratch design system without touching the committed config."""
    config = load_yaml(ext_dir(root) / "extension.yml").get("config", {}).get("defaults", {})
    config = deep_merge(config, load_yaml(ext_dir(root) / CONFIG_NAME))
    config = deep_merge(config, load_yaml(ext_dir(root) / LOCAL_CONFIG_NAME))

    for variable, (dotted, kind) in ENV_OVERRIDES.items():
        raw = os.environ.get(variable)
        if raw not in (None, ""):
            set_path(config, dotted, coerce(raw, kind))

    return config


def load_adapter(root: Path, config: dict) -> dict:
    adapter_id = config.get("adapter") or "static-json"
    if adapter_id == "custom":
        adapter = {"id": "custom", "name": "custom", "capabilities": {}}
    else:
        path = ext_dir(root) / "adapters" / f"{adapter_id}.yml"
        adapter = load_yaml(path)
        if not adapter:
            die(f"adapter '{adapter_id}' not found at {path}")

    # Project config may override the binary, the inventory path, and individual
    # capabilities.
    if config.get("bin"):
        adapter["bin"] = config["bin"]
    if config.get("source"):
        adapter["source"] = config["source"]
    if config.get("registries"):
        adapter["registries"] = config["registries"]
    if config.get("capabilities"):
        adapter["capabilities"] = deep_merge(
            adapter.get("capabilities", {}), config["capabilities"]
        )
    return adapter


def mapped_capabilities(adapter: dict) -> list[str]:
    mapped = adapter.get("capabilities") or {}
    return [name for name in CAPABILITIES if name in mapped and mapped[name]]


# Probed in this order; the first mapped one is used. `describe` is cheapest and
# most informative where a CLI self-describes.
PROBE_ORDER = ["describe", "list_components", "search", "component"]
PROBE_PARAMS = {"search": {"query": "button"}, "component": {"name": "Button"}}


def probe_adapter(root: Path, config: dict, adapter: dict) -> dict:
    """Actually reach the design system before reporting what it can do.

    Reading capabilities off the adapter YAML alone would report a full set for
    a CLI that is not installed, which would make the commands' fail-closed
    guard unreachable: the gate would pass precisely when it cannot check
    anything. So this spends one call to find out.
    """
    mapped = mapped_capabilities(adapter)
    if not mapped:
        return {"capabilities": [], "reachable": False, "reason": "adapter maps no capabilities"}

    probe = next((name for name in PROBE_ORDER if name in mapped), mapped[0])
    result = run_capability(root, config, adapter, probe, dict(PROBE_PARAMS.get(probe, {})))

    if not result.get("available"):
        return {
            "capabilities": [],
            "reachable": False,
            "probed": probe,
            "reason": result.get("reason", "design system could not be reached"),
        }
    return {"capabilities": mapped, "reachable": True, "probed": probe}


# --- capability dispatch -----------------------------------------------------


def substitute(args: list[str], params: dict[str, Any]) -> list[str]:
    """Expand {placeholders}.

    A list-valued parameter splices into separate argv elements, so multiple
    registries reach the CLI as multiple arguments rather than one space-joined
    blob that matches nothing.

    A placeholder with no value drops its argument, and the flag immediately
    before it, if any. Dropping only the value would leave a dangling flag that
    swallows whatever argument follows it.
    """
    out: list[str] = []
    for arg in args:
        whole = re.fullmatch(r"\{([a-z_]+)\}", arg)
        if whole:
            value = params.get(whole.group(1))
            if isinstance(value, (list, tuple)):
                out.extend(str(item) for item in value)
                continue
            if value in (None, ""):
                if out and out[-1].startswith("-"):
                    out.pop()
                continue
            out.append(str(value))
            continue

        def replace(match: re.Match) -> str:
            found = params.get(match.group(1))
            if isinstance(found, (list, tuple)):
                return " ".join(str(item) for item in found)
            return "" if found is None else str(found)

        out.append(re.sub(r"\{([a-z_]+)\}", replace, arg))
    return out


def dig(data: Any, path: str) -> Any:
    if not path:
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def run_capability(
    root: Path, config: dict, adapter: dict, capability: str, params: dict[str, str]
) -> dict:
    spec = (adapter.get("capabilities") or {}).get(capability)
    if not spec:
        return {
            "capability": capability,
            "available": False,
            "reason": f"adapter '{adapter.get('id')}' does not map '{capability}'",
        }

    # Paths and subprocesses resolve against the same base, so `cwd` works for
    # monorepos whichever kind of capability the adapter maps.
    base = root / config["cwd"] if config.get("cwd") else root

    # File-backed capability, such as a static inventory.
    if spec.get("read_file"):
        target = substitute([spec["read_file"]], {**params, "source": adapter.get("source", "")})
        path = base / target[0] if target else None
        if not path or not path.is_file():
            return {"capability": capability, "available": False, "reason": f"{path} not found"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return {"capability": capability, "available": False, "reason": str(exc)}
        result = dig(data, spec.get("result_path", ""))

        key_field = spec.get("key_field")
        wanted = params.get("name")
        if key_field and wanted and isinstance(result, list):
            match = next(
                (
                    item
                    for item in result
                    if isinstance(item, dict)
                    and str(item.get(key_field, "")).lower() == wanted.lower()
                ),
                None,
            )
            return {
                "capability": capability,
                "available": True,
                "found": match is not None,
                "source": str(path),
                "data": match,
            }

        if spec.get("match_fields") and wanted is None and params.get("query"):
            query_tokens = set(normalize(params["query"]))
            hits = []
            for section in spec.get("search_keys") or []:
                for item in data.get(section) or []:
                    if not isinstance(item, dict):
                        continue
                    haystack = " ".join(
                        str(item.get(field, "")) for field in spec["match_fields"]
                    )
                    overlap = query_tokens & set(normalize(haystack))
                    if overlap:
                        hits.append(
                            {"kind": section, "score": len(overlap), **item}
                        )
            hits.sort(key=lambda entry: entry["score"], reverse=True)
            return {
                "capability": capability,
                "available": True,
                "found": bool(hits),
                "source": str(path),
                "data": hits[:20],
            }

        return {
            "capability": capability,
            "available": True,
            "source": str(path),
            "data": result,
        }

    binary = adapter.get("bin") or ""
    if not binary:
        return {"capability": capability, "available": False, "reason": "no binary configured"}

    merged: dict[str, Any] = {**(spec.get("defaults") or {}), **params}
    if adapter.get("registries"):
        merged.setdefault("registries", list(adapter["registries"]))

    argv = shlex.split(binary)
    argv += substitute(list(spec.get("args") or []), merged)
    argv += list(adapter.get("global_args") or [])

    try:
        proc = subprocess.run(
            argv, cwd=base, capture_output=True, text=True, timeout=120, check=False
        )
    except FileNotFoundError:
        return {
            "capability": capability,
            "available": False,
            "reason": f"'{argv[0]}' not found. Is the design system CLI installed?",
        }
    except subprocess.TimeoutExpired:
        return {"capability": capability, "available": False, "reason": "CLI timed out after 120s"}

    raw = proc.stdout.strip()
    parsed: Any
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = None  # CLI printed prose; hand it back verbatim

    envelope = adapter.get("envelope") or {}
    error_key = envelope.get("error_code_key")
    code = parsed.get(error_key) if (isinstance(parsed, dict) and error_key) else None

    # A code the adapter declares as "not found" is a real answer: the design
    # system was reached and does not have this thing.
    if code and code in set(spec.get("not_found_codes") or []):
        return {
            "capability": capability,
            "available": True,
            "found": False,
            "error_code": code,
            "command": " ".join(argv),
        }

    # Anything else that failed is a failure to ask, not an answer. Reporting it
    # as "nothing found" would let a registry outage read as an empty design
    # system and push the ladder toward Create, the exact outcome this
    # extension exists to prevent.
    if code or proc.returncode != 0:
        detail = (proc.stderr or "").strip() or (raw if parsed is None else json.dumps(parsed))
        return {
            "capability": capability,
            "available": False,
            "reason": (detail or "non-zero exit").strip()[:500],
            "error_code": code,
            "exit_code": proc.returncode,
            "command": " ".join(argv),
        }

    return {
        "capability": capability,
        "available": True,
        "found": True,
        "command": " ".join(argv),
        "data": dig(parsed, spec.get("result_path", "")) if parsed is not None else raw,
    }


# --- ledger ------------------------------------------------------------------


def resolve_house_rules(root: Path, name: str) -> Path | None:
    """Find the project's rules file.

    Looked up in three places, in order: next to the extension config, relative
    to the repository root, and as an absolute path. The second is what makes a
    multi-repo setup work, because it lets the rules live where they belong:
    inside the design system package itself. Every repo that installs the
    package then gets the same rules without copying a file into each one, and
    the design system owns its rules rather than each consumer restating them.

        house_rules: "node_modules/@acme/design-system/spec-kit-rules.yml"
        house_rules: "../design-system/rules.yml"
    """
    if not name:
        return None
    candidate = Path(name)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for base in (ext_dir(root), root):
        path = base / candidate
        if path.is_file():
            return path
    return None


def load_rules(root: Path, config: dict, kinds: list[str] | None = None) -> dict:
    """The rules in force, in two layers.

    **Baseline** ships with the extension and holds what every design system
    wants regardless of which one it is. It deliberately carries no colors,
    breakpoints or sizes, because those belong to a specific system.

    **House rules** are the project's own, and they are where concrete values
    belong: your minimum target size, your contrast floor, your motion budget.
    A house rule sharing an id with a baseline rule replaces it, which is how a
    team tightens the floor rather than merely switching it off.

    The two are distinguishable in the output by `source`, because relaxing your
    own house rule is a product decision while switching off a baseline rule is
    a deliberate step below what design systems generally expect.
    """
    settings = config.get("rules") or {}
    disabled = {str(entry) for entry in (settings.get("disabled") or [])}

    layers: list[tuple[str, list]] = []
    if settings.get("baseline", True):
        layers.append(("baseline", load_yaml(ext_dir(root) / BASELINE_NAME).get("rules") or []))

    house_path = resolve_house_rules(root, settings.get("house_rules") or HOUSE_RULES_NAME)
    if house_path:
        layers.append(("house", load_yaml(house_path).get("rules") or []))

    # Later layers win on id, so a house rule can tighten a baseline one.
    merged: dict[str, dict] = {}
    overridden: list[str] = []
    for source, rules in layers:
        for rule in rules:
            if not isinstance(rule, dict) or not rule.get("id"):
                continue
            entry = dict(rule)
            entry["source"] = source
            if rule["id"] in merged and merged[rule["id"]]["source"] != source:
                overridden.append(rule["id"])
            merged[rule["id"]] = entry

    wanted = {kind.strip() for kind in (kinds or []) if kind.strip()}
    selected, skipped = [], 0
    for rule in merged.values():
        if rule["id"] in disabled:
            continue
        applies = rule.get("applies_to", "any")
        if wanted and applies != "any" and applies not in wanted:
            skipped += 1
            continue
        selected.append(rule)

    house_count = sum(1 for rule in selected if rule["source"] == "house")
    return {
        "enabled": bool(selected) or bool(layers),
        "baseline": str(ext_dir(root) / BASELINE_NAME),
        "house_rules": str(house_path) if house_path else None,
        "filtered_by": sorted(wanted) or None,
        "rules": selected,
        "house_rule_count": house_count,
        "overridden_by_house": sorted(set(overridden)),
        # Reported rather than silently dropped: a switched-off rule is a
        # decision someone should be able to see and question.
        "disabled": sorted(disabled),
        "skipped_as_not_applicable": skipped,
    }


def ledger_path(root: Path) -> Path:
    return root / ".specify" / "memory" / LEDGER_NAME


def load_ledger(root: Path) -> dict:
    data = load_yaml(ledger_path(root))
    data.setdefault("schema_version", "1.0")
    # An explicit `decisions:` with nothing under it parses as None, which
    # setdefault would happily keep. A hand-edited ledger should not crash the
    # scripts' always-emit-JSON contract.
    if not isinstance(data.get("decisions"), list):
        data["decisions"] = []
    return data


def normalize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS]


def score(query: str, decision: dict) -> float:
    """Token overlap against the capability phrase and the wordings that were
    actually searched when the decision was made. Aliases matter more than they
    look: they are what makes a later, differently-worded lookup hit."""
    q = set(normalize(query))
    if not q:
        return 0.0
    best = 0.0
    phrases = [decision.get("capability", "")] + list(decision.get("aliases") or [])
    for phrase in phrases:
        tokens = set(normalize(phrase))
        if not tokens:
            continue
        best = max(best, len(q & tokens) / len(q | tokens))
    return round(best, 3)


def ledger_lookup(
    root: Path, query: str, threshold: float, config: dict, current_version: str | None
) -> dict:
    ledger = load_ledger(root)

    matches = []
    for decision in ledger["decisions"]:
        if decision.get("status") == "superseded":
            continue
        value = score(query, decision)
        if value >= threshold:
            entry = dict(decision)
            entry["match_score"] = value
            # A decision taken against an older inventory may no longer hold.
            # Surface that rather than letting it be reused silently. None means
            # "could not be determined", which is not the same as "fresh".
            recorded = decision.get("design_system_version")
            entry["stale"] = (
                None if not (current_version and recorded) else recorded != current_version
            )
            matches.append(entry)

    matches.sort(key=lambda entry: entry["match_score"], reverse=True)
    return {
        "query": query,
        "threshold": threshold,
        "current_version": current_version,
        # Without a current version there is nothing to compare against, so
        # staleness is unknown rather than false. Say so, so a caller does not
        # read an unchecked decision as a verified-fresh one.
        "staleness_checked": current_version is not None,
        "ledger": str(ledger_path(root)),
        "match_count": len(matches),
        "matches": matches[:5],
    }


def ledger_record(root: Path, payload: dict) -> dict:
    required = {"capability", "resolution", "decision"}
    missing = required - set(payload)
    if missing:
        die(f"decision is missing required field(s): {', '.join(sorted(missing))}")

    ledger = load_ledger(root)
    decisions = ledger["decisions"]

    numbers = [
        int(match.group(1))
        for entry in decisions
        if (match := re.match(r"dd-(\d+)$", str(entry.get("id", ""))))
    ]
    payload.setdefault("id", f"dd-{max(numbers, default=0) + 1:03d}")
    payload.setdefault("status", "active")
    payload.setdefault("decided_on", date.today().isoformat())

    # Superseding is explicit: a new decision does not quietly shadow an old one.
    superseded = payload.pop("supersedes", None)
    if superseded:
        for entry in decisions:
            if entry.get("id") == superseded:
                entry["status"] = "superseded"
                entry["superseded_by"] = payload["id"]

    decisions.append(payload)
    dump_yaml(ledger_path(root), ledger)
    return {"recorded": payload["id"], "supersedes": superseded, "ledger": str(ledger_path(root))}


# --- gate --------------------------------------------------------------------

UI_SIGNALS = re.compile(
    r"\b(ui|screen|page|view|button|form|input|field|modal|dialog|dropdown|menu|"
    r"nav|navigation|layout|table|list|card|icon|toast|banner|tooltip|tab|"
    r"click|tap|select|display|render|show|visible|responsive|mobile|desktop|"
    r"accessib|keyboard|focus|hover|colou?r|spacing|typograph|component)\b",
    re.IGNORECASE,
)


def detect_ui_bearing(spec_path: Path | None) -> bool | None:
    """Heuristic. The command may override it: a spec can describe a user-facing
    surface without using any of these words, and a backend spec can mention
    'render' in passing."""
    if not spec_path or not spec_path.is_file():
        return None
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError:
        return None
    return len(UI_SIGNALS.findall(text)) >= 3


def cmd_gate(args: argparse.Namespace) -> None:
    root = repo_root()
    config = load_config(root)
    adapter = load_adapter(root, config)
    feature = feature_dir(root)
    spec = feature / "spec.md" if feature else None
    probe = probe_adapter(root, config, adapter)
    rules = load_rules(root, config)

    emit(
        {
            "REPO_ROOT": str(root),
            "FEATURE_DIR": str(feature) if feature else "",
            "FEATURE_SPEC": str(spec) if spec else "",
            "IMPL_PLAN": str(feature / "plan.md") if feature else "",
            "DESIGN_DOC": str(feature / DESIGN_DOC_NAME) if feature else "",
            "LEDGER": str(ledger_path(root)),
            "LEDGER_COUNT": len(load_ledger(root)["decisions"]),
            "RULES_COUNT": len(rules["rules"]),
            "HOUSE_RULE_COUNT": rules["house_rule_count"],
            "HOUSE_RULES_FILE": rules["house_rules"],
            "RULES_OVERRIDDEN": rules["overridden_by_house"],
            "RULES_DISABLED": rules["disabled"],
            "ADAPTER": adapter.get("id", ""),
            "ADAPTER_NAME": adapter.get("name", ""),
            # Empty when the design system could not actually be reached. The
            # commands treat that as a gate failure, not a pass.
            "CAPABILITIES": probe["capabilities"],
            "MAPPED_CAPABILITIES": mapped_capabilities(adapter),
            "REACHABLE": probe["reachable"],
            "UNREACHABLE_REASON": probe.get("reason", ""),
            "UI_BEARING": detect_ui_bearing(spec),
            "SPEC_EXISTS": bool(spec and spec.is_file()),
            "DESIGN_DOC_EXISTS": bool(feature and (feature / DESIGN_DOC_NAME).is_file()),
            "CONFIG": config,
        }
    )


def cmd_rules(args: argparse.Namespace) -> None:
    root = repo_root()
    kinds = (args.applies_to or "").split(",") if args.applies_to else None
    result = load_rules(root, load_config(root), kinds)
    if args.dimension:
        result["rules"] = [r for r in result["rules"] if r.get("dimension") == args.dimension]
    if args.source:
        result["rules"] = [r for r in result["rules"] if r["source"] == args.source]
    emit(result)


def cmd_query(args: argparse.Namespace) -> None:
    root = repo_root()
    config = load_config(root)
    adapter = load_adapter(root, config)

    params: dict[str, str] = {}
    positional = {
        "search": ["query"],
        "component": ["name"],
        "pattern": ["name"],
        "extend": ["name"],
        "tokens": ["theme"],
        "breakpoints": ["theme"],
        "report_gap": ["title", "body"],
    }.get(args.capability, [])
    for key, value in zip(positional, args.args):
        params[key] = value

    emit(run_capability(root, config, adapter, args.capability, params))


def cmd_ledger(args: argparse.Namespace) -> None:
    root = repo_root()
    config = load_config(root)

    if args.action == "list":
        ledger = load_ledger(root)
        active = [d for d in ledger["decisions"] if d.get("status") != "superseded"]
        emit({"ledger": str(ledger_path(root)), "count": len(active), "decisions": active})
    elif args.action == "lookup":
        if not args.value:
            die("ledger lookup requires a capability phrase")
        threshold = args.threshold
        if threshold is None:
            threshold = float(config.get("ledger", {}).get("match_threshold", 0.34))
        current_version = args.current_version or config.get("design_system_version")
        emit(ledger_lookup(root, args.value, threshold, config, current_version))
    elif args.action == "record":
        if args.value in (None, "-"):
            raw = sys.stdin.read()
        else:
            try:
                raw = Path(args.value).read_text(encoding="utf-8")
            except OSError as exc:
                die(f"could not read decision payload from {args.value}: {exc}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            die(f"decision payload is not valid JSON: {exc}")
        if not isinstance(payload, dict):
            die("decision payload must be a JSON object")
        emit(ledger_record(root, payload))


def main() -> None:
    # --json is accepted on either side of the subcommand: output is always JSON,
    # but spec-kit's script convention is to pass the flag, and callers differ on
    # where they put it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="accepted for convention; output is always JSON")

    parser = argparse.ArgumentParser(prog="designsys", description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("gate", parents=[common]).set_defaults(func=cmd_gate)

    query = sub.add_parser("query", parents=[common])
    query.add_argument("capability", choices=CAPABILITIES)
    query.add_argument("args", nargs="*")
    query.set_defaults(func=cmd_query)

    rules = sub.add_parser("rules", parents=[common])
    rules.add_argument(
        "--applies-to",
        help=f"comma-separated surface kinds this feature involves ({', '.join(SURFACE_KINDS)})",
    )
    rules.add_argument("--dimension", help="return only rules for one dimension")
    rules.add_argument(
        "--source",
        choices=["baseline", "house"],
        help="return only the shipped baseline, or only this project's house rules",
    )
    rules.set_defaults(func=cmd_rules)

    ledger = sub.add_parser("ledger", parents=[common])
    ledger.add_argument("action", choices=["lookup", "record", "list"])
    ledger.add_argument("value", nargs="?")
    ledger.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="override ledger.match_threshold from config for this lookup",
    )
    ledger.add_argument(
        "--current-version",
        default=None,
        help=(
            "the design system version in use now, so prior decisions taken against "
            "an older one are flagged stale; falls back to design_system_version in config"
        ),
    )
    ledger.set_defaults(func=cmd_ledger)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
