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
    scan [--path <glob>]     raw values and token names in the implementation
    cache stats              how often the design system was actually asked
    cache clear              drop remembered answers for the active feature

Everything emits one compact JSON object on stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol

EXT_ID = "design"
CONFIG_NAME = "design-config.yml"
LOCAL_CONFIG_NAME = "design-config.local.yml"
LEDGER_NAME = "design-decisions.yml"
DESIGN_DOC_NAME = "design-system.md"
# The team's own Definition of Done, next to the config because it is authored
# rather than derived. Optional: most projects will not have one.
DOD_NAME = "definition-of-done.md"
DEFAULT_PRINCIPLES = "principles/default.yml"

# What a principle can apply to. A feature declares which of these it involves,
# and only the matching principles reach its context.
SURFACE_KINDS = ["interactive", "layout", "text", "media", "motion", "any"]

@dataclass(frozen=True)
class Capability:
    """One question the commands know how to ask.

    Everything about a capability in one row. Adding one used to mean editing
    four places -- the name list, `cmd_query`'s positional map, `PROBE_PARAMS`
    and `LADDER_CAPABILITIES` -- with nothing to say they had drifted apart.

    `positional` names what `ds.sh query <capability> a b` means. `probe_with`
    is a call cheap enough to prove the design system is reachable, and only a
    capability that carries one may be probed: `extend`, `validate` and
    `report_gap` may eject a component, run a build or file an issue, and a
    reachability check must never do any of that. `rung` is which step of the
    ladder this capability backs, so an adapter author can see what a missing
    mapping costs before a run does.

    `cacheable` says an answer may be remembered and served again. True for
    every question about what the design system *is*; false for the three that
    act or inspect code that is still changing, because replaying yesterday's
    `validate` verdict, or skipping a second `report_gap`, would be a lie.
    """

    name: str
    positional: tuple[str, ...] = ()
    probe_with: dict[str, str] | None = None
    rung: str | None = None
    note: str = ""
    cacheable: bool = True


# The contract the commands are written against. An adapter maps these to real
# invocations; anything unmapped is reported as unavailable rather than faked.
CAPABILITY_LIST = [
    Capability("describe", probe_with={}),
    Capability("search", ("query",), probe_with={"query": "button"}, rung="reuse"),
    Capability("list_components", probe_with={}),
    Capability("component", ("name",), probe_with={"name": "Button"}, rung="reuse"),
    Capability("pattern", ("name",), rung="compose"),
    Capability("tokens", ("theme",), probe_with={}),
    Capability(
        "breakpoints",
        ("theme",),
        probe_with={},
        note="Its own query because 'use our breakpoints' is unenforceable "
        "unless the agent can find out what they actually are.",
    ),
    Capability(
        "principles",
        probe_with={},
        note="When this answers, it IS the principles for the run; nothing "
        "shipped here is merged into it.",
    ),
    Capability("extend", ("name",), rung="extend", cacheable=False),
    Capability("validate", ("target",), cacheable=False),
    Capability("report_gap", ("title", "body"), rung="create", cacheable=False),
]

CAPABILITY_REGISTRY = {capability.name: capability for capability in CAPABILITY_LIST}
CAPABILITIES = [capability.name for capability in CAPABILITY_LIST]

# How long the design system gets to answer. The probe is held to a shorter
# leash than a real question: it runs before every gate and context call, and a
# system that needs two minutes to say hello is already unusable.
DEFAULT_TIMEOUT = 120
PROBE_TIMEOUT = 30

# How much of a failure to quote back. Enough to recognise the error, not enough
# to bury the JSON object it travels in.
ERROR_DETAIL_CHARS = 500
CLI_PROSE_CHARS = 200

# How many results a listing hands back before the caller has to narrow the
# question. Not a limit on the design system: the full answer is one call away.
SEARCH_HITS_RETURNED = 20
LEDGER_MATCHES_RETURNED = 5
RFC_QUESTIONS_RETURNED = 20

# Below this a document is too thin to have said much, and the clarify phase
# should expect to do real work.
RFC_SHORT_WORDS = 30

# A hit on the name is worth more than a hit buried in prose.
FIELD_WEIGHTS = {"name": 3.0, "usage": 1.5, "description": 1.0}

STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "and", "or", "with", "in", "on",
    "that", "this", "is", "are", "be", "by", "as", "at", "from", "it",
}


def die(message: str, code: int = 1) -> None:
    print(f"[design] {message}", file=sys.stderr)
    # Callers parse stdout, so a refusal is JSON there too, not just stderr text,
    # and it carries the same fail-closed markers an unexpected error would.
    emit(failure_envelope(ACTIVE_COMMAND, message))
    raise SystemExit(code)


# Which subcommand is running. `die` can be reached from deep inside config or
# adapter loading, long before the caller sees a result, and the shape of a
# refusal depends on who is about to read it.
ACTIVE_COMMAND: str | None = None

# The keys each subcommand is read through when it fails. A command body decides
# to stop on `REACHABLE`/`principles_source`, so an envelope that carries neither
# is not a refusal it can act on — it reads as a malformed response and the guard
# never fires. Failing closed has to survive the failure being an unexpected one.
FAILURE_MARKERS: dict[str, dict[str, Any]] = {
    "gate": {
        "REACHABLE": False,
        "CAPABILITIES": [],
        "PRINCIPLES_SOURCE": "unavailable",
        "REQUIRED_DIMENSIONS": [],
        "HAS_TOKENS": False,
        "DOD_ITEMS": [],
    },
    "principles": {"principles_source": "unavailable", "principles": [], "principle_count": 0},
    "context": {"reachable": False, "principles": {"principles_source": "unavailable"}},
    "workflow": {"next": "stop", "complete": False},
}


def failure_envelope(command: str | None, message: str) -> dict:
    """A refusal shaped like the answer its caller is about to read.

    Every command body guards on the same two things — the design system was not
    reachable, or no principles are in force — and stops. An error that arrives
    without those keys slips past both guards, which is how a crash turns into a
    run that proceeds on no principles at all.
    """
    envelope: dict[str, Any] = {"available": False, "error": message}
    envelope.update(FAILURE_MARKERS.get(command or "", {}))
    if command in ("gate", "context", "principles"):
        envelope["UNREACHABLE_REASON"] = message
    return envelope


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
    "SPECKIT_DESIGN_CACHE_ENABLED": ("cache.enabled", bool),
    "SPECKIT_DESIGN_CACHE_TTL_MINUTES": ("cache.ttl_minutes", int),
}


TRUE_WORDS = {"1", "true", "yes", "on"}
FALSE_WORDS = {"0", "false", "no", "off"}


def coerce(value: str, kind: type) -> Any:
    if kind is bool:
        # Refused rather than read as false: `SPECKIT_DESIGN_GATE_ENFORCE=ture`
        # would otherwise switch the gate off without a word.
        word = value.strip().lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
        words = ", ".join(sorted(TRUE_WORDS | FALSE_WORDS))
        die(f"could not read '{value}' as a boolean. One of: {words}")
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


# Anything detection could not read, reported by the gate rather than swallowed.
DETECTION_NOTES: list[str] = []

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
    except FileNotFoundError:
        pass  # No package.json at all is the ordinary case, not a problem.
    except (OSError, ValueError, AttributeError) as exc:
        # A package.json that exists and cannot be read is different: detection
        # silently falls through to static-json and the project is left
        # wondering why its component library was not recognised.
        DETECTION_NOTES.append(f"could not read {base / 'package.json'}: {exc}")
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


# Probed in this order; the first mapped one is used. Only a capability that
# declares a `probe_with` call can stand in for reachability.
PROBE_PARAMS = {c.name: c.probe_with for c in CAPABILITY_LIST if c.probe_with is not None}


