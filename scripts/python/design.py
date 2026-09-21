#!/usr/bin/env python3
"""Design system integration for spec-kit.

All logic lives here; `scripts/bash/ds.sh` is a thin shim. Callers without bash
can invoke this module directly and get identical behaviour.

Subcommands:
    gate                     prerequisites + resolved config as one JSON object
    query <capability> ...   ask the design system through the adapter
    principles               the principles in force (CLI -> adapter -> default)
    context <phase>          the focused context for one workflow phase
    workflow status          where the autonomous run has got to, and what is next
    rfc <path|->             normalize an RFC into structured JSON
    ledger lookup <phrase>   find prior decisions for a capability
    ledger record <file>     append a decision (JSON object on disk or '-')
    ledger list              all active decisions

Everything emits one compact JSON object on stdout.
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

EXT_ID = "design"
CONFIG_NAME = "design-config.yml"
LOCAL_CONFIG_NAME = "design-config.local.yml"
LEDGER_NAME = "design-decisions.yml"
DESIGN_DOC_NAME = "design-system.md"
DEFAULT_PRINCIPLES = "principles/default.yml"

# What a principle can apply to. A feature declares which of these it involves,
# and only the matching principles reach its context.
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
    # The design system's own principles. When this answers, it IS the
    # principles for the run; nothing shipped here is merged into it.
    "principles",
    "extend",
    "validate",
    "report_gap",
]

# Phases of the autonomous workflow, in order. `clarify` and `verify` bracket
# the spec-kit lifecycle; the rest map onto spec-kit's own commands.
PHASES = ["clarify", "specify", "plan", "implement", "validate", "verify"]

# A hit on the name is worth more than a hit buried in prose.
FIELD_WEIGHTS = {"name": 3.0, "usage": 1.5, "description": 1.0}

STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "and", "or", "with", "in", "on",
    "that", "this", "is", "are", "be", "by", "as", "at", "from", "it",
}


def die(message: str, code: int = 1) -> None:
    print(f"[design] {message}", file=sys.stderr)
    # Callers parse stdout, so a refusal is JSON there too, not just stderr text.
    emit({"available": False, "error": message})
    raise SystemExit(code)


def emit(obj: Any) -> None:
    """One compact JSON object on stdout, per spec-kit script convention."""
    try:
        json.dump(obj, sys.stdout, separators=(",", ":"), default=str)
        sys.stdout.write("\n")
        sys.stdout.flush()
    except BrokenPipeError:
        # Reader closed early (`| head`); nothing left to tell it.
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass


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
    "SPECKIT_DESIGN_ADAPTER": ("adapter", str),
    "SPECKIT_DESIGN_BIN": ("bin", str),
    "SPECKIT_DESIGN_CWD": ("cwd", str),
    "SPECKIT_DESIGN_GATE_ENFORCE": ("gate.enforce", bool),
    "SPECKIT_DESIGN_MIN_CANDIDATES": ("gate.min_candidates_considered", int),
    "SPECKIT_DESIGN_MAX_VALIDATION_ROUNDS": ("workflow.max_validation_rounds", int),
    "SPECKIT_DESIGN_LEDGER_ENABLED": ("ledger.enabled", bool),
    "SPECKIT_DESIGN_MATCH_THRESHOLD": ("ledger.match_threshold", float),
    "SPECKIT_DESIGN_FORBID_RAW_VALUES": ("validation.forbid_raw_values", bool),
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


def migrate_config(config: dict) -> dict:
    """Carry pre-0.2 configuration forward.

    `baseline` is gone as a public concept: what it named is now the *default*
    principles, used only when the design system supplies none. Old keys are
    mapped rather than ignored, so an existing project keeps working, and the
    mapping is reported so it can be cleaned up.
    """
    notes: list[str] = []

    rules = config.pop("rules", None)
    if isinstance(rules, dict):
        principles = dict(config.get("principles") or {})
        if "baseline" in rules and "default" not in principles:
            principles["default"] = bool(rules["baseline"])
            notes.append("rules.baseline -> principles.default")
        if rules.get("house_rules") and not principles.get("source"):
            principles["source"] = rules["house_rules"]
            notes.append("rules.house_rules -> principles.source")
        if rules.get("disabled") and not principles.get("disabled"):
            principles["disabled"] = rules["disabled"]
            notes.append("rules.disabled -> principles.disabled")
        config["principles"] = principles

    audit = config.pop("audit", None)
    if isinstance(audit, dict):
        config["validation"] = deep_merge(audit, config.get("validation") or {})
        notes.append("audit.* -> validation.*")

    gate = config.get("gate")
    if isinstance(gate, dict) and "require_gap_report" in gate:
        gate.pop("require_gap_report")
        notes.append("gate.require_gap_report dropped: a gap record is always required")

    if notes:
        config["_migrated"] = notes
    return config


def load_config(root: Path) -> dict:
    """Resolution order: extension defaults -> project config -> local override
    -> environment. This mirrors spec-kit's own layering, so a developer can
    point at a scratch design system without touching the committed config."""
    config = load_yaml(ext_dir(root) / "extension.yml").get("config", {}).get("defaults", {})
    config = deep_merge(config, migrate_config(load_yaml(ext_dir(root) / CONFIG_NAME)))
    config = deep_merge(config, migrate_config(load_yaml(ext_dir(root) / LOCAL_CONFIG_NAME)))

    for variable, (dotted, kind) in ENV_OVERRIDES.items():
        raw = os.environ.get(variable)
        if raw not in (None, ""):
            set_path(config, dotted, coerce(raw, kind))

    return config


# Dependency name -> adapter. Ordered: the first match wins.
LIBRARY_ADAPTERS = (
    ("@mui/material", "mui"),
    ("antd", "antd"),
    ("@chakra-ui/react", "chakra"),
    ("@ark-ui/react", "ark-ui"),
    ("radix-ui", "radix"),
    ("@radix-ui/", "radix"),  # trailing slash: any scoped primitive
)


def detect_adapter(root: Path, config: dict) -> str:
    """Pick a shipped adapter from what the project already contains, so nobody
    has to name one. Only unambiguous signals count; anything else falls back to
    static-json, which needs no CLI and degrades cleanly."""
    base = root / config["cwd"] if config.get("cwd") else root
    if (base / "components.json").is_file():
        return "shadcn"
    deps: dict = {}
    try:
        package = json.loads((base / "package.json").read_text(encoding="utf-8"))
        for key in ("dependencies", "devDependencies"):
            deps.update(package.get(key) or {})
    except (OSError, ValueError, AttributeError):
        pass
    for package, adapter_id in LIBRARY_ADAPTERS:
        if package in deps or (package.endswith("/") and any(d.startswith(package) for d in deps)):
            return adapter_id
    return "static-json"


def load_adapter(root: Path, config: dict) -> dict:
    adapter_id = config.get("adapter") or "auto"
    if adapter_id == "auto":
        adapter_id = detect_adapter(root, config)
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
    result = run_capability(
        root, config, adapter, probe, dict(PROBE_PARAMS.get(probe, {})), timeout=30
    )

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


def slice_result(data: Any, spec: dict) -> tuple[Any, bool]:
    """The part of a response a capability actually answers with.

    Three ways to say it, in the order they are tried:

    * `result_path` - one dotted path, the common case.
    * `result_paths` - an ordered list of candidates, first hit wins. One
      command often answers two questions (`tokens` and `breakpoints` are
      usually the same call), and the slice sits under a key that differs
      between systems and versions.
    * `pick` - keep only these keys of the resolved mapping. For the case where
      the answer is several siblings rather than one subtree.

    Returns the slice and whether a mapping was configured but resolved to
    nothing, which callers report rather than silently pass off as an answer.
    """
    paths = [path for path in (spec.get("result_paths") or []) if path]
    configured = bool(paths)
    if not paths:
        single = spec.get("result_path", "")
        configured = bool(single)
        paths = [single]

    value = None
    for path in paths:
        value = dig(data, path)
        if value is not None:
            break

    keys = [key for key in (spec.get("pick") or []) if key]
    if value is not None and keys:
        configured = True
        if isinstance(value, dict):
            narrowed = {key: value[key] for key in keys if key in value}
            value = narrowed or None
        # A list or scalar has no keys to pick from; `pick` cannot narrow it, so
        # it is left as it is rather than reported as a miss.

    return value, configured and value is None


def payload_bytes(data: Any) -> int:
    """Size of a payload as it will be handed on, so context cost is a number
    somebody can see rather than something they discover in a token bill."""
    try:
        return len(json.dumps(data, separators=(",", ":"), default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def run_capability(
    root: Path,
    config: dict,
    adapter: dict,
    capability: str,
    params: dict[str, str],
    timeout: int = 120,
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
            data = read_structured(path)
        except ValueError as exc:
            return {"capability": capability, "available": False, "reason": str(exc)}
        if not isinstance(data, dict):
            return {
                "capability": capability,
                "available": False,
                "reason": f"{path} must hold a mapping at top level, got {type(data).__name__}",
            }
        result, _ = slice_result(data, spec)

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
                "bytes": payload_bytes(match),
                "data": match,
            }

        if spec.get("match_fields") and wanted is None and not params.get("query"):
            return {
                "capability": capability,
                "available": False,
                "reason": f"'{capability}' needs a query",
            }

        if spec.get("match_fields") and wanted is None and params.get("query"):
            query_tokens = set(normalize(params["query"]))
            hits = []
            for section in spec.get("search_keys") or []:
                for item in data.get(section) or []:
                    if not isinstance(item, dict):
                        continue
                    # Weighted per field rather than one bag of words. A raw
                    # overlap count makes every candidate tie at 1 on short
                    # descriptions, so results come back in insertion order and
                    # "pull detail on the strongest hits" has nothing to act on.
                    score = 0.0
                    for field in spec["match_fields"]:
                        tokens = set(normalize(str(item.get(field, ""))))
                        if not tokens:
                            continue
                        overlap = query_tokens & tokens
                        if overlap:
                            weight = FIELD_WEIGHTS.get(field, 1.0)
                            score += weight * len(overlap) / len(query_tokens)
                    if score:
                        hits.append(
                            {"kind": section, "score": round(score, 3), **item}
                        )
            # Ties break on name so ordering is stable rather than positional.
            hits.sort(key=lambda entry: (-entry["score"], str(entry.get("name", ""))))
            return {
                "capability": capability,
                "available": True,
                "found": bool(hits),
                "source": str(path),
                "bytes": payload_bytes(hits[:20]),
                "data": hits[:20],
            }

        # No envelope guessing here: a file-backed adapter knows the shape of the
        # file it points at, so a missing `result_path` means the file genuinely
        # does not carry that section, not that the mapping was wrong.
        return {
            "capability": capability,
            "available": True,
            "found": result not in (None, [], {}),
            "source": str(path),
            "bytes": payload_bytes(result),
            "data": result,
        }

    # A capability may name its own binary. The two rungs at the top of the
    # ladder are the reason: a gap is filed in an issue tracker and a component
    # is ejected by a codegen tool, and neither is usually the design system's
    # own CLI. Without this they can only be mapped by writing a wrapper script,
    # which is how rungs 4 and 5 end up unmapped on systems that could support
    # them. A file-backed adapter with no `bin` at all can map them this way too.
    own_binary = bool(spec.get("bin"))
    binary = spec.get("bin") or adapter.get("bin") or ""
    if not binary:
        return {"capability": capability, "available": False, "reason": "no binary configured"}

    merged: dict[str, Any] = {**(spec.get("defaults") or {}), **params}
    if adapter.get("registries"):
        merged.setdefault("registries", list(adapter["registries"]))

    argv = shlex.split(binary)
    argv += substitute(list(spec.get("args") or []), merged)
    # `global_args` are the design system CLI's flags - usually the one that
    # makes it emit JSON. Appending them to someone else's binary would be a
    # mapping error the adapter author never wrote.
    if not own_binary:
        argv += list(adapter.get("global_args") or [])

    try:
        proc = subprocess.run(
            argv, cwd=base, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return {
            "capability": capability,
            "available": False,
            "reason": f"'{argv[0]}' not found. Is the design system CLI installed?",
        }
    except subprocess.TimeoutExpired:
        return {"capability": capability, "available": False, "reason": f"CLI timed out after {timeout}s"}

    raw = proc.stdout.strip()
    parsed: Any
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = None  # CLI printed prose; hand it back verbatim

    # The envelope describes one CLI's response shape, so it applies to that
    # CLI. Reading another tool's `code` field as this one's error code would
    # turn a filed issue into a reported outage.
    envelope = (adapter.get("envelope") or {}) if not own_binary else {}
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

    mapped_slice = bool(
        spec.get("result_path") or spec.get("result_paths") or spec.get("pick")
    )
    if raw and parsed is None and (mapped_slice or envelope):
        # The adapter was written against a JSON CLI. Prose here means a flag
        # or output format changed, which is a failure to ask, not an answer.
        return {
            "capability": capability,
            "available": False,
            "reason": f"expected JSON from the CLI, got: {raw[:200]}",
            "exit_code": proc.returncode,
            "command": " ".join(argv),
        }
    if not raw:
        return {
            "capability": capability,
            "available": True,
            "found": False,
            "command": " ".join(argv),
            "result_path_missed": False,
            "bytes": 0,
            "data": None,
        }
    if parsed is None:
        data: Any = raw
        missed = False
    else:
        data, missed = slice_result(parsed, spec)
        # A shipped adapter guesses at the CLI's envelope. When the guess misses,
        # hand back what the CLI actually said instead of a null that reads as
        # "the design system has nothing".
        if missed:
            data = parsed

    return {
        "capability": capability,
        "available": True,
        "found": True,
        "command": " ".join(argv),
        "result_path_missed": missed,
        # Unnarrowed, this is the whole CLI payload: the number to watch when a
        # capability that should answer narrowly starts costing context.
        "bytes": payload_bytes(data),
        "data": data,
    }


def project_fields(data: Any, fields: list[str]) -> Any:
    """Keep only these keys of a result.

    The caller's own trim, not the adapter's: an inventory listing is the
    right answer to `list_components` and also the most expensive thing the
    design system will say. Asking for `name,description` makes a survey cheap
    without the full answer stopping being available on the next call.
    """
    if not fields:
        return data
    if isinstance(data, list):
        return [
            {key: item[key] for key in fields if key in item} if isinstance(item, dict) else item
            for item in data
        ]
    if isinstance(data, dict):
        return {key: data[key] for key in fields if key in data}
    return data


def read_structured(path: Path) -> Any:
    """Read a JSON or YAML file. Adapters point at whatever the design system
    already publishes, and that is JSON about as often as it is YAML."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    if path.suffix.lower() in {".yml", ".yaml"}:
        return load_yaml(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


# --- principles ---------------------------------------------------------------


def resolve_path(root: Path, name: str) -> Path | None:
    """Find a file named in config, in three places: next to the extension
    config, relative to the repository root, and as an absolute path.

    The second is what makes a multi-repo setup work, because it lets the
    principles live inside the design system package itself. Every repo that
    installs the package then reads the same file:

        principles:
          source: "node_modules/@acme/design-system/principles.yml"
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


def normalize_principles(payload: Any) -> dict:
    """Accept whatever shape a design system publishes.

    There is deliberately no schema to conform to. A system may return prose, a
    list of rules, or a document with both. Requiring one shape would mean
    asking teams to restate what their design system already says, which is the
    thing this extension exists not to do.
    """
    prose = ""
    rules: list[dict] = []
    extra: dict = {}

    if payload is None:
        return {"prose": "", "rules": [], "version": None, "extra": {}}
    if isinstance(payload, str):
        return {"prose": payload.strip(), "rules": [], "version": None, "extra": {}}
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                rules.append(item)
            elif isinstance(item, str):
                prose = f"{prose}\n{item}".strip()
        return {"prose": prose, "rules": rules, "version": None, "extra": {}}
    if isinstance(payload, dict):
        # Whatever key the design system publishes its list under.
        for key in ("principles", "rules", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                rules.extend(entry for entry in value if isinstance(entry, dict))
                prose = "\n".join(
                    [prose, *(entry for entry in value if isinstance(entry, str))]
                ).strip()
            elif isinstance(value, str):
                prose = f"{prose}\n{value}".strip()
        for key in ("prose", "text", "content", "docs", "description", "body"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                prose = f"{prose}\n{value}".strip()
        extra = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "principles", "rules", "items",
                "prose", "text", "content", "docs", "description", "body",
            }
        }
        if not prose and not rules and extra:
            # Nothing recognizable; hand the document back rather than dropping
            # it. An unfamiliar shape is still the system speaking for itself.
            prose = json.dumps(extra, indent=2, default=str)
        version = extra.get("version")
        return {
            "prose": prose,
            "rules": rules,
            "version": str(version) if version not in (None, "") else None,
            "extra": extra,
        }
    return {"prose": str(payload), "rules": [], "version": None, "extra": {}}


def select_principles(rules: list[dict], kinds: list[str] | None, disabled: set[str]) -> tuple:
    """Filter to what this feature actually involves. Anything without an
    `applies_to` is unconditional, because a design system writing free-form
    principles cannot be expected to classify them."""
    wanted = {kind.strip() for kind in (kinds or []) if kind.strip()}
    selected, skipped = [], 0
    for rule in rules:
        if str(rule.get("id", "")) in disabled:
            continue
        applies = rule.get("applies_to", "any")
        if wanted and applies != "any" and applies not in wanted:
            skipped += 1
            continue
        selected.append(rule)
    return selected, skipped


def resolve_principles(
    root: Path, config: dict, adapter: dict, kinds: list[str] | None = None
) -> dict:
    """The principles in force, resolved from exactly one source.

        1. the design system's CLI        (`principles` capability, invoked)
        2. adapter-provided static data   (inventory key, or a file it ships)
        3. the small default set shipped here

    The first one that answers wins **outright**. The default set is a fallback,
    not a floor: merging it into a real design system's principles would mean
    holding that system to rules it never wrote.
    """
    settings = config.get("principles") or {}
    disabled = {str(entry) for entry in (settings.get("disabled") or [])}
    attempts: list[dict] = []

    spec = (adapter.get("capabilities") or {}).get("principles") or {}
    is_file_backed = bool(spec.get("read_file"))

    # 1. The CLI.
    if spec and not is_file_backed:
        result = run_capability(root, config, adapter, "principles", {})
        if result.get("available") and result.get("data") not in (None, "", [], {}):
            return _principles_payload(
                "cli", result.get("command", adapter.get("bin", "")),
                result["data"], kinds, disabled, attempts,
            )
        attempts.append({"source": "cli", "reason": result.get("reason", "no principles returned")})

    # 2. Adapter-provided static data: a file the design system ships, either
    #    named in config or mapped by the adapter as a file-backed capability.
    configured = resolve_path(root, str(settings.get("source") or ""))
    if configured:
        try:
            payload = read_structured(configured)
        except ValueError as exc:
            attempts.append({"source": "docs", "reason": str(exc)})
        else:
            return _principles_payload(
                "docs", str(configured), payload, kinds, disabled, attempts
            )
    elif settings.get("source"):
        attempts.append({"source": "docs", "reason": f"{settings['source']} not found"})

    if is_file_backed:
        result = run_capability(root, config, adapter, "principles", {})
        if result.get("available") and result.get("data") not in (None, "", [], {}):
            return _principles_payload(
                "docs", result.get("source", ""), result["data"], kinds, disabled, attempts
            )
        attempts.append(
            {"source": "docs", "reason": result.get("reason", "no principles in inventory")}
        )

    # 3. The default set.
    if settings.get("default", True) is False:
        # Nothing answered and the fallback is switched off, so there are no
        # principles in force. Said outright, because a gate that requires them
        # must fail closed here rather than pass on an empty set.
        return {
            "principles_source": "unavailable",
            "principles_version": None,
            "origin": "",
            "authoritative": False,
            "prose": "",
            "principles": [],
            "principle_count": 0,
            "unenforceable": [],
            "filtered_by": sorted({k for k in (kinds or []) if k}) or None,
            "skipped_as_not_applicable": 0,
            "disabled": sorted(disabled),
            "attempted": attempts,
        }

    path = ext_dir(root) / DEFAULT_PRINCIPLES
    payload = load_yaml(path)
    return _principles_payload("default", str(path), payload, kinds, disabled, attempts)


# A principle binds only if something can be checked against it. MUST/SHOULD
# says it is normative; `verify` says how anyone would know. Missing either, it
# is a statement of intent - worth reading, not worth citing as a requirement.
NORMATIVE = re.compile(r"\b(MUST|SHOULD|MUST NOT|SHOULD NOT)\b")


def is_enforceable(principle: dict) -> bool:
    return bool(
        str(principle.get("verify", "")).strip()
        and NORMATIVE.search(str(principle.get("requirement", "")))
    )


def _principles_payload(
    source: str,
    origin: str,
    payload: Any,
    kinds: list[str] | None,
    disabled: set[str],
    attempts: list[dict],
) -> dict:
    normalized = normalize_principles(payload)
    selected, skipped = select_principles(normalized["rules"], kinds, disabled)
    # Derived, never substituted: the design system's own fields are passed
    # through as they were written.
    marked = [{**principle, "enforceable": is_enforceable(principle)} for principle in selected]
    return {
        # Where these principles came from, and what that means:
        #   cli          the design system answered for itself
        #   docs         static principles it publishes (inventory key or file)
        #   default      it supplied none, so the fallback set applies
        #   unavailable  it supplied none and the fallback is switched off
        "principles_source": source,
        # What the source calls this revision of its principles, when it says.
        # Null is honest: most systems do not version them, and inventing one
        # would make a stale citation look checked.
        "principles_version": normalized["version"],
        "origin": origin,
        "authoritative": source in {"cli", "docs"},
        "prose": normalized["prose"],
        "principles": marked,
        "principle_count": len(marked),
        # Stated rather than filtered out. A principle nobody can check is not a
        # principle to drop quietly; it is one to write a `verify` step for.
        "unenforceable": [
            str(principle.get("id", "")) for principle in marked if not principle["enforceable"]
        ],
        "filtered_by": sorted({k for k in (kinds or []) if k}) or None,
        "skipped_as_not_applicable": skipped,
        # Reported rather than silently dropped: a switched-off principle is a
        # decision someone should be able to see and question.
        "disabled": sorted(disabled),
        "attempted": attempts,
    }


# --- focused context ----------------------------------------------------------

# What each phase is given up front. Everything else stays one query away;
# nothing here is a ceiling on what the agent may ask for.
PHASE_CONTEXT = {
    "clarify": ["rfc", "principles"],
    "specify": ["rfc", "principles", "candidates"],
    "plan": ["spec", "principles", "named_components", "tokens", "breakpoints"],
    "implement": ["plan", "named_components", "tokens"],
    "validate": ["spec", "principles", "named_components"],
    "verify": ["spec", "principles"],
}

RETRIEVAL_HINT = "ds.sh query {capability} [args]"

# Above this, a capability's answer is large enough to be worth narrowing. Not a
# limit and not a filter: nothing is dropped, the size is just said out loud
# where the person tuning the adapter will see it.
LARGE_PAYLOAD_BYTES = 8192


def cost_note(capability: str, result: dict) -> str | None:
    """What a bulky or unnarrowed answer costs, phrased as the fix.

    A capability mapped to a command it shares with a broader one (`breakpoints`
    onto the token command is the usual pair) answers with the whole payload
    unless the adapter carves out a slice. That is invisible at the call site:
    the context is simply bigger, every phase, every run.
    """
    size = result.get("bytes") or 0
    if result.get("result_path_missed"):
        return (
            f"{capability}: the adapter's result_path did not resolve, so the CLI's whole "
            f"payload came back ({size} bytes). Narrow it with result_path, result_paths "
            f"or pick in the adapter."
        )
    if size > LARGE_PAYLOAD_BYTES:
        return (
            f"{capability}: {size} bytes in this context. If the design system can answer "
            f"it more narrowly, or the adapter can slice the response (result_path, "
            f"result_paths, pick), that cost is paid once in the adapter instead of every run."
        )
    return None


def context_sizes(payload: dict) -> dict:
    """Bytes per section of the context, and the total.

    Focused context is a claim about size, so it should be measurable. Without
    this, a capability quietly answering with 50 KB looks exactly like one
    answering with 50.
    """
    sections = ["principles", "components", "tokens", "breakpoints", "candidates"]
    sizes = {name: payload_bytes(payload.get(name)) for name in sections}
    sizes["total"] = payload_bytes(payload)
    return sizes


def build_context(
    root: Path,
    config: dict,
    adapter: dict,
    phase: str,
    kinds: list[str] | None = None,
    components: list[str] | None = None,
    query: str | None = None,
) -> dict:
    """The context one phase starts with.

    Two properties matter and are both deliberate:

    * The whole design system is never inlined. A phase gets the principles that
      apply and the components it actually named.
    * Nothing is withheld. Every capability the design system can answer is
      listed under `available_on_demand`, with the exact call to make. Focused
      context is about noise, not about keeping the agent in the dark.
    """
    if phase not in PHASE_CONTEXT:
        die(f"unknown phase '{phase}'. One of: {', '.join(PHASE_CONTEXT)}")

    wants = PHASE_CONTEXT[phase]
    probe = probe_adapter(root, config, adapter)
    principles = resolve_principles(root, config, adapter, kinds)

    payload: dict[str, Any] = {
        "phase": phase,
        "includes": wants,
        "adapter": adapter.get("id", ""),
        "reachable": probe["reachable"],
        "principles": principles,
        "components": {},
        "tokens": None,
        "breakpoints": None,
        "candidates": None,
        # Everything the design system can still be asked, and how. The context
        # is a starting point, never a limit.
        "available_on_demand": probe["capabilities"],
        "retrieval": {
            capability: RETRIEVAL_HINT.format(capability=capability)
            for capability in probe["capabilities"]
        },
        "notes": [],
    }

    if not probe["reachable"]:
        payload["notes"].append(probe.get("reason", "design system unreachable"))
        payload["sizes"] = context_sizes(payload)
        return payload

    if "named_components" in wants:
        for name in components or []:
            result = run_capability(root, config, adapter, "component", {"name": name})
            if not result.get("found"):
                result = run_capability(root, config, adapter, "pattern", {"name": name})
            payload["components"][name] = result.get("data") if result.get("found") else None
            if not result.get("found"):
                payload["notes"].append(f"{name}: not found in the design system")
        if not components:
            payload["notes"].append(
                "no components named; ask for them with `query component <Name>` as the work "
                "identifies them"
            )

    if "candidates" in wants and query:
        search = run_capability(root, config, adapter, "search", {"query": query})
        payload["candidates"] = search.get("data") if search.get("available") else None

    if "tokens" in wants:
        tokens = run_capability(root, config, adapter, "tokens", {})
        payload["tokens"] = tokens.get("data") if tokens.get("available") else None
        note = cost_note("tokens", tokens) if tokens.get("available") else None
        if note:
            payload["notes"].append(note)

    if "breakpoints" in wants:
        breakpoints = run_capability(root, config, adapter, "breakpoints", {})
        payload["breakpoints"] = breakpoints.get("data") if breakpoints.get("available") else None
        if breakpoints.get("available"):
            # The specific, common case: `breakpoints` mapped onto the token
            # command and never narrowed, so both capabilities answer with the
            # same thing. It works - the names are in there - and it doubles
            # what this phase pays, silently, on every run.
            duplicate = (
                "tokens" in wants
                and payload["tokens"] is not None
                and payload["tokens"] == payload["breakpoints"]
            )
            if duplicate:
                payload["notes"].append(
                    f"breakpoints: answered with the same payload as tokens "
                    f"({breakpoints.get('bytes', 0)} bytes, counted twice). The names are in "
                    f"there; narrowing the adapter's breakpoints mapping (result_path, "
                    f"result_paths, pick) is what stops this phase paying for the token set "
                    f"a second time."
                )
            else:
                note = cost_note("breakpoints", breakpoints)
                if note:
                    payload["notes"].append(note)

    payload["sizes"] = context_sizes(payload)
    return payload


# --- autonomous workflow ------------------------------------------------------

FINDING_OPEN = re.compile(r"^\s*-\s*\[ \]\s*(DS-F-\S+)", re.MULTILINE)
FINDING_CLOSED = re.compile(r"^\s*-\s*\[[xX]\]\s*(DS-F-\S+)", re.MULTILINE)
VALIDATION_ROUND = re.compile(r"^##+\s*Validation round\s+(\d+)", re.MULTILINE | re.IGNORECASE)
CLARIFICATION = re.compile(r"\[NEEDS CLARIFICATION", re.IGNORECASE)
TASK_OPEN = re.compile(r"^\s*-\s*\[ \]\s", re.MULTILINE)
TASK_DONE = re.compile(r"^\s*-\s*\[[xX]\]\s", re.MULTILINE)


def read_text(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def last_round_findings(design: str) -> list[str]:
    """Findings raised by the most recent validation round, ticked or not."""
    starts = [match.start() for match in VALIDATION_ROUND.finditer(design)]
    if not starts:
        return []
    section = design[starts[-1]:]
    return FINDING_OPEN.findall(section) + FINDING_CLOSED.findall(section)


def workflow_status(root: Path, config: dict) -> dict:
    """Where the run has got to, derived from the artifacts on disk.

    There is no run-state file. Progress is whatever the spec, plan, tasks and
    design document already say, which means an interrupted run can be resumed
    by reading them, and nothing can drift out of sync with the work itself.
    """
    feature = feature_dir(root)
    if not feature:
        return {
            "feature_dir": "",
            "error": "no active feature. Run /speckit.specify first, or let "
                     "/speckit.design.run create one from the RFC.",
            "next": "specify",
            "complete": False,
        }

    spec = read_text(feature / "spec.md")
    plan = read_text(feature / "plan.md")
    tasks = read_text(feature / "tasks.md")
    design = read_text(feature / DESIGN_DOC_NAME)

    rounds = [int(match) for match in VALIDATION_ROUND.findall(design)]
    open_findings = sorted(set(FINDING_OPEN.findall(design)))
    closed_findings = sorted(set(FINDING_CLOSED.findall(design)))
    max_rounds = int((config.get("workflow") or {}).get("max_validation_rounds", 3))

    # A round that raised findings does not become clean because they were
    # ticked off. Only a fresh round with nothing in it ends the loop, which is
    # what stops the fixing pass from also signing off its own fixes.
    last_round_clean = bool(rounds) and not last_round_findings(design)

    tasks_open = len(TASK_OPEN.findall(tasks))
    tasks_done = len(TASK_DONE.findall(tasks))

    implemented = bool(tasks) and tasks_open == 0 and tasks_done > 0
    phases = {
        "clarify": "done" if spec and not CLARIFICATION.search(spec) else
                   ("blocked" if spec else "pending"),
        "specify": "done" if spec else "pending",
        "plan": "done" if plan else "pending",
        "implement": "done" if implemented else ("in_progress" if tasks else "pending"),
        "validate": "done" if last_round_clean else ("in_progress" if rounds else "pending"),
        "verify": "done" if last_round_clean and implemented else "pending",
    }

    rounds_used = max(rounds) if rounds else 0
    may_validate_again = rounds_used < max_rounds

    if phases["clarify"] == "blocked":
        nxt, reason = "clarify", "the spec still carries [NEEDS CLARIFICATION] markers"
    elif not spec:
        nxt, reason = "specify", "no specification yet"
    elif not plan:
        nxt, reason = "plan", "no plan yet"
    elif phases["implement"] != "done":
        nxt, reason = "implement", "tasks remain open"
    elif open_findings and not may_validate_again:
        nxt, reason = "stop", (
            f"{len(open_findings)} finding(s) still open after {rounds_used} validation "
            f"round(s), the configured maximum. This needs a human."
        )
    elif open_findings:
        nxt, reason = "fix", f"{len(open_findings)} open finding(s) from validation"
    elif not rounds:
        nxt, reason = "validate", "the implementation has not been validated yet"
    elif not last_round_clean:
        nxt, reason = "validate", (
            f"round {rounds_used} raised findings that are now fixed; they need checking"
        )
    else:
        nxt, reason = "done", "the last validation round was clean"

    return {
        "feature_dir": str(feature),
        "design_doc": str(feature / DESIGN_DOC_NAME),
        "phases": phases,
        "tasks_open": tasks_open,
        "tasks_done": tasks_done,
        "validation_rounds_used": rounds_used,
        "last_round_clean": last_round_clean,
        "max_validation_rounds": max_rounds,
        "may_validate_again": may_validate_again,
        "open_findings": open_findings,
        "closed_findings": closed_findings,
        "next": nxt,
        "reason": reason,
        "complete": nxt == "done",
    }


# --- RFC ----------------------------------------------------------------------

HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
SECTION_ALIASES = {
    "problem": ("problem", "background", "context", "motivation", "why"),
    "proposal": ("proposal", "solution", "what", "approach", "scope"),
    "surfaces": ("surfaces", "ui", "user interface", "screens", "user experience"),
    "acceptance": ("acceptance", "success", "criteria", "done when", "requirements"),
    "out_of_scope": ("out of scope", "non-goals", "non goals", "excluded"),
    "open_questions": ("open questions", "questions", "unknowns", "risks"),
}

UI_SIGNALS = re.compile(
    r"\b(ui|screen|page|view|button|form|input|field|modal|dialog|drawer|popover|"
    r"dropdown|menu|nav|navigation|sidebar|header|footer|layout|table|list|card|"
    r"icon|toast|banner|tooltip|tab|badge|avatar|spinner|checkbox|radio|toggle|"
    r"slider|picker|control|filter|sort|search|scroll|drag|swipe|label|placeholder|"
    r"click|tap|select|display|render|show|visible|responsive|mobile|desktop|theme|"
    r"accessib|keyboard|focus|hover|colou?r|spacing|typograph|component)\b",
    re.IGNORECASE,
)

# An RFC is short by nature, so it clears a lower bar than a full specification
# before it counts as describing a user interface. Under-detecting here is the
# expensive direction: it skips the design system entirely.
RFC_UI_THRESHOLD = 2
SPEC_UI_THRESHOLD = 3


def parse_rfc(text: str, origin: str = "") -> dict:
    """Normalize an RFC into the few things the workflow needs from it.

    The RFC is the input abstraction, and it is deliberately the only one. Where
    it came from — a file, an issue, a ticket, an MCP server — is somebody
    else's problem, and keeping it that way is what stops this extension from
    turning into an integration platform.
    """
    lines = text.splitlines()
    headings = list(HEADING.finditer(text))
    title = ""
    for match in headings:
        if len(match.group(1)) == 1:
            title = match.group(2).strip()
            break
    if not title:
        title = next((line.strip(" #") for line in lines if line.strip()), "")[:120]

    sections: dict[str, str] = {}
    for index, match in enumerate(headings):
        name = match.group(2).strip().lower()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end():end].strip()
        for key, aliases in SECTION_ALIASES.items():
            if any(alias in name for alias in aliases) and key not in sections:
                sections[key] = body

    open_questions = [
        line.strip(" -*")
        for line in lines
        if CLARIFICATION.search(line) or re.match(r"^\s*[-*]\s*\?", line)
    ]
    if "open_questions" in sections:
        open_questions += [
            line.strip(" -*")
            for line in sections["open_questions"].splitlines()
            if line.strip().startswith(("-", "*"))
        ]

    warnings = []
    if not sections.get("problem"):
        warnings.append("no problem statement found; clarify what the RFC is solving")
    if not sections.get("acceptance"):
        warnings.append("no acceptance criteria found; clarify what done means")
    if len(text.split()) < 30:
        warnings.append("the RFC is very short; expect the clarify phase to do real work")

    return {
        "origin": origin,
        "title": title,
        "sections": sections,
        "open_questions": sorted(set(q for q in open_questions if q))[:20],
        "ui_bearing": len(UI_SIGNALS.findall(text)) >= RFC_UI_THRESHOLD,
        "word_count": len(text.split()),
        "warnings": warnings,
        "text": text,
    }


# --- ledger ------------------------------------------------------------------


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
    """Tokenize for matching, splitting CamelCase first.

    Component names are almost always CamelCase, so lowercasing before
    splitting would turn `DateRangePicker` into one token that the query
    "date range picker" can never match. Both the component search and the
    ledger's alias matching depend on this.
    """
    split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text or "")
    words = re.findall(r"[a-z0-9]+", split.lower())
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
    return len(UI_SIGNALS.findall(text)) >= SPEC_UI_THRESHOLD


# Which capabilities carry which rung of the reuse ladder. The rungs themselves
# live in `commands/speckit.design.check.md`; this only says what is automated,
# so an adapter author can see what a missing mapping costs before a run does.
LADDER_CAPABILITIES = {
    "reuse": ["search", "component"],
    "compose": ["pattern", "search"],
    "extend": ["extend"],
    "create": ["report_gap"],
}


def ladder_support(capabilities: list[str]) -> dict:
    """Per rung: what backs it, and whether the design system can answer for it.

    An unbacked rung is not a broken run - the command still walks it on the
    component's own documentation, and a gap record is written whether or not
    `report_gap` is mapped. It is a rung the design system is not being asked
    about, which is worth knowing at gate time rather than inferring from a
    thin ladder walk later.
    """
    reachable = set(capabilities)
    return {
        rung: {
            "backed_by": backing,
            "automated": bool(reachable & set(backing)),
        }
        for rung, backing in LADDER_CAPABILITIES.items()
    }


def effective_dimensions(config: dict, capabilities: list[str]) -> list[str]:
    """Dimensions this design system can actually be held to.

    A design system with no token layer cannot be asked for token names, so
    requiring a `tokens` answer from it would fail the gate on something it has
    no way to provide. Nothing is mandatory that the system cannot supply.
    """
    wanted = list((config.get("validation") or {}).get("required_dimensions") or [])
    if "tokens" not in capabilities:
        wanted = [dimension for dimension in wanted if dimension != "tokens"]
    return wanted


def cmd_gate(args: argparse.Namespace) -> None:
    root = repo_root()
    config = load_config(root)
    adapter = load_adapter(root, config)
    feature = feature_dir(root)
    spec = feature / "spec.md" if feature else None
    probe = probe_adapter(root, config, adapter)
    principles = resolve_principles(root, config, adapter)

    emit(
        {
            "REPO_ROOT": str(root),
            "FEATURE_DIR": str(feature) if feature else "",
            "FEATURE_SPEC": str(spec) if spec else "",
            "IMPL_PLAN": str(feature / "plan.md") if feature else "",
            "TASKS": str(feature / "tasks.md") if feature else "",
            "DESIGN_DOC": str(feature / DESIGN_DOC_NAME) if feature else "",
            "LEDGER": str(ledger_path(root)),
            "LEDGER_COUNT": len(load_ledger(root)["decisions"]),
            # Where the principles came from: cli, adapter or default. `default`
            # means the design system supplied none.
            "PRINCIPLES_SOURCE": principles["principles_source"],
            "PRINCIPLES_VERSION": principles["principles_version"],
            "PRINCIPLES_ORIGIN": principles["origin"],
            "PRINCIPLES_COUNT": principles["principle_count"],
            "PRINCIPLES_HAS_PROSE": bool(principles["prose"]),
            "PRINCIPLES_DISABLED": principles["disabled"],
            # Cited as requirements only where something can check them.
            "PRINCIPLES_UNENFORCEABLE": principles["unenforceable"],
            "ADAPTER": adapter.get("id", ""),
            "ADAPTER_NAME": adapter.get("name", ""),
            # Empty when the design system could not actually be reached. The
            # commands treat that as a gate failure, not a pass.
            "CAPABILITIES": probe["capabilities"],
            "HAS_TOKENS": "tokens" in probe["capabilities"],
            "REQUIRED_DIMENSIONS": effective_dimensions(config, probe["capabilities"]),
            "MAPPED_CAPABILITIES": mapped_capabilities(adapter),
            # Which rungs of the reuse ladder the design system can be asked
            # about, and which the command has to walk on documentation alone.
            "LADDER_SUPPORT": ladder_support(probe["capabilities"]),
            "REACHABLE": probe["reachable"],
            "UNREACHABLE_REASON": probe.get("reason", ""),
            "UI_BEARING": detect_ui_bearing(spec),
            "SPEC_EXISTS": bool(spec and spec.is_file()),
            "DESIGN_DOC_EXISTS": bool(feature and (feature / DESIGN_DOC_NAME).is_file()),
            "CONFIG": config,
        }
    )


def cmd_principles(args: argparse.Namespace) -> None:
    root = repo_root()
    config = load_config(root)
    adapter = load_adapter(root, config)
    kinds = (args.applies_to or "").split(",") if args.applies_to else None
    result = resolve_principles(root, config, adapter, kinds)
    if args.dimension:
        result["principles"] = [
            entry for entry in result["principles"] if entry.get("dimension") == args.dimension
        ]
        result["principle_count"] = len(result["principles"])
        result["unenforceable"] = [
            str(entry.get("id", "")) for entry in result["principles"]
            if not entry.get("enforceable")
        ]
    emit(result)


def cmd_context(args: argparse.Namespace) -> None:
    root = repo_root()
    config = load_config(root)
    adapter = load_adapter(root, config)
    kinds = (args.applies_to or "").split(",") if args.applies_to else None
    emit(
        build_context(
            root, config, adapter, args.phase,
            kinds=kinds, components=args.component, query=args.query,
        )
    )


def cmd_workflow(args: argparse.Namespace) -> None:
    root = repo_root()
    emit(workflow_status(root, load_config(root)))


def cmd_rfc(args: argparse.Namespace) -> None:
    source = args.source
    if source in (None, "-"):
        emit(parse_rfc(sys.stdin.read(), origin="stdin"))
        return
    path = Path(source)
    if path.is_file():
        emit(parse_rfc(path.read_text(encoding="utf-8"), origin=str(path)))
        return
    # Not a file: treat the argument itself as the RFC. A one-line RFC is a
    # legitimate starting point; the clarify phase exists for exactly that.
    result = parse_rfc(source, origin="argument")
    if "\n" not in source and re.search(r"\.(md|markdown|txt)$", source.strip(), re.I):
        result["warnings"].insert(0, f"{source} looks like a path but no such file exists")
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
        "validate": ["target"],
        "tokens": ["theme"],
        "breakpoints": ["theme"],
        "report_gap": ["title", "body"],
    }.get(args.capability, [])
    for key, value in zip(positional, args.args):
        params[key] = value

    result = run_capability(root, config, adapter, args.capability, params)

    fields = [field.strip() for field in (args.fields or "").split(",") if field.strip()]
    if fields and result.get("available") and result.get("data") is not None:
        result["bytes_unprojected"] = result.get("bytes", 0)
        result["projected_fields"] = fields
        result["data"] = project_fields(result["data"], fields)
        result["bytes"] = payload_bytes(result["data"])

    emit(result)


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
        elif args.value.lstrip().startswith("{"):
            raw = args.value
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
    common.add_argument(
        "--json", action="store_true", help="accepted for convention; output is always JSON"
    )

    parser = argparse.ArgumentParser(prog="design", description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("gate", parents=[common]).set_defaults(func=cmd_gate)

    query = sub.add_parser("query", parents=[common])
    query.add_argument("capability", choices=CAPABILITIES)
    query.add_argument("args", nargs="*")
    query.add_argument(
        "--fields",
        help=(
            "comma-separated keys to keep from the result, for surveying a large answer "
            "cheaply (e.g. --fields name,description); the full answer stays one call away"
        ),
    )
    query.set_defaults(func=cmd_query)

    principles = sub.add_parser("principles", parents=[common])
    principles.add_argument(
        "--applies-to",
        help=f"comma-separated surface kinds this feature involves ({', '.join(SURFACE_KINDS)})",
    )
    principles.add_argument("--dimension", help="return only principles for one dimension")
    principles.set_defaults(func=cmd_principles)

    context = sub.add_parser("context", parents=[common])
    context.add_argument("phase", choices=list(PHASE_CONTEXT))
    context.add_argument("--applies-to", help="surface kinds this feature involves")
    context.add_argument(
        "--component", action="append", help="pull detail for this component (repeatable)"
    )
    context.add_argument("--query", help="search the design system for candidates")
    context.set_defaults(func=cmd_context)

    workflow = sub.add_parser("workflow", parents=[common])
    workflow.add_argument("action", choices=["status"], nargs="?", default="status")
    workflow.set_defaults(func=cmd_workflow)

    rfc = sub.add_parser("rfc", parents=[common])
    rfc.add_argument("source", nargs="?", help="path to the RFC, '-' for stdin, or the text itself")
    rfc.set_defaults(func=cmd_rfc)

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
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - commands degrade on JSON, never a traceback
        emit({"available": False, "error": f"internal error: {type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
