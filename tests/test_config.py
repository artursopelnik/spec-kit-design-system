"""Config resolution: extension defaults -> project -> local -> environment."""

from __future__ import annotations

from pathlib import Path


def test_defaults_come_from_the_extension_manifest(designsys, project):
    config = designsys.load_config(Path.cwd())
    assert config["adapter"] == "astryx"
    assert config["gate"]["enforce"] is True
    assert config["ledger"]["match_threshold"] == 0.34


def test_project_config_overrides_defaults(designsys, project, write_config):
    write_config({"adapter": "static-json", "gate": {"enforce": False}})
    config = designsys.load_config(Path.cwd())
    assert config["adapter"] == "static-json"
    assert config["gate"]["enforce"] is False
    # Untouched keys survive the merge rather than being replaced wholesale.
    assert config["gate"]["min_candidates_considered"] == 3


def test_local_override_beats_project_config(designsys, project, write_config):
    write_config({"gate": {"enforce": True}})
    write_config({"gate": {"enforce": False}}, local=True)
    assert designsys.load_config(Path.cwd())["gate"]["enforce"] is False


def test_environment_beats_local_override(designsys, project, write_config, monkeypatch):
    write_config({"gate": {"enforce": True}})
    write_config({"gate": {"enforce": False}}, local=True)
    monkeypatch.setenv("SPECKIT_DESIGNSYS_GATE_ENFORCE", "true")
    monkeypatch.setenv("SPECKIT_DESIGNSYS_ADAPTER", "static-json")
    monkeypatch.setenv("SPECKIT_DESIGNSYS_MATCH_THRESHOLD", "0.75")

    config = designsys.load_config(Path.cwd())
    assert config["gate"]["enforce"] is True
    assert config["adapter"] == "static-json"
    assert config["ledger"]["match_threshold"] == 0.75


def test_falsy_overrides_are_not_dropped(designsys, project, write_config):
    """`false` and `0` are real values, not absence — a naive merge loses them."""
    write_config({"gate": {"enforce": False, "min_candidates_considered": 0}})
    config = designsys.load_config(Path.cwd())
    assert config["gate"]["enforce"] is False
    assert config["gate"]["min_candidates_considered"] == 0


def test_adapter_source_and_registries_are_overridable(designsys, project, write_config):
    write_config({"adapter": "static-json", "source": "custom/ds.json"})
    config = designsys.load_config(Path.cwd())
    adapter = designsys.load_adapter(Path.cwd(), config)
    assert adapter["source"] == "custom/ds.json"


def test_unknown_adapter_is_a_hard_error(designsys, project, write_config):
    write_config({"adapter": "nope"})
    config = designsys.load_config(Path.cwd())
    try:
        designsys.load_adapter(Path.cwd(), config)
    except SystemExit as exit_:
        assert exit_.code == 1
    else:
        raise AssertionError("an unknown adapter must not resolve silently")