def probe_adapter(ds: DesignSystem) -> dict:
    """Actually reach the design system before reporting what it can do.

    Reading capabilities off the adapter YAML alone would report a full set for
    a CLI that is not installed, which would make the commands' fail-closed
    guard unreachable: the gate would pass precisely when it cannot check
    anything. So this spends one call to find out.
    """
    mapped = mapped_capabilities(ds.adapter)
    if not mapped:
        return {"capabilities": [], "reachable": False, "reason": "adapter maps no capabilities"}

    probe = next((name for name in PROBE_PARAMS if name in mapped), None)
    if probe is None:
        # Only capabilities with side effects are mapped. Calling one to see
        # whether it answers would file an issue or eject a component on every
        # gate, so reachability stays unproven and the gate fails closed.
        return {
            "capabilities": [],
            "reachable": False,
            "reason": (
                f"adapter maps only {', '.join(mapped)}, none of which is safe to probe; "
                f"map one of {', '.join(PROBE_PARAMS)}"
            ),
        }
    # Never served from the cache: this call is the proof of reach, and a
    # remembered answer proves only that the system was there earlier.
    result = ds.ask(probe, timeout=PROBE_TIMEOUT, fresh=True, **PROBE_PARAMS[probe])

    if not result.get("available"):
        return {
            "capabilities": [],
            "reachable": False,
            "probed": probe,
            "reason": result.get("reason", "design system could not be reached"),
        }
    return {"capabilities": mapped, "reachable": True, "probed": probe}


@dataclass
class DesignSystem:
    """One resolved view of the project and the system it asks.

    `(root, config, adapter)` used to be threaded through nine functions and
    rebuilt at the top of every subcommand. That cost three things: the same
    three-line preamble in every `cmd_*`, no place to cache anything, and
    signatures that drifted out of order.

    The caching is the part that shows up in a run. `gate` probes the design
    system, then each `context <phase>` probed it again, and for a CLI-backed
    system resolved its principles a second time too -- so a phase transition
    paid for four round-trips where two would do. Resolving once per process
    fixes that without any command having to know it happened.
    """

    root: Path
    config: dict
    adapter: dict
    _probe: dict | None = field(default=None, repr=False)
    _cache: AnswerCache | None = field(default=None, repr=False)

    @classmethod
    def resolve(cls) -> DesignSystem:
        root = repo_root()
        config = load_config(root)
        return cls(root, config, load_adapter(root, config))

    @property
    def base(self) -> Path:
        """Where paths and subprocesses resolve. `cwd` points a monorepo at one
        package, and it has to mean the same thing for both kinds of capability."""
        return self.root / self.config["cwd"] if self.config.get("cwd") else self.root

    @property
    def adapter_id(self) -> str:
        return self.adapter.get("id", "")

    @property
    def probe(self) -> dict:
        if self._probe is None:
            self._probe = probe_adapter(self)
        return self._probe

    @property
    def capabilities(self) -> list[str]:
        """What the design system could actually be reached for just now."""
        return self.probe["capabilities"]

    @property
    def reachable(self) -> bool:
        return self.probe["reachable"]

    @property
    def cache(self) -> AnswerCache:
        if self._cache is None:
            self._cache = AnswerCache.for_project(self)
        return self._cache

    def ask(
        self, capability: str, timeout: int | None = None, fresh: bool = False, **params: Any
    ) -> dict:
        """Ask one question, answered from memory where that is honest.

        Caching lives here rather than in `run_capability`, which routes and
        nothing else. `fresh` skips the lookup but still counts the call and
        stores what came back.
        """
        spec = (self.adapter.get("capabilities") or {}).get(capability)
        # A file read costs what a cache read costs, and the file may have been
        # regenerated since, so only a process or a server round-trip is worth
        # remembering -- and only those are what "the CLI was asked" means.
        remote = bool(spec) and not reads_a_file(spec)
        entry = CAPABILITY_REGISTRY.get(capability)
        cacheable = remote and entry is not None and entry.cacheable
        key = self.cache.key(self, capability, params) if cacheable else ""

        if cacheable and not fresh:
            hit = self.cache.get(key)
            if hit is not None:
                self.cache.count(capability, hit=True)
                return hit

        result = run_capability(self, capability, params, timeout=timeout)
        if remote:
            self.cache.count(capability, hit=False)
        if cacheable and result.get("available"):
            self.cache.put(key, capability, result)
        result["cached"] = False
        return result


# --- answer cache ------------------------------------------------------------

CACHE_DIR_NAME = ".cache"
DEFAULT_CACHE_TTL_MINUTES = 480
# Answers outside a feature (a query before `/speckit.specify` ran) share one scope.
PROJECT_SCOPE = "_project"


@dataclass
class AnswerCache:
    """Answers the design system already gave, and how often it was asked.

    Every `ds.sh` call is its own process, so the per-process probe cache on
    `DesignSystem` never saw a second question. A run asked the same `component
    Popover` in the context hook, the gate, every implement task and every
    validation round, and each was a real CLI call.

    Three rules keep this from changing what an answer means:

    * Only answers are remembered. A failure to ask is never stored, so an
      outage is re-tried rather than replayed, and nothing here can turn
      "unreachable" into a cached "found nothing".
    * Answers are scoped to the active feature and expire after `ttl_minutes`.
      A new feature starts from what the design system says now.
    * The key covers the whole adapter and the configured version, so editing
      a mapping or bumping `design_system_version` is a different question.

    The counts are kept whether or not caching is on. They are what turns
    "the CLI is called extremely often" into a number, before and after.
    """

    path: Path | None
    enabled: bool
    ttl_seconds: int
    scope: str
    data: dict = field(default_factory=dict)
    dirty: bool = False

    @classmethod
    def for_project(cls, ds: DesignSystem) -> AnswerCache:
        settings = ds.config.get("cache") or {}
        feature = feature_dir(ds.root)
        scope = feature.name if feature else PROJECT_SCOPE
        directory = ext_dir(ds.root)
        # No extension directory means no project to keep state in: count in
        # memory and remember nothing, rather than creating one as a side effect.
        path = directory / CACHE_DIR_NAME / f"{scope}.json" if directory.is_dir() else None
        cache = cls(
            path=path,
            enabled=bool(settings.get("enabled", True)),
            ttl_seconds=int(settings.get("ttl_minutes", DEFAULT_CACHE_TTL_MINUTES)) * 60,
            scope=scope,
        )
        cache.data = cache._load()
        return cache

    def _load(self) -> dict:
        empty = {"answers": {}, "calls": {}, "hits": {}}
        if not self.path or not self.path.is_file():
            return empty
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A corrupt cache is a cold cache, never an error a run stops on.
            return empty
        if not isinstance(data, dict):
            return empty
        for name in empty:
            if not isinstance(data.get(name), dict):
                data[name] = {}
        return data

    @staticmethod
    def key(ds: DesignSystem, capability: str, params: dict) -> str:
        material = {
            "capability": capability,
            "params": params,
            "adapter": ds.adapter,
            "base": str(ds.base),
            "version": ds.config.get("design_system_version") or "",
        }
        encoded = json.dumps(material, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str) -> dict | None:
        if not self.enabled:
            return None
        entry = self.data["answers"].get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("answer"), dict):
            return None
        try:
            age = time.time() - float(entry.get("at", 0))
        except (TypeError, ValueError):
            return None
        if age < 0 or age > self.ttl_seconds:
            return None
        answer = dict(entry["answer"])
        answer["cached"] = True
        answer["cached_age_seconds"] = int(age)
        return answer

    def put(self, key: str, capability: str, answer: dict) -> None:
        if not self.enabled:
            return
        stored = {k: v for k, v in answer.items() if k not in ("cached", "cached_age_seconds")}
        self.data["answers"][key] = {"at": time.time(), "capability": capability, "answer": stored}
        self.dirty = True
        self.save()

    def count(self, capability: str, hit: bool) -> None:
        bucket = self.data["hits" if hit else "calls"]
        bucket[capability] = int(bucket.get(capability, 0)) + 1
        self.dirty = True
        self.save()

    def save(self) -> None:
        if not self.path or not self.dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ignore = self.path.parent / ".gitignore"
            if not ignore.exists():
                # Derived state: nothing in here should ever be committed.
                ignore.write_text("*\n", encoding="utf-8")
            scratch = self.path.with_suffix(".tmp")
            scratch.write_text(json.dumps(self.data, default=str), encoding="utf-8")
            os.replace(scratch, self.path)
            self.dirty = False
        except OSError:
            # A read-only checkout still gets its answers, just not remembered.
            self.path = None

    def stats(self) -> dict:
        calls = self.data["calls"]
        hits = self.data["hits"]
        live = sum(
            1 for key in self.data["answers"] if self.get(key) is not None
        )
        return {
            "scope": self.scope,
            "enabled": self.enabled,
            "ttl_minutes": self.ttl_seconds // 60,
            "path": str(self.path) if self.path else "",
            # Real round-trips to the design system's CLI or MCP server.
            # File-backed capabilities are reads, not calls, and are not counted.
            "calls": sum(int(v) for v in calls.values()),
            # Questions answered from memory instead.
            "hits": sum(int(v) for v in hits.values()),
            "by_capability": {
                name: {"calls": int(calls.get(name, 0)), "hits": int(hits.get(name, 0))}
                for name in sorted(set(calls) | set(hits))
            },
            "entries": live,
        }

    def clear(self) -> dict:
        before = self.stats()
        self.data = {"answers": {}, "calls": {}, "hits": {}}
        if self.path and self.path.is_file():
            try:
                self.path.unlink()
            except OSError:
                pass
        return before


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


