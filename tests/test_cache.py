"""The answer cache, and the call count it keeps.

Every `ds.sh` call is its own process, so without this a run put the same
question to the design system's CLI once per phase, task and validation round.
What must not change is what an answer means: a failure to ask is never
remembered, the probe is always real, and nothing that acts is replayed.
"""

from __future__ import annotations

import json
import textwrap
import time

import yaml


def ask(design, capability, **params):
    # A fresh DesignSystem per call, as each `ds.sh` invocation is a new process.
    return design.DesignSystem.resolve().ask(capability, **params)


def stats(design):
    return design.DesignSystem.resolve().cache.stats()


def counting_cli(project, write_config, extra_capabilities=None):
    """A CLI that logs every invocation, so a test can see what really ran."""
    log = project / "calls.log"
    tool = project / "countcli"
    tool.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            echo "$*" >> {log}
            case "$1" in
              down) exit 7 ;;
              *)    echo '{{"data":{{"asked":"'"$*"'"}}}}' ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    tool.chmod(0o755)
    capabilities = {
        "search": {"args": ["search", "{query}"], "result_path": "data"},
        "component": {"args": ["component", "{name}"], "result_path": "data"},
        "report_gap": {"args": ["gap", "{title}"], "result_path": "data"},
        **(extra_capabilities or {}),
    }
    write_config({"adapter": "custom", "bin": str(tool), "capabilities": capabilities})

    def invocations():
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    return invocations


def test_a_repeated_question_reaches_the_cli_once(design, project, write_config):
    invocations = counting_cli(project, write_config)

    first = ask(design, "component", name="Popover")
    second = ask(design, "component", name="Popover")

    assert invocations() == ["component Popover"]
    assert first["cached"] is False and second["cached"] is True
    assert second["data"] == first["data"]
    assert stats(design)["by_capability"]["component"] == {"calls": 1, "hits": 1}


def test_a_different_question_is_not_answered_from_memory(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "component", name="Popover")
    ask(design, "component", name="Calendar")
    assert invocations() == ["component Popover", "component Calendar"]


def test_a_failure_to_ask_is_never_remembered(design, project, write_config):
    """An outage replayed from memory would outlive the outage."""
    invocations = counting_cli(
        project, write_config, {"describe": {"args": ["down"], "result_path": "data"}}
    )
    first = ask(design, "describe")
    second = ask(design, "describe")

    assert first["available"] is False and second["available"] is False
    assert second["cached"] is False
    assert invocations() == ["down", "down"]


def test_a_declared_miss_is_an_answer_and_is_remembered(design, project, write_config, fake_cli):
    write_config({"adapter": "fake"})
    ask(design, "component", name="missing")
    again = ask(design, "component", name="missing")
    assert again["cached"] is True
    assert again["available"] is True and again["found"] is False


def test_the_probe_is_always_a_real_call(design, project, write_config):
    """Reachability proven from memory proves only that it was there earlier."""
    invocations = counting_cli(project, write_config)
    for _ in range(3):
        assert design.DesignSystem.resolve().probe["reachable"] is True
    assert invocations() == ["search button"] * 3


def test_the_probe_still_fails_closed_after_a_good_answer(design, project, write_config):
    invocations = counting_cli(project, write_config)
    assert design.DesignSystem.resolve().probe["reachable"] is True

    write_config({"adapter": "custom", "bin": str(project / "gone"),
                  "capabilities": {"search": {"args": ["search", "{query}"]}}})
    probe = design.DesignSystem.resolve().probe
    assert probe["reachable"] is False
    assert invocations() == ["search button"]


def test_a_capability_that_acts_is_never_replayed(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "report_gap", title="Rating")
    second = ask(design, "report_gap", title="Rating")
    assert invocations() == ["gap Rating", "gap Rating"]
    assert second["cached"] is False
    assert stats(design)["by_capability"]["report_gap"] == {"calls": 2, "hits": 0}


