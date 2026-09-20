"""Fixtures building a minimal spec-kit project layout on disk.

The layout mirrors what `specify extension add` actually produces, verified
against Spec Kit 1.0.9.dev0:

    .specify/extensions/designsys/{extension.yml,designsys-config.yml,adapters/}
    .specify/memory/
    .specify/feature.json
    specs/<feature>/spec.md
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def designsys():
    spec = importlib.util.spec_from_file_location(
        "designsys", REPO / "scripts" / "python" / "designsys.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["designsys"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A spec-kit project with the extension installed, cwd set into it."""
    ext = tmp_path / ".specify" / "extensions" / "designsys"
    (ext / "adapters").mkdir(parents=True)
    (tmp_path / ".specify" / "memory").mkdir(parents=True)

    for name in ("extension.yml",):
        (ext / name).write_text((REPO / name).read_text(encoding="utf-8"), encoding="utf-8")
    for adapter in (REPO / "adapters").glob("*.yml"):
        (ext / "adapters" / adapter.name).write_text(
            adapter.read_text(encoding="utf-8"), encoding="utf-8"
        )

    monkeypatch.chdir(tmp_path)
    # Leak-proofing: a stray SPECKIT_DESIGNSYS_* in the developer's shell would
    # otherwise silently override config under test.
    for key in list(os.environ):
        if key.startswith(("SPECKIT_DESIGNSYS_", "SPECIFY_")):
            monkeypatch.delenv(key, raising=False)
    return tmp_path


@pytest.fixture
def baseline_installed(project):
    """baseline.yml as the installer places it, next to extension.yml."""
    target = project / ".specify" / "extensions" / "designsys" / "baseline.yml"
    target.write_text((REPO / "baseline.yml").read_text(encoding="utf-8"), encoding="utf-8")
    return target


@pytest.fixture
def write_config(project):
    def _write(data: dict, local: bool = False):
        name = "designsys-config.local.yml" if local else "designsys-config.yml"
        path = project / ".specify" / "extensions" / "designsys" / name
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def feature(project):
    """An active feature with a UI-bearing spec."""
    directory = project / "specs" / "001-booking-filters"
    directory.mkdir(parents=True)
    (directory / "spec.md").write_text(
        textwrap.dedent(
            """\
            # Feature Specification: Booking Filters

            User selects a date range on the booking screen. The form shows a
            dropdown and a button. Layout must be responsive on mobile and
            desktop, keyboard accessible, with visible focus.
            """
        ),
        encoding="utf-8",
    )
    (project / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-booking-filters"}), encoding="utf-8"
    )
    return directory


@pytest.fixture
def inventory(project):
    """A static JSON inventory, the CLI-free path."""
    path = project / ".design-system" / "inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "Calendar",
                        "description": "Month grid for date display",
                        "states": ["default", "disabled"],
                    },
                    {
                        "name": "Popover",
                        "description": "Floating container anchored to a trigger",
                    },
                ],
                "patterns": [
                    {"name": "FilterBar", "description": "Horizontal row of filter controls"}
                ],
                "tokens": {"space": {"3": "12px"}},
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fake_cli(project):
    """A CLI that can be told to fail in each way the dispatcher must survive."""
    path = project / "fakecli"
    path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            case "$1" in
              boom)    echo '{"error":"not found"}'; exit 3 ;;
              unknown) echo '{"code":"ERR_REGISTRY_DOWN"}' ;;
              missing) echo '{"code":"ERR_GONE"}' ;;
              prose)   echo 'not json at all' ;;
              *)       printf '{"type":"argv","data":' ;
                       python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]),end="")' "$@" ;
                       printf '}\\n' ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)

    adapter = project / ".specify" / "extensions" / "designsys" / "adapters" / "fake.yml"
    adapter.write_text(
        yaml.safe_dump(
            {
                "id": "fake",
                "name": "Fake",
                "bin": "./fakecli",
                "global_args": ["--json"],
                "envelope": {
                    "type_key": "type",
                    "data_key": "data",
                    "error_code_key": "code",
                },
                "registries": ["@one", "@two"],
                "capabilities": {
                    "search": {"args": ["ok", "{query}", "{registries}"], "result_path": "data"},
                    "component": {
                        "args": ["{name}"],
                        "result_path": "data",
                        "not_found_codes": ["ERR_GONE"],
                    },
                    "report_gap": {
                        "args": ["ok", "--title", "{title}", "--body", "{body}"],
                        "result_path": "data",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path