class Answer:
    """One capability's response, built in one place.

    Thirteen return statements used to construct this dict by hand, and the
    shape drifted between them: the file-backed paths never carried
    `result_path_missed`, six of the failure paths never carried `bytes`, and a
    caller reading a missing key cannot tell it from a different kind of answer.

    The distinction the two constructors encode is the invariant the whole
    extension rests on. `unavailable` is a failure to *ask* — an outage, a
    missing binary, a changed flag. `answered` is the design system speaking,
    and only then may `found` be false. Collapsing the two would let a registry
    outage read as an empty design system and push the ladder toward Create.
    """

    @staticmethod
    def unavailable(capability: str, reason: str, **extra: Any) -> dict:
        return {"capability": capability, "available": False, "reason": reason, **extra}

    @staticmethod
    def cost_note(capability: str, result: dict) -> str | None:
        """What a bulky or unnarrowed answer costs, phrased as the fix.

        Reads `bytes` and `result_path_missed` off an answer, so it belongs to
        whatever builds them. A capability mapped to a command it shares with a
        broader one (`breakpoints` onto the token call is the usual pair)
        answers with the whole payload unless the adapter carves out a slice,
        and that is invisible at the call site: the context is simply bigger,
        every phase, every run.
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

    @staticmethod
    def answered(
        capability: str,
        data: Any,
        *,
        found: bool | None = None,
        size: int | None = None,
        missed: bool = False,
        **extra: Any,
    ) -> dict:
        return {
            "capability": capability,
            "available": True,
            "found": (data not in (None, [], {})) if found is None else found,
            "result_path_missed": missed,
            "bytes": payload_bytes(data) if size is None else size,
            "data": data,
            **extra,
        }


@dataclass
class Request:
    """One question, with everything needed to ask it. Passed to a transport so
    the transports stay stateless and orderable."""

    capability: str
    spec: dict
    adapter: dict
    base: Path
    params: dict
    timeout: int


@dataclass
class Fetched:
    """What a transport got back, before anything decided what it means.

    `status` is the three-way the invariant needs: reached and answered,
    reached and explicitly told no, or never reached at all. Only a transport
    knows which of the three happened; only a strategy knows what the payload
    means. Keeping them apart is what stopped `run_capability` being one
    234-line function with both jobs in it.
    """

    status: str  # "ok" | "not_found" | "unreachable"
    document: Any = None
    raw: str = ""
    source: str = ""
    reason: str = ""
    detail: dict = field(default_factory=dict)
    # Whether the adapter was guessing at this payload's shape. A shipped
    # adapter guesses at a CLI's envelope, so a mapping that resolves to
    # nothing probably means the guess missed and the whole payload is worth
    # more than a null. A file-backed adapter knows the shape of the file it
    # points at, so the same miss means the file genuinely does not carry that
    # section -- handing the whole document back there would turn "no
    # principles in this inventory" into "here is the entire inventory".
    shape_is_guessed: bool = False

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class Transport(Protocol):
    """How one capability is reached.

    A new way of asking a design system is a new class and one registry entry.
    It never edits the dispatcher, which is the property the README's promise of
    "CLI, MCP, or files" needs and did not have: adding a third transport used
    to mean operating inside a 234-line function between the other two.
    """

    def handles(self, request: Request) -> bool: ...

    def fetch(self, request: Request) -> Fetched: ...


def reads_a_file(spec: dict) -> bool:
    """Whether a mapping is answered from a file rather than by asking anything."""
    return bool(spec.get("read_file"))


class FileTransport:
    """A capability answered by reading a file the project already generates."""

    def handles(self, request: Request) -> bool:
        return reads_a_file(request.spec)

    def fetch(self, request: Request) -> Fetched:
        target = substitute(
            [request.spec["read_file"]],
            {**request.params, "source": request.adapter.get("source", "")},
        )
        if not target:
            return Fetched(
                "unreachable",
                reason=f"'{request.spec['read_file']}' names no file; set `source` in the config",
            )
        path = request.base / target[0]
        if not path.is_file():
            return Fetched("unreachable", reason=f"{path} not found")
        try:
            document = read_structured(path)
        except ValueError as exc:
            return Fetched("unreachable", reason=str(exc))
        if not isinstance(document, dict):
            return Fetched(
                "unreachable",
                reason=(
                    f"{path} must hold a mapping at top level, "
                    f"got {type(document).__name__}"
                ),
            )
        return Fetched("ok", document=document, source=str(path))


class ProcessTransport:
    """A capability answered by the design system's own CLI."""

    def handles(self, request: Request) -> bool:
        return bool(request.spec.get("bin") or request.adapter.get("bin"))

    def fetch(self, request: Request) -> Fetched:
        spec, adapter = request.spec, request.adapter
        # A capability may name its own binary: filing a gap and ejecting a
        # component are not usually the design system's own CLI. Its own binary
        # means the adapter's global flags and envelope do not apply to it.
        own_binary = bool(spec.get("bin"))
        binary = spec.get("bin") or adapter.get("bin") or ""

        merged: dict[str, Any] = {**(spec.get("defaults") or {}), **request.params}
        if adapter.get("registries"):
            merged.setdefault("registries", list(adapter["registries"]))

        argv = shlex.split(binary)
        argv += substitute(list(spec.get("args") or []), merged)
        if not own_binary:
            argv += list(adapter.get("global_args") or [])

        # The envelope describes one CLI's response shape, so it applies to that
        # CLI. Reading another tool's `code` field as this one's error code
        # would turn a filed issue into a reported outage.
        envelope = (adapter.get("envelope") or {}) if not own_binary else {}
        return self.invoke(request, argv, envelope)

    @staticmethod
    def invoke(request: Request, argv: list[str], envelope: dict) -> Fetched:
        """Run a finished argv and sort the outcome into the three-way.

        Takes the argv as built, so a transport that delegates here (MCP) hands
        over its arguments once: splitting or substituting them a second time
        would break a client path with a space in it, and expand a `{...}` that
        arrived inside a query.
        """
        spec = request.spec
        try:
            proc = subprocess.run(
                argv,
                cwd=request.base,
                capture_output=True,
                text=True,
                timeout=request.timeout,
                check=False,
            )
        except FileNotFoundError:
            return Fetched(
                "unreachable",
                reason=f"'{argv[0]}' not found. Is the design system CLI installed?",
            )
        except subprocess.TimeoutExpired:
            return Fetched(
                "unreachable", reason=f"CLI timed out after {request.timeout}s"
            )

        command = shlex.join(argv)
        raw = proc.stdout.strip()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None  # CLI printed prose; hand it back verbatim

        error_key = envelope.get("error_code_key")
        code = parsed.get(error_key) if (isinstance(parsed, dict) and error_key) else None

        # A code the adapter declares as "not found" is a real answer: the
        # design system was reached and does not have this thing.
        if code and code in set(spec.get("not_found_codes") or []):
            return Fetched(
                "not_found", source=command, detail={"error_code": code, "command": command}
            )

        # Anything else that failed is a failure to ask, not an answer.
        if code or proc.returncode != 0:
            detail = (proc.stderr or "").strip() or (
                raw if parsed is None else json.dumps(parsed)
            )
            return Fetched(
                "unreachable",
                reason=(detail or "non-zero exit").strip()[:ERROR_DETAIL_CHARS],
                detail={
                    "error_code": code,
                    "exit_code": proc.returncode,
                    "command": command,
                },
            )

        mapped_slice = bool(
            spec.get("result_path") or spec.get("result_paths") or spec.get("pick")
        )
        if raw and parsed is None and (mapped_slice or envelope):
            # The adapter was written against a JSON CLI. Prose here means a
            # flag or output format changed: a failure to ask, not an answer.
            return Fetched(
                "unreachable",
                reason=f"expected JSON from the CLI, got: {raw[:CLI_PROSE_CHARS]}",
                detail={"exit_code": proc.returncode, "command": command},
            )

        return Fetched(
            "ok",
            document=parsed,
            raw=raw,
            source=command,
            detail={"command": command},
            shape_is_guessed=True,
        )


