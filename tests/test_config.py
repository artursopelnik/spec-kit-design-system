"""Config resolution: extension defaults -> project -> local -> environment.

Plus the migration of pre-0.2 keys, which matters because the alternative is an
existing project silently losing its principles when it upgrades.
"""

from __future__ import annotations

from pathlib import Path


def test_defaults_come_from_the_extension_manifest(design, project):
    config = design.load_config(Path.cwd())
    assert config["adapter"] == "auto"
    assert config["gate"]["enforce"] is True
    assert config["ledger"]["match_threshold"] == 0.34
    assert config["workflow"]["max_validation_rounds"] == 3
    assert config["principles"]["default"] is True


def test_a_working_config_is_one_line(design, project, write_config):
    """The whole point of the resolution defaults: naming an adapter is enough,
    and everything else has an answer already."""
    write_config({"adapter": "static-json"})
    config = design.load_config(Path.cwd())

    assert config["gate"]["enforce"] is True
    assert config["workflow"]["max_validation_rounds"] == 3
    assert config["validation"]["required_dimensions"]


def test_project_config_overrides_defaults(design, project, write_config):
    write_config({"adapter": "static-json", "gate": {"enforce": False}})
    config = design.load_config(Path.cwd())
    assert config["adapter"] == "static-json"
    assert config["gate"]["enforce"] is False
    # Untouched keys survive the merge rather than being replaced wholesale.
    assert config["gate"]["min_candidates_considered"] == 3


def test_local_override_beats_project_config(design, project, write_config):
    write_config({"gate": {"enforce": True}})
    write_config({"gate": {"enforce": False}}, local=True)
    assert design.load_config(Path.cwd())["gate"]["enforce"] is False


def test_pre_02_rule_keys_still_work(design, project, write_config):
    """`baseline` is gone as a concept, not as a setting someone already wrote."""
    write_config(
        {
            "rules": {
                "baseline": False,
                "house_rules": "node_modules/@acme/design-system/rules.yml",
                "disabled": ["BL-MOTION-REDUCED"],
            }
        }
    )
    config = design.load_config(Path.cwd())

    assert "rules" not in config
    assert config["principles"]["default"] is False
    assert config["principles"]["source"].endswith("rules.yml")
    assert config["principles"]["disabled"] == ["BL-MOTION-REDUCED"]
    assert any("rules.baseline" in note for note in config["_migrated"])


def test_pre_02_audit_keys_still_work(design, project, write_config):
    write_config({"audit": {"forbid_raw_values": False, "source_globs": ["src/ui/**"]}})
    config = design.load_config(Path.cwd())

    assert "audit" not in config
    assert config["validation"]["forbid_raw_values"] is False
    assert config["validation"]["source_globs"] == ["src/ui/**"]


def test_environment_beats_local_override(design, project, write_config, monkeypatch):
    write_config({"gate": {"enforce": True}})
    write_config({"gate": {"enforce": False}}, local=True)
    monkeypatch.setenv("SPECKIT_DESIGN_GATE_ENFORCE", "true")
    monkeypatch.setenv("SPECKIT_DESIGN_ADAPTER", "static-json")
    monkeypatch.setenv("SPECKIT_DESIGN_MATCH_THRESHOLD", "0.75")
    monkeypatch.setenv("SPECKIT_DESIGN_MAX_VALIDATION_ROUNDS", "5")

    config = design.load_config(Path.cwd())
    assert config["gate"]["enforce"] is True
    assert config["adapter"] == "static-json"
    assert config["ledger"]["match_threshold"] == 0.75
    assert config["workflow"]["max_validation_rounds"] == 5


def test_falsy_overrides_are_not_dropped(design, project, write_config):
    """`false` and `0` are real values, not absence. A naive merge loses them."""
    write_config({"gate": {"enforce": False, "min_candidates_considered": 0}})
    config = design.load_config(Path.cwd())
    assert config["gate"]["enforce"] is False
    assert config["gate"]["min_candidates_considered"] == 0


def test_adapter_source_and_registries_are_overridable(design, project, write_config):
    write_config({"adapter": "static-json", "source": "custom/ds.json"})
    config = design.load_config(Path.cwd())
    adapter = design.load_adapter(Path.cwd(), config)
    assert adapter["source"] == "custom/ds.json"


def test_unknown_adapter_is_a_hard_error(design, project, write_config):
    write_config({"adapter": "nope"})
    config = design.load_config(Path.cwd())
    try:
        design.load_adapter(Path.cwd(), config)
    except SystemExit as exit_:
        assert exit_.code == 1
    else:
        raise AssertionError("an unknown adapter must not resolve silently")


def test_auto_adapter_detects_from_the_project(design, project):
    root = Path.cwd()
    config = design.load_config(root)
    assert design.load_adapter(root, config)["id"] == "static-json"

    (root / "components.json").write_text("{}", encoding="utf-8")
    assert design.load_adapter(root, config)["id"] == "shadcn"

    pinned = dict(config, adapter="static-json")
    assert design.load_adapter(root, pinned)["id"] == "static-json"


def test_auto_adapter_detects_component_libraries(design, project):
    root = Path.cwd()
    config = design.load_config(root)
    for dependency, expected in (
        ("@mui/material", "mui"),
        ("antd", "antd"),
        ("@chakra-ui/react", "chakra"),
        ("@ark-ui/react", "ark-ui"),
        ("@radix-ui/react-dialog", "radix"),
        ("radix-ui", "radix"),
    ):
        (root / "package.json").write_text(
            '{"dependencies": {"%s": "1.0.0"}}' % dependency, encoding="utf-8"
        )
        assert design.load_adapter(root, config)["id"] == expected, dependency


def test_the_guidelines_block_is_carried_to_principles(design, project, write_config):
    """The rename is breaking on purpose, but a config someone already wrote is
    not where that break should land. Mapped, and reported so it gets cleaned
    up — a config silently reinterpreted is worse than one that fails."""
    write_config(
        {
            "guidelines": {
                "source": "node_modules/@acme/design-system/guidelines.yml",
                "default": False,
            }
        }
    )
    config = design.load_config(Path.cwd())

    assert "guidelines" not in config
    assert config["principles"]["default"] is False
    assert config["principles"]["source"].endswith("guidelines.yml")
    assert any("guidelines.* -> principles.*" in note for note in config["_migrated"])


def test_a_principle_switched_off_by_its_old_id_stays_off(design, project, write_config):
    """Somebody decided to disable that principle. Renaming the ids underneath
    them would turn it back on silently, which is the one outcome a rename must
    not produce."""
    write_config({"guidelines": {"disabled": ["GL-REDUCED-MOTION", "ACME-OWN-ID"]}})
    config = design.load_config(Path.cwd())

    assert config["principles"]["disabled"] == ["PRIN-REDUCED-MOTION", "ACME-OWN-ID"]
    assert any("GL-* ids renamed" in note for note in config["_migrated"])


def test_a_project_that_already_uses_principles_is_left_alone(design, project, write_config):
    write_config({"principles": {"disabled": ["PRIN-CONTRAST"]}})
    config = design.load_config(Path.cwd())

    assert config["principles"]["disabled"] == ["PRIN-CONTRAST"]
    assert "_migrated" not in config