def test_only_actions_are_uncacheable(design):
    uncacheable = {c.name for c in design.CAPABILITY_LIST if not c.cacheable}
    assert uncacheable == {"extend", "validate", "report_gap"}


def test_a_file_read_is_neither_cached_nor_counted(design, project, write_config, inventory):
    write_config({"adapter": "static-json"})
    ask(design, "component", name="Calendar")
    again = ask(design, "component", name="Calendar")
    assert again["cached"] is False
    assert stats(design)["calls"] == 0 and stats(design)["hits"] == 0


def test_changing_the_mapping_is_a_different_question(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "search", query="date")
    counting_cli(
        project, write_config,
        {"search": {"args": ["search", "{query}", "--all"], "result_path": "data"}},
    )
    ask(design, "search", query="date")
    assert invocations() == ["search date", "search date --all"]


def test_a_new_design_system_version_is_a_different_question(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "search", query="date")

    config = project / ".specify" / "extensions" / "design" / "design-config.yml"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["design_system_version"] = "2.0.0"
    config.write_text(yaml.safe_dump(data), encoding="utf-8")

    ask(design, "search", query="date")
    assert len(invocations()) == 2


def test_each_feature_starts_from_what_the_system_says_now(design, project, write_config, feature):
    invocations = counting_cli(project, write_config)
    ask(design, "search", query="date")

    other = project / "specs" / "002-ratings"
    other.mkdir(parents=True)
    (project / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/002-ratings"}), encoding="utf-8"
    )
    ask(design, "search", query="date")

    assert len(invocations()) == 2
    assert stats(design)["scope"] == "002-ratings"


def test_an_expired_answer_is_asked_again(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "search", query="date")

    cache = design.DesignSystem.resolve().cache
    for entry in cache.data["answers"].values():
        entry["at"] = time.time() - cache.ttl_seconds - 1
    cache.dirty = True
    cache.save()

    assert ask(design, "search", query="date")["cached"] is False
    assert len(invocations()) == 2


def test_switched_off_it_asks_every_time_and_still_counts(design, project, write_config, monkeypatch):
    invocations = counting_cli(project, write_config)
    monkeypatch.setenv("SPECKIT_DESIGN_CACHE_ENABLED", "false")
    ask(design, "search", query="date")
    ask(design, "search", query="date")

    assert len(invocations()) == 2
    summary = stats(design)
    assert summary["enabled"] is False
    assert summary["calls"] == 2 and summary["hits"] == 0 and summary["entries"] == 0


def test_a_corrupt_cache_is_a_cold_cache(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "search", query="date")
    path = design.DesignSystem.resolve().cache.path
    path.write_text("{not json", encoding="utf-8")

    assert ask(design, "search", query="date")["available"] is True
    assert len(invocations()) == 2


def test_the_cache_is_never_committed(design, project, write_config):
    counting_cli(project, write_config)
    ask(design, "search", query="date")
    path = design.DesignSystem.resolve().cache.path
    assert (path.parent / ".gitignore").read_text(encoding="utf-8").strip() == "*"


def test_clear_drops_answers_and_reports_what_was_there(design, project, write_config):
    invocations = counting_cli(project, write_config)
    ask(design, "search", query="date")
    ask(design, "search", query="date")

    before = design.DesignSystem.resolve().cache.clear()
    assert before["calls"] == 1 and before["hits"] == 1 and before["entries"] == 1

    ask(design, "search", query="date")
    assert len(invocations()) == 2
    assert stats(design)["calls"] == 1


def test_stats_and_clear_are_one_json_object_each(design, project, write_config, capsys, monkeypatch):
    counting_cli(project, write_config)
    ask(design, "search", query="date")

    for argv, key in ((["design", "cache", "stats", "--json"], "calls"),
                      (["design", "cache", "clear"], "cleared")):
        monkeypatch.setattr("sys.argv", argv)
        design.main()
        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 1 and key in json.loads(out[0])