class McpTransport:
    """A capability answered by an MCP server.

    The README has promised "CLI, MCP, or files" from the start. It could not be
    written while dispatch was one function: there was no seam to add it at. It
    is here to keep that promise and to prove the seam holds — a transport is a
    class and a registry entry, nothing else.

    The call itself is delegated to a command the adapter names, because this
    extension does not ship an MCP client and should not grow one: stdio
    framing, session handling and auth belong to whatever the project already
    uses to talk to its servers.

        capabilities:
          search:
            mcp:
              server: "design-system"
              tool: "search_components"
              client: "npx @acme/mcp-call"     # optional; defaults to mcp.client
            args: ["--query", "{query}"]
    """

    def handles(self, request: Request) -> bool:
        return bool(request.spec.get("mcp"))

    def fetch(self, request: Request) -> Fetched:
        mcp = request.spec["mcp"]
        if not isinstance(mcp, dict) or not mcp.get("tool"):
            return Fetched("unreachable", reason="mcp mapping needs a `tool`")

        client = mcp.get("client") or (request.adapter.get("mcp") or {}).get("client")
        if not client:
            return Fetched(
                "unreachable",
                reason="no MCP client configured. Name one under `mcp.client`.",
            )

        argv = shlex.split(client)
        if mcp.get("server"):
            argv += ["--server", str(mcp["server"])]
        argv += ["--tool", str(mcp["tool"])]
        argv += substitute(
            list(request.spec.get("args") or []),
            {**(request.spec.get("defaults") or {}), **request.params},
        )

        # Reuse the process transport's failure semantics rather than restating
        # them: an MCP server that cannot be reached is exactly as unavailable
        # as a CLI that is not installed, and must never read as an empty
        # design system. The client is not the design system's CLI, so the
        # adapter's envelope does not describe its output.
        return ProcessTransport.invoke(request, argv, envelope={})


# Ordered: the first transport that recognises the mapping is used.
TRANSPORTS: tuple[Transport, ...] = (FileTransport(), McpTransport(), ProcessTransport())


class Strategy(Protocol):
    """How to answer from whatever the transport returned.

    The other axis. A transport knows where the bytes came from; a strategy
    knows what question they answer. Keeping the weighted inventory search in
    here rather than in the dispatcher is also what keeps it out of the layer
    that is supposed to know nothing about any particular design system.
    """

    def handles(self, request: Request) -> bool: ...

    def answer(self, request: Request, fetched: Fetched) -> dict: ...


class KeyFieldLookup:
    """One record out of a list, by name. `component`, `pattern`, `extend`."""

    def handles(self, request: Request) -> bool:
        return bool(request.spec.get("key_field")) and bool(request.params.get("name"))

    def answer(self, request: Request, fetched: Fetched) -> dict:
        sliced, _ = slice_result(fetched.document, request.spec)
        if not isinstance(sliced, list):
            return SliceOnly().answer(request, fetched)

        key_field = request.spec["key_field"]
        wanted = str(request.params["name"]).lower()
        match = next(
            (
                item
                for item in sliced
                if isinstance(item, dict)
                and str(item.get(key_field, "")).lower() == wanted
            ),
            None,
        )
        return Answer.answered(
            request.capability, match, found=match is not None, source=fetched.source
        )


class WeightedSearch:
    """Rank an inventory's sections against a query.

    Weighted per field rather than one bag of words: a raw overlap count makes
    every candidate tie at 1 on short descriptions, so results come back in
    insertion order and "pull detail on the strongest hits" has nothing to act
    on.
    """

    def handles(self, request: Request) -> bool:
        return bool(request.spec.get("match_fields")) and not request.params.get("name")

    def answer(self, request: Request, fetched: Fetched) -> dict:
        spec, params = request.spec, request.params
        if not params.get("query"):
            return Answer.unavailable(
                request.capability, f"'{request.capability}' needs a query"
            )

        query_tokens = set(normalize(params["query"]))
        document = fetched.document if isinstance(fetched.document, dict) else {}
        hits = []
        for section in spec.get("search_keys") or []:
            for item in document.get(section) or []:
                if not isinstance(item, dict):
                    continue
                score = 0.0
                for field_name in spec["match_fields"]:
                    tokens = set(normalize(str(item.get(field_name, ""))))
                    if not tokens or not query_tokens:
                        continue
                    overlap = query_tokens & tokens
                    if overlap:
                        weight = FIELD_WEIGHTS.get(field_name, 1.0)
                        score += weight * len(overlap) / len(query_tokens)
                if score:
                    hits.append({"kind": section, "score": round(score, 3), **item})

        # Ties break on name so ordering is stable rather than positional.
        hits.sort(key=lambda entry: (-entry["score"], str(entry.get("name", ""))))
        top = hits[:SEARCH_HITS_RETURNED]
        return Answer.answered(
            request.capability, top, found=bool(hits), source=fetched.source
        )


class SliceOnly:
    """The default: hand back the part of the payload the adapter mapped."""

    def handles(self, request: Request) -> bool:
        return True

    def answer(self, request: Request, fetched: Fetched) -> dict:
        extra = dict(fetched.detail)
        extra.pop("error_code", None)

        # A CLI that printed nothing at all was reached and had nothing to say.
        if fetched.document is None and not fetched.raw:
            return Answer.answered(
                request.capability, None, found=False, size=0, **extra
            )

        # Prose from a CLI the adapter did not promise JSON for is still the
        # design system speaking. Hand it back verbatim.
        if fetched.document is None and fetched.raw:
            return Answer.answered(request.capability, fetched.raw, found=True, **extra)

        data, missed = slice_result(fetched.document, request.spec)
        if missed and fetched.shape_is_guessed:
            # The guess missed, so hand back what the design system actually
            # said instead of a null that reads as "it has nothing".
            data = fetched.document

        if fetched.source and "source" not in extra and "command" not in extra:
            extra["source"] = fetched.source

        # A file-backed adapter knows the shape of the file it points at, so a
        # mapping that resolves to nothing means the file genuinely does not
        # carry that section.
        return Answer.answered(request.capability, data, missed=missed, **extra)


STRATEGIES: tuple[Strategy, ...] = (KeyFieldLookup(), WeightedSearch(), SliceOnly())


def run_capability(
    ds: DesignSystem, capability: str, params: dict[str, Any], timeout: int | None = None
) -> dict:
    """Ask the design system one question, through whatever the adapter maps.

    Routing only. Reaching the system is a transport's job and interpreting the
    answer is a strategy's, which is what lets a new transport be a class rather
    than a branch.
    """
    spec = (ds.adapter.get("capabilities") or {}).get(capability)
    if not spec:
        return Answer.unavailable(
            capability, f"adapter '{ds.adapter.get('id')}' does not map '{capability}'"
        )

    request = Request(
        capability=capability,
        spec=spec,
        adapter=ds.adapter,
        base=ds.base,
        params=params,
        timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
    )

    transport = next((t for t in TRANSPORTS if t.handles(request)), None)
    if transport is None:
        return Answer.unavailable(capability, "no binary configured")

    fetched = transport.fetch(request)
    if fetched.status == "unreachable":
        return Answer.unavailable(capability, fetched.reason, **fetched.detail)
    if fetched.status == "not_found":
        return Answer.answered(
            capability, None, found=False, size=0, **fetched.detail
        )

    strategy = next(s for s in STRATEGIES if s.handles(request))
    return strategy.answer(request, fetched)


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


