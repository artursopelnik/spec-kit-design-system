"""Config resolution: extension defaults -> project -> local -> environment.

Plus the rule that keeps that layering honest: a key this extension does not
document is a key it does not read, and a default it ships is one something
actually reads. Both directions have been wrong here — a carry-forward shim for
a version that was never released, and a setting with a justifying comment and
no reader at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


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


def test_a_retired_key_is_not_read(design, project, write_config):
    """Nothing has been released, so nobody can hold a config written against an
    older vocabulary. The repository already decided this once, for `guidelines:`
    — "no alias, no carry-forward" — and then carried `rules:` and `audit:`
    forward anyway, from a "pre-0.2" that never existed at version 0.1.0.

    One policy: a key this extension does not document is a key it does not
    read. It is left in the config untouched rather than silently reinterpreted,
    because a setting that quietly means something else is worse than one that
    plainly does nothing.
    """
    write_config(
        {
            "adapter": "static-json",
            "rules": {"baseline": False, "house_rules": "old/rules.yml"},
            "audit": {"forbid_raw_values": False},
        }
    )
    config = design.load_config(Path.cwd())

    # Not reinterpreted into the current keys...
    assert config["principles"]["default"] is True
    assert "source" not in config["principles"]
    assert config["validation"]["forbid_raw_values"] is True
    # ...and not rewritten behind the author's back either.
    assert config["rules"] == {"baseline": False, "house_rules": "old/rules.yml"}
    assert "_migrated" not in config


def test_the_documented_keys_are_the_ones_that_work(design, project, write_config):
    write_config(
        {
            "adapter": "static-json",
            "principles": {"default": False, "source": "docs/principles.yml"},
            "validation": {"forbid_raw_values": False},
        }
    )
    config = design.load_config(Path.cwd())

    assert config["principles"]["default"] is False
    assert config["principles"]["source"] == "docs/principles.yml"
    assert config["validation"]["forbid_raw_values"] is False


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



# Settings the *script* never reads, because the layer that enforces them is the
# command body: the script hands them over in `CONFIG` and the agent acting on
# the prose honours them. That is a real architectural choice — judgement lives
# in `commands/`, mechanism in the script — and it is worth naming, because
# "the gate blocks" reads as a mechanical guarantee and for these four it is
# not. Each one must be named by a command body, or nothing enforces it at all.
ENFORCED_BY_THE_COMMANDS = {
    "gate.enforce": "check.md decides whether a failed gate errors or warns",
    "gate.min_candidates_considered": "check.md refuses Extend or Create on fewer rejected candidates",
    "ledger.enabled": "check.md skips lookup and recording when false",
    "validation.forbid_raw_values": "validate.md raises a finding for a raw value",
}


def config_defaults() -> list[str]:
    import yaml

    manifest = yaml.safe_load((REPO / "extension.yml").read_text(encoding="utf-8"))

    def leaves(node, prefix=""):
        for key, value in (node or {}).items():
            path = f"{prefix}{key}"
            if isinstance(value, dict):
                yield from leaves(value, f"{path}.")
            else:
                yield path

    return sorted(leaves(manifest["config"]["defaults"]))


def test_every_shipped_default_is_read_by_something():
    """A default with a comment explaining why it matters, and no reader
    anywhere, is a promise to whoever configures it that nothing keeps.
    `ledger.revalidate_when_stale` sat in the manifest with a three-line
    justification while staleness was reported unconditionally and the key was
    never loaded by anything."""
    source = (REPO / "scripts" / "python" / "design.py").read_text(encoding="utf-8")
    unread = [
        path
        for path in config_defaults()
        if path.rsplit(".", 1)[-1] not in source
        and path not in ENFORCED_BY_THE_COMMANDS
    ]
    assert unread == [], f"declared as a default, read by nothing: {unread}"


@pytest.mark.parametrize("setting", sorted(ENFORCED_BY_THE_COMMANDS))
def test_a_setting_the_script_ignores_is_named_by_a_command(setting):
    """These four are honoured only because a command body says so. If the body
    stops mentioning one, the setting silently stops doing anything while still
    appearing in the config as though it worked."""
    bodies = "\n".join(
        path.read_text(encoding="utf-8") for path in (REPO / "commands").glob("*.md")
    )
    leaf = setting.rsplit(".", 1)[-1]
    assert setting in bodies or leaf in bodies, (
        f"{setting} is enforced by nothing: the script does not read it and no "
        f"command body mentions it ({ENFORCED_BY_THE_COMMANDS[setting]})"
    )


@pytest.mark.parametrize("word", ["ture", "enabled", ""])
def test_an_unreadable_boolean_is_refused_not_read_as_false(design, word):
    """`SPECKIT_DESIGN_GATE_ENFORCE=ture` read as false switches the gate off
    without a word, which is the gate failing open on a typo."""
    if not word:
        assert design.coerce("off", bool) is False
        return
    with pytest.raises(SystemExit):
        design.coerce(word, bool)