def surface_kinds(value: str | None) -> list[str] | None:
    """`--applies-to interactive,layout` as a list. None means unfiltered, which
    is not the same as an empty list: every principle applies rather than none."""
    if not value:
        return None
    return [kind.strip() for kind in value.split(",") if kind.strip()] or None


def read_structured(path: Path) -> Any:
    """Read a JSON or YAML file. Adapters point at whatever the design system
    already publishes, and that is JSON about as often as it is YAML."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    if path.suffix.lower() in {".yml", ".yaml"}:
        # Parsed here rather than through `load_yaml`, which exits the process:
        # a broken inventory is one capability that cannot answer, and the
        # callers already report a ValueError as exactly that.
        import yaml

        try:
            return yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"{path} is not valid YAML: {exc}") from exc
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


def applies_to_kinds(rule: dict) -> set[str]:
    """The surface kinds one principle claims, as a set.

    A principle that genuinely bears on two kinds has only one natural way to
    say so — `applies_to: [interactive, layout]` — and a design system writing
    its own principles will reach for it. Reading that as a scalar used to raise
    `unhashable type: 'list'` from the membership test below, which surfaced as
    an internal-error envelope with no `principles_source` at all: the gate went
    on reporting the principles as present and authoritative while the phase
    that writes them into the spec got nothing. Accepting both shapes is the
    same promise `normalize_principles` already makes about the document.
    """
    applies = rule.get("applies_to", "any")
    if applies in (None, ""):
        return {"any"}
    if isinstance(applies, (list, tuple, set)):
        kinds = {str(kind).strip() for kind in applies if str(kind).strip()}
        return kinds or {"any"}
    return {str(applies).strip() or "any"}


def select_principles(rules: list[dict], kinds: list[str] | None, disabled: set[str]) -> tuple:
    """Filter to what this feature actually involves. Anything without an
    `applies_to` is unconditional, because a design system writing free-form
    principles cannot be expected to classify them."""
    wanted = {kind.strip() for kind in (kinds or []) if kind.strip()}
    selected, skipped = [], 0
    for rule in rules:
        if str(rule.get("id", "")) in disabled:
            continue
        applies = applies_to_kinds(rule)
        if wanted and "any" not in applies and not (applies & wanted):
            skipped += 1
            continue
        selected.append(rule)
    return selected, skipped


def resolve_principles(ds: DesignSystem, kinds: list[str] | None = None) -> dict:
    """The principles in force, resolved from exactly one source.

        1. the design system's CLI        (`principles` capability, invoked)
        2. adapter-provided static data   (inventory key, or a file it ships)
        3. the small default set shipped here

    The first one that answers wins **outright**. The default set is a fallback,
    not a floor: merging it into a real design system's principles would mean
    holding that system to rules it never wrote.
    """
    settings = ds.config.get("principles") or {}
    disabled = {str(entry) for entry in (settings.get("disabled") or [])}
    attempts: list[dict] = []

    spec = (ds.adapter.get("capabilities") or {}).get("principles") or {}
    is_file_backed = bool(spec.get("read_file"))

    # 1. The CLI.
    if spec and not is_file_backed:
        result = ds.ask("principles")
        if result.get("available") and result.get("data") not in (None, "", [], {}):
            return _principles_payload(
                "cli", result.get("command", ds.adapter.get("bin", "")),
                result["data"], kinds, disabled, attempts,
            )
        attempts.append({"source": "cli", "reason": result.get("reason", "no principles returned")})

    # 2. Adapter-provided static data: a file the design system ships, either
    #    named in config or mapped by the adapter as a file-backed capability.
    configured = resolve_path(ds.root, str(settings.get("source") or ""))
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
        result = ds.ask("principles")
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

    path = ext_dir(ds.root) / DEFAULT_PRINCIPLES
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


# --- definition of done -------------------------------------------------------

# A DoD line is a markdown bullet and nothing else, optionally written as a
# checkbox. Teams already keep this list; they should not have to restate it as
# a schema to have it checked.
DOD_ITEM = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s*)?(.+?)\s*$")


def dod_items(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in text.splitlines()
        if (match := DOD_ITEM.match(line)) and match.group(1).strip()
    ]


def resolve_dod(ds: DesignSystem) -> dict:
    """The team's Definition of Done, if they keep one.

    Deliberately unlike `resolve_principles`, in every way that matters:

    - **No source but the project's own file.** A DoD is never asked of the
      design system. It is what a team decided among themselves, and no CLI
      can answer for that.
    - **No default set.** The default principles are defensible because they
      cite WCAG and carry no values of their own. There is no equivalent for
      "done": shipping one would hold every project to rules nobody there
      agreed to, and produce findings against them.
    - **No file is the normal case, not a failure.** Absent, this is simply
      off, and nothing downstream mentions it. Gating would make a DoD
      mandatory, which is the opposite of optional.

    It lives next to the config rather than in `.specify/memory/` because it is
    authored, not derived. The ledger there can go stale and be rebuilt from
    the design system; this cannot be rebuilt from anything. Clearing memory to
    re-derive the ledger must not take the team's own rules with it.
    """
    settings = ds.config.get("dod") or {}
    if not isinstance(settings, dict):
        # Someone wrote the list inline under `dod:`. A natural guess, and the
        # gate must say where it actually goes rather than crash on it.
        return {
            "items": [],
            "source": "",
            "error": f"dod: expected a mapping with `source`; the list itself belongs in {DOD_NAME}",
        }
    configured = str(settings.get("source") or "")
    path = resolve_path(ds.root, configured or DOD_NAME)
    if path:
        return {"items": dod_items(read_text(path)), "source": str(path), "error": ""}
    # Nothing configured and no file: there is no DoD, which is fine and silent.
    # A path someone *did* configure and that does not resolve is the opposite:
    # they believe their rules are being enforced, and they are not.
    return {
        "items": [],
        "source": "",
        "error": f"dod.source: {configured} not found" if configured else "",
    }


# --- focused context ----------------------------------------------------------

# What each phase is given up front, named by the key it actually arrives under.
# Everything else stays one query away; nothing here is a ceiling on what the
# agent may ask for.
#
# `includes` used to list `rfc`, `spec` and `plan` too, and `named_components`
# for a section delivered as `components`. Those are files on disk that this
# command has no business inlining — but a response advertising keys it does not
# carry is a contract that reads as an empty answer. They are reported
# separately, as what the phase should go and read for itself.
PHASE_CONTEXT = {
    "clarify": ["principles"],
    "specify": ["principles", "candidates"],
    "plan": ["principles", "components", "tokens", "breakpoints"],
    "implement": ["components", "tokens"],
    "validate": ["principles", "components"],
    "verify": ["principles"],
}

# The artifacts a phase works from, which it reads itself. Named so a caller can
# see the whole input to a phase in one place, not so this command fetches them.
PHASE_ARTIFACTS = {
    "clarify": ["rfc"],
    "specify": ["rfc"],
    "plan": ["spec"],
    "implement": ["plan"],
    "validate": ["spec"],
    "verify": ["spec"],
}

RETRIEVAL_HINT = "ds.sh query {capability} [args]"

# Above this, a capability's answer is large enough to be worth narrowing. Not a
# limit and not a filter: nothing is dropped, the size is just said out loud
# where the person tuning the adapter will see it.
LARGE_PAYLOAD_BYTES = 8192


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


def unasked(what: str, result: dict) -> str:
    """The note for a question that could not be put, as opposed to answered."""
    return f"{what}: could not ask the design system ({result.get('reason', 'unavailable')})"


def _bulk_section(ds: DesignSystem, payload: dict, capability: str, note: bool = True) -> dict:
    """Ask for one of the big shared sections and record what it cost.

    `tokens` and `breakpoints` are fetched the same way and were written out
    twice. The cost note is optional because breakpoints has a more specific
    thing to say when it answered with the token payload verbatim.
    """
    result = ds.ask(capability)
    payload[capability] = result.get("data") if result.get("available") else None
    if not result.get("available") and capability in ds.capabilities:
        # Mapped and reached at probe time, then failed. A null section here
        # would read as "the design system has no tokens".
        payload["notes"].append(unasked(capability, result))
    if note and result.get("available"):
        message = Answer.cost_note(capability, result)
        if message:
            payload["notes"].append(message)
    return result


def build_context(
    ds: DesignSystem,
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
    probe = ds.probe
    principles = resolve_principles(ds, kinds)

    payload: dict[str, Any] = {
        "phase": phase,
        # Every name here is a key of this object. Anything the phase works from
        # but has to open itself is under `read_from_artifacts`.
        "includes": wants,
        "read_from_artifacts": PHASE_ARTIFACTS.get(phase, []),
        "adapter": ds.adapter_id,
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

    if "components" in wants:
        for name in components or []:
            # A component, else a pattern of that name. "Not found" is only
            # said when every question that was put got an answer: an outage
            # on either is a failure to ask, never an empty design system.
            asked = [
                ds.ask(capability, name=name)
                for capability in ("component", "pattern")
                if capability in probe["capabilities"]
            ]
            hit = next((result for result in asked if result.get("found")), None)
            payload["components"][name] = hit.get("data") if hit else None
            if hit:
                continue
            failed = next((result for result in asked if not result.get("available")), None)
            if failed:
                payload["notes"].append(unasked(name, failed))
            elif asked:
                payload["notes"].append(f"{name}: not found in the design system")
            else:
                payload["notes"].append(
                    f"{name}: the adapter maps neither component nor pattern, so it was not asked"
                )
        if not components:
            payload["notes"].append(
                "no components named; ask for them with `query component <Name>` as the work "
                "identifies them"
            )

    if "candidates" in wants and query:
        search = ds.ask("search", query=query)
        payload["candidates"] = search.get("data") if search.get("available") else None
        if not search.get("available"):
            payload["notes"].append(unasked("search", search))

    if "tokens" in wants:
        _bulk_section(ds, payload, "tokens")

    if "breakpoints" in wants:
        breakpoints = _bulk_section(ds, payload, "breakpoints", note=False)
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
                note = Answer.cost_note("breakpoints", breakpoints)
                if note:
                    payload["notes"].append(note)

    payload["sizes"] = context_sizes(payload)
    return payload


# --- autonomous workflow ------------------------------------------------------

FINDING_OPEN = re.compile(r"^\s*-\s*\[ \]\s*(DS-F-\S+)", re.MULTILINE)
FINDING_CLOSED = re.compile(r"^\s*-\s*\[[xX]\]\s*(DS-F-\S+)", re.MULTILINE)
VALIDATION_ROUND = re.compile(r"^##+\s*Validation round\s+(\d+)", re.MULTILINE | re.IGNORECASE)
# What the verify pass leaves behind. Without it there is no artifact to derive
# the phase from, and a phase nothing can observe is one the run skips: status
# went straight from a clean round to `done`, reporting `verify: done` for work
# that never ran. The heading is the same kind of contract as the round heading
# above, in the same file, and `speckit.design.run.md` states the format.
VERIFICATION = re.compile(r"^##+\s*Verification\b", re.MULTILINE | re.IGNORECASE)
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


@dataclass(frozen=True)
class Position:
    """Everything the next step is decided from, read off the artifacts."""

    spec: str
    plan: str
    phases: dict
    rounds: list
    rounds_used: int
    open_findings: list
    last_round_clean: bool
    may_validate_again: bool
    verified: bool


# Ordered: the first rule that fires decides, so priority is the order of this
# list. It was an `elif` chain, which mixed the two things a reader needs to
# separate -- what each phase means, and which one wins when several are true.
# Inserting a phase is now inserting a row; `verify` had to be threaded through
# the middle of the chain by hand.
WORKFLOW_RULES: list[tuple[Any, str, Any]] = [
    (lambda p: p.phases["clarify"] == "blocked",
     "clarify", "the spec still carries [NEEDS CLARIFICATION] markers"),
    (lambda p: not p.spec, "specify", "no specification yet"),
    (lambda p: not p.plan, "plan", "no plan yet"),
    (lambda p: p.phases["implement"] != "done", "implement", "tasks remain open"),
    (lambda p: p.open_findings and not p.may_validate_again, "stop",
     lambda p: (
         f"{len(p.open_findings)} finding(s) still open after {p.rounds_used} validation "
         f"round(s), the configured maximum. This needs a human."
     )),
    (lambda p: bool(p.open_findings), "fix",
     lambda p: f"{len(p.open_findings)} open finding(s) from validation"),
    (lambda p: not p.rounds, "validate", "the implementation has not been validated yet"),
    # The last allowed round raised findings, and they have been fixed since.
    # Another round is exactly what the bound refuses, and calling the fixes
    # checked would let the fixing pass sign off its own work.
    (lambda p: not p.last_round_clean and not p.may_validate_again, "stop",
     lambda p: (
         f"the fixes for round {p.rounds_used}'s findings are unchecked and all "
         f"{p.rounds_used} validation round(s) are used. This needs a human to review them."
     )),
    (lambda p: not p.last_round_clean, "validate",
     lambda p: f"round {p.rounds_used} raised findings that are now fixed; they need checking"),
    (lambda p: not p.verified, "verify",
     "validation is clean; the whole change still needs checking against the RFC's "
     "acceptance criteria, the spec's DS- requirements and the principles in force"),
]

DONE_REASON = "validation was clean and the change was verified against the RFC"


def next_step(position: Position) -> tuple[str, str]:
    for fires, step, reason in WORKFLOW_RULES:
        if fires(position):
            return step, reason(position) if callable(reason) else reason
    return "done", DONE_REASON


def workflow_status(ds: DesignSystem) -> dict:
    """Where the run has got to, derived from the artifacts on disk.

    There is no run-state file. Progress is whatever the spec, plan, tasks and
    design document already say, which means an interrupted run can be resumed
    by reading them, and nothing can drift out of sync with the work itself.
    """
    feature = feature_dir(ds.root)
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
    max_rounds = int((ds.config.get("workflow") or {}).get("max_validation_rounds", 2))

    # A round that raised findings does not become clean because they were
    # ticked off. Only a fresh round with nothing in it ends the loop, which is
    # what stops the fixing pass from also signing off its own fixes.
    last_round_clean = bool(rounds) and not last_round_findings(design)

    tasks_open = len(TASK_OPEN.findall(tasks))
    tasks_done = len(TASK_DONE.findall(tasks))

    implemented = bool(tasks) and tasks_open == 0 and tasks_done > 0
    # Derived from its own artifact, like every other phase. Deriving it from
    # `last_round_clean and implemented` restated the validate row and reported
    # work as done that nothing had recorded.
    verified = bool(VERIFICATION.search(design))
    phases = {
        "clarify": "done" if spec and not CLARIFICATION.search(spec) else
                   ("blocked" if spec else "pending"),
        "specify": "done" if spec else "pending",
        "plan": "done" if plan else "pending",
        "implement": "done" if implemented else ("in_progress" if tasks else "pending"),
        "validate": "done" if last_round_clean else ("in_progress" if rounds else "pending"),
        "verify": "done" if verified else "pending",
    }

    rounds_used = max(rounds) if rounds else 0
    may_validate_again = rounds_used < max_rounds

    nxt, reason = next_step(
        Position(
            spec=spec,
            plan=plan,
            phases=phases,
            rounds=rounds,
            rounds_used=rounds_used,
            open_findings=open_findings,
            last_round_clean=last_round_clean,
            may_validate_again=may_validate_again,
            verified=verified,
        )
    )

    return {
        "feature_dir": str(feature),
        "design_doc": str(feature / DESIGN_DOC_NAME),
        "phases": phases,
        "tasks_open": tasks_open,
        "tasks_done": tasks_done,
        "validation_rounds_used": rounds_used,
        "last_round_clean": last_round_clean,
        "verified": verified,
        "max_validation_rounds": max_rounds,
        "may_validate_again": may_validate_again,
        "open_findings": open_findings,
        "closed_findings": closed_findings,
        "next": nxt,
        "reason": reason,
        "complete": nxt == "done",
    }


# --- mechanical scan ------------------------------------------------------------

# What a validation round can settle without judgement. Raw values and token
# names are string facts about files on disk; spending a model's review on them,
# once per round, is how validation became the slowest phase. The scan states
# them, and the review spends its attention on what only a reader can judge.
SCAN_EXTENSIONS = {
    ".tsx", ".ts", ".jsx", ".js", ".mjs", ".css", ".scss", ".sass", ".less",
    ".vue", ".svelte", ".astro", ".html",
}
SCAN_SKIP_PARTS = {"node_modules", ".git", "dist", "build", ".next", ".specify", "coverage"}
SCAN_REPORTED = 200

RAW_VALUE_PATTERNS = (
    ("color", re.compile(r"(?<![\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")),
    ("color", re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\([^)]*\)")),
    # Zero is not a value anyone tokenises, and 1px is the hairline every
    # system leaves literal; flagging either would bury the real ones.
    ("length", re.compile(r"(?<![\w.#-])(?!0+(?:\.0+)?(?:px|rem|em)\b)(?!1px\b)\d*\.?\d+(?:px|rem|em)\b")),
    ("font", re.compile(r"font-family\s*:\s*(?!\s*var\()(?!\s*inherit)[^;}\n]+|fontFamily\s*:\s*['\"][^'\"]+['\"]")),
)
COMMENT_LINE = re.compile(r"^\s*(?://|/\*|\*|<!--)")
# A token as prose names it: `color.surface.inverse`, `space-6`, `space.*`.
TOKEN_MENTION = re.compile(r"`([a-zA-Z][\w-]*(?:[./][\w*-]+)+|[a-zA-Z][a-zA-Z]*-[\w-]+)`")


def token_names(payload: Any, prefix: str = "") -> set[str]:
    """Every token's dotted name, from a nested token payload.

    A leaf is a scalar, or a mapping that carries its own value (`$value`,
    `value`), which is how DTCG and Style Dictionary files mark one.
    """
    names: set[str] = set()
    if isinstance(payload, dict):
        if prefix and any(key in payload for key in ("$value", "value")):
            return {prefix}
        for key, value in payload.items():
            if str(key).startswith("$"):
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            names |= token_names(value, path) or {path}
    elif prefix:
        names.add(prefix)
    return names


def token_spellings(name: str) -> set[str]:
    """How a token may be written in code: dotted, dashed, or as a CSS variable
    without its group (`color.surface.inverse` -> `surface-inverse`)."""
    parts = [p for p in re.split(r"[./-]", name) if p]
    spellings = {name, "-".join(parts), ".".join(parts), "_".join(parts)}
    if len(parts) > 2:
        spellings.add("-".join(parts[1:]))
    return spellings


def scan_sources(root: Path, patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if (
                path.is_file()
                and path.suffix in SCAN_EXTENSIONS
                and not SCAN_SKIP_PARTS & set(path.relative_to(root).parts)
            ):
                files.add(path)
    return sorted(files)


def contract_mentions(texts: list[str], names: set[str]) -> list[str]:
    """Token names the contract and the spec ask for, in order of first mention.

    A mention counts when its first segment is one of the system's token groups
    (`color.surface.inverse`), or when it is a real token named without its
    group, the way a brief usually writes it (`muted-foreground` for
    `color.muted-foreground`). Anything else, a path like `src/components` or a
    prop like `aria-label`, is not read as a token that does not exist.
    """
    groups = {name.split(".")[0] for name in names}
    ungrouped = {name.split(".", 1)[1] for name in names if "." in name}
    seen: dict[str, None] = {}
    for text in texts:
        for match in TOKEN_MENTION.finditer(text):
            name = match.group(1)
            if re.split(r"[./-]", name)[0] in groups or token_spellings(name) & ungrouped:
                seen.setdefault(name, None)
    return list(seen)


def scan_implementation(ds: DesignSystem, paths: list[str] | None = None) -> dict:
    """Raw values and token names in the implementation, stated rather than judged."""
    validation = ds.config.get("validation") or {}
    patterns = list(paths or validation.get("source_globs") or [])
    exempt = list(validation.get("theme_globs") or [])
    feature = feature_dir(ds.root)
    notes: list[str] = []

    tokens = ds.ask("tokens")
    has_tokens = bool(tokens.get("available") and tokens.get("data") not in (None, {}, []))
    names = token_names(tokens.get("data")) if has_tokens else set()
    if "tokens" in mapped_capabilities(ds.adapter) and not tokens.get("available"):
        notes.append(unasked("tokens", tokens))
    contract = contract_mentions(
        [read_text(feature / DESIGN_DOC_NAME), read_text(feature / "spec.md")] if feature else [],
        names,
    )
    ungrouped = {name.split(".", 1)[1] for name in names if "." in name}
    unknown = [
        name for name in contract
        if not name.endswith("*")
        and not token_spellings(name) & (names | ungrouped)
    ]

    if not patterns:
        notes.append(
            "no source files to scan: pass --path, or set validation.source_globs in the config"
        )
    files = scan_sources(ds.root, patterns)
    exempted = {path for path in scan_sources(ds.root, exempt)} if exempt else set()

    raw: list[dict] = []
    corpus: list[str] = []
    for path in files:
        text = read_text(path)
        corpus.append(text)
        if path in exempted:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if COMMENT_LINE.match(line):
                continue
            for kind, pattern in RAW_VALUE_PATTERNS:
                for match in pattern.finditer(line):
                    raw.append({
                        "file": str(path.relative_to(ds.root)),
                        "line": number,
                        "kind": kind,
                        "value": match.group(0).strip()[:80],
                    })
    code = "\n".join(corpus)
    not_seen = [
        name for name in contract
        if name not in unknown and not name.endswith("*")
        and not any(spelling in code for spelling in token_spellings(name))
    ]

    return {
        "sources": patterns,
        "files_scanned": len(files),
        "theme_files_exempt": len(exempted & set(files)),
        "has_tokens": has_tokens,
        "forbid_raw_values": bool(validation.get("forbid_raw_values", True)),
        # Literal colours, lengths and font stacks outside the theme files.
        "raw_value_count": len(raw),
        "raw_values": raw[:SCAN_REPORTED],
        # Token names design-system.md or the spec asks for.
        "contract_tokens": contract,
        # Asked for, but the design system has no token of that name.
        "unknown_tokens": unknown,
        # Asked for and real, but written nowhere in the scanned code under any
        # usual spelling. A lead for the review, not yet a verdict.
        "tokens_not_seen": not_seen if files else [],
        "notes": notes,
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
    if len(text.split()) < RFC_SHORT_WORDS:
        warnings.append("the RFC is very short; expect the clarify phase to do real work")

    return {
        "origin": origin,
        "title": title,
        "sections": sections,
        "open_questions": sorted(set(q for q in open_questions if q))[:RFC_QUESTIONS_RETURNED],
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
    """How well a prior decision answers this query.

    Overlap as a fraction of the *shorter* side, not of the union. The
    distinction is the whole feature, because of the discipline the ladder
    imposes on the query: surfaces are named by capability, so lookups arrive as
    "a control for picking a start and end date" rather than "DateRangePicker".
    Measured against the union, every word of that description that the stored
    phrase happens not to use counts against the match — so the more carefully a
    surface is described, the less likely it is to recall the decision that
    already answered it. It scored 0.167 against a 0.34 threshold, and Recall,
    the rung the whole ledger exists to serve, quietly never fired.

    Containment asks the question actually being asked: is one of these phrases
    substantially about the other? An exact match is still 1.0, and a two-word
    query against an unrelated decision is still 0.

    Aliases matter more than they look: they are what makes a later,
    differently-worded lookup hit.
    """
    q = set(normalize(query))
    if not q:
        return 0.0
    best = 0.0
    phrases = [decision.get("capability", "")] + list(decision.get("aliases") or [])
    for phrase in phrases:
        tokens = set(normalize(phrase))
        if not tokens:
            continue
        best = max(best, len(q & tokens) / min(len(q), len(tokens)))
    return round(best, 3)


def ledger_lookup(
    root: Path, query: str, threshold: float, current_version: str | None
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
        "matches": matches[:LEDGER_MATCHES_RETURNED],
    }


# The rungs, as the ledger stores them. One spelling, because a ledger is read
# back by string match years after it was written: `compose` and
# `compose-components` sitting side by side is two answers to one question.
# Rung 0 (Recall) is not among them — adopting a prior decision records nothing,
# it reuses the entry that is already there.
RESOLUTIONS = ("reuse", "compose-pattern", "compose-components", "extend", "create")

# What the prose, the design document and an author in a hurry actually write.
# Normalized rather than rejected: the point is one spelling in the file, not a
# spelling test at the point of writing.
RESOLUTION_ALIASES = {
    "compose": "compose-components",
    "compose (components)": "compose-components",
    "compose components": "compose-components",
    "compose_components": "compose-components",
    "compose (pattern)": "compose-pattern",
    "compose pattern": "compose-pattern",
    "compose_pattern": "compose-pattern",
    "pattern": "compose-pattern",
    "reused": "reuse",
    "extended": "extend",
    "created": "create",
    "new": "create",
}

# Two names for "which feature decided this" were in circulation. `decided_in`
# wins because it says when as well as where; `feature` is folded into it.
FEATURE_FIELD_ALIASES = ("feature", "decided_in_feature")


def canonical_resolution(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    text = RESOLUTION_ALIASES.get(text, text)
    return text if text in RESOLUTIONS else None


def ledger_record(root: Path, payload: dict) -> dict:
    required = {"capability", "resolution", "decision"}
    missing = required - set(payload)
    if missing:
        die(f"decision is missing required field(s): {', '.join(sorted(missing))}")

    resolution = canonical_resolution(payload["resolution"])
    if resolution is None:
        die(
            f"unknown resolution {payload['resolution']!r}. "
            f"One of: {', '.join(RESOLUTIONS)}"
        )
    payload["resolution"] = resolution

    for alias in FEATURE_FIELD_ALIASES:
        if alias in payload and not payload.get("decided_in"):
            payload["decided_in"] = payload.pop(alias)
        else:
            payload.pop(alias, None)

    ledger = load_ledger(root)
    decisions = ledger["decisions"]

    # One capability, one active decision. Recording a second without retiring
    # the first is the drift the ladder exists to prevent, and it arrives by
    # accident: the gate records a surface when it walks it, and a later phase
    # records the same surface again from its own notes.
    active = [entry for entry in decisions if entry.get("status") != "superseded"]
    phrase = str(payload["capability"]).strip().lower()
    clash = next(
        (
            entry
            for entry in active
            if str(entry.get("capability", "")).strip().lower() == phrase
        ),
        None,
    )

    # Superseding is explicit: a new decision does not quietly shadow an old one.
    # And it has to retire the decision it clashes with. Naming any other id —
    # a typo, an already-retired one, a different capability's — would pass the
    # check above and still leave two active answers to one question.
    superseded = payload.pop("supersedes", None)
    target = next((entry for entry in active if entry.get("id") == superseded), None)
    if superseded and target is None:
        die(f"supersedes '{superseded}', but no active decision has that id")
    if clash and clash is not target:
        die(
            f"'{payload['capability']}' already has an active decision "
            f"({clash.get('id')}: {clash.get('resolution')}). Adopt it, or supersede it "
            f'explicitly with "supersedes": "{clash.get("id")}".'
        )

    numbers = [
        int(match.group(1))
        for entry in decisions
        if (match := re.match(r"dd-(\d+)$", str(entry.get("id", ""))))
    ]
    payload.setdefault("id", f"dd-{max(numbers, default=0) + 1:03d}")
    if any(entry.get("id") == payload["id"] for entry in decisions):
        die(f"decision id '{payload['id']}' is already taken; leave `id` out to have one assigned")
    payload.setdefault("status", "active")
    payload.setdefault("decided_on", date.today().isoformat())

    if target is not None:
        target["status"] = "superseded"
        target["superseded_by"] = payload["id"]

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
    return len(UI_SIGNALS.findall(read_text(spec_path))) >= SPEC_UI_THRESHOLD


# Which capabilities back which rung, derived from the registry so the two
# cannot drift. The rungs themselves live in `commands/speckit.design.check.md`;
# this only says what is automated.
LADDER_CAPABILITIES: dict[str, list[str]] = {}
for _capability in CAPABILITY_LIST:
    if _capability.rung:
        LADDER_CAPABILITIES.setdefault(_capability.rung, []).append(_capability.name)
# Compose is walked by searching as well as by asking for a named pattern.
LADDER_CAPABILITIES["compose"].append("search")


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
    ds = DesignSystem.resolve()
    root = ds.root
    feature = feature_dir(root)
    spec = feature / "spec.md" if feature else None
    probe = ds.probe
    principles = resolve_principles(ds)
    dod = resolve_dod(ds)

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
            # The team's Definition of Done. Empty is the normal case and means
            # the project keeps none; nothing downstream should mention it then.
            "DOD_ITEMS": dod["items"],
            "DOD_SOURCE": dod["source"],
            # Non-empty only when a configured DoD file did not resolve, which
            # is a misconfiguration to report, not an absent DoD.
            "DOD_ERROR": dod["error"],
            "ADAPTER": ds.adapter_id,
            "ADAPTER_NAME": ds.adapter.get("name", ""),
            # Empty when the design system could not actually be reached. The
            # commands treat that as a gate failure, not a pass.
            "CAPABILITIES": probe["capabilities"],
            "HAS_TOKENS": "tokens" in probe["capabilities"],
            "REQUIRED_DIMENSIONS": effective_dimensions(ds.config, probe["capabilities"]),
            "MAPPED_CAPABILITIES": mapped_capabilities(ds.adapter),
            # Which rungs of the reuse ladder the design system can be asked
            # about, and which the command has to walk on documentation alone.
            "LADDER_SUPPORT": ladder_support(probe["capabilities"]),
            "REACHABLE": probe["reachable"],
            "UNREACHABLE_REASON": probe.get("reason", ""),
            # Non-empty when adapter detection hit something it could not read,
            # which otherwise falls through to static-json without a word.
            "DETECTION_NOTES": list(DETECTION_NOTES),
            "UI_BEARING": detect_ui_bearing(spec),
            "SPEC_EXISTS": bool(spec and spec.is_file()),
            "DESIGN_DOC_EXISTS": bool(feature and (feature / DESIGN_DOC_NAME).is_file()),
            "CONFIG": ds.config,
        }
    )


def cmd_principles(args: argparse.Namespace) -> None:
    result = resolve_principles(DesignSystem.resolve(), surface_kinds(args.applies_to))
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
    emit(
        build_context(
            DesignSystem.resolve(),
            args.phase,
            kinds=surface_kinds(args.applies_to),
            components=args.component,
            query=args.query,
        )
    )


def cmd_workflow(args: argparse.Namespace) -> None:
    emit(workflow_status(DesignSystem.resolve()))


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
    params = dict(zip(CAPABILITY_REGISTRY[args.capability].positional, args.args))
    result = DesignSystem.resolve().ask(args.capability, **params)

    wanted = [name.strip() for name in (args.fields or "").split(",") if name.strip()]
    if wanted and result.get("available") and result.get("data") is not None:
        result["bytes_unprojected"] = result.get("bytes", 0)
        result["projected_fields"] = wanted
        result["data"] = project_fields(result["data"], wanted)
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
            threshold = float((config.get("ledger") or {}).get("match_threshold", 0.34))
        current_version = args.current_version or config.get("design_system_version")
        emit(ledger_lookup(root, args.value, threshold, current_version))
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


def cmd_scan(args: argparse.Namespace) -> None:
    emit(scan_implementation(DesignSystem.resolve(), args.path))


def cmd_cache(args: argparse.Namespace) -> None:
    cache = DesignSystem.resolve().cache
    if args.action == "clear":
        emit({"cleared": True, "before": cache.clear()})
    else:
        emit(cache.stats())


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

    scan = sub.add_parser("scan", parents=[common])
    scan.add_argument(
        "--path", action="append",
        help="glob of implementation files, relative to the repo root (repeatable); "
             "defaults to validation.source_globs",
    )
    scan.set_defaults(func=cmd_scan)

    cache = sub.add_parser("cache", parents=[common])
    cache.add_argument("action", choices=["stats", "clear"], nargs="?", default="stats")
    cache.set_defaults(func=cmd_cache)

    args = parser.parse_args()
    global ACTIVE_COMMAND
    ACTIVE_COMMAND = args.command
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - commands degrade on JSON, never a traceback
        emit(failure_envelope(ACTIVE_COMMAND, f"internal error: {type(exc).__name__}: {exc}"))


if __name__ == "__main__":
    main()
