"""The prose and the mechanism have to agree.

Three layers, and only one of them is executed. `commands/*.md` is the layer a
model acts on, so a JSON example there is as load-bearing as a function
signature — and nothing runs it. Every blocker found in review lived in exactly
this seam: code that did something slightly other than the text beside it
claimed, in a place no test looked.

These tests read the shipped prose and check it against the script.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMANDS = sorted((REPO / "commands").glob("*.md"))
PROSE = COMMANDS + sorted((REPO / "preset" / "templates").glob("*.md")) + [REPO / "README.md"]


def body(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ledger_payloads(text: str) -> list[dict]:
    """Every `ledger record` JSON heredoc in a command body."""
    payloads = []
    for block in re.findall(r"ledger record .*?<<'JSON'\n(.*?)\nJSON", text, re.S):
        payloads.append(json.loads(block))
    for inline in re.findall(r"ledger record '(\{.*?\})'", text, re.S):
        payloads.append(json.loads(inline))
    return payloads


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_every_ledger_example_records_a_real_rung(design, path):
    """`compose` and `compose-components` were both being taught, by two command
    bodies, for one rung. The ledger stored whichever arrived, so following the
    extension's own documentation produced two contradicting active decisions."""
    for payload in ledger_payloads(body(path)):
        assert design.canonical_resolution(payload["resolution"]) is not None, (
            f"{path.name}: {payload['resolution']!r} is not a rung "
            f"({', '.join(design.RESOLUTIONS)})"
        )


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_every_ledger_example_is_actually_recordable(design, path, project):
    """The examples are copied verbatim by whoever follows them, so they have to
    survive the validation they will meet."""
    for payload in ledger_payloads(body(path)):
        design.ledger_record(Path.cwd(), dict(payload))


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_no_command_teaches_a_retired_field_name(path):
    """One name for the feature that took a decision. `feature` is folded into
    `decided_in` on the way in, but a body that still teaches it is teaching a
    reader to write something the file will not contain."""
    for payload in ledger_payloads(body(path)):
        assert "feature" not in payload, f"{path.name}: use `decided_in`, not `feature`"


def test_only_one_command_writes_to_the_ledger():
    """The gate walks the ladder and records what it decided, at the point where
    the candidates and the reasoning are still in hand. A second writer means one
    surface, two entries, and the drift the ladder exists to prevent."""
    writers = [p.name for p in COMMANDS if ledger_payloads(body(p))]
    assert writers == ["speckit.design.check.md"], writers


# --- the gate's keys ----------------------------------------------------------


def gate_keys() -> set[str]:
    """Every key `cmd_gate` emits, read off the source."""
    source = (REPO / "scripts" / "python" / "design.py").read_text(encoding="utf-8")
    return set(re.findall(r'"([A-Z][A-Z_0-9]+)":', source[source.index("def cmd_gate"):]))


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_a_command_declares_every_gate_key_it_goes_on_to_use(path):
    """A body says "Parse the JSON for ..." and then reads whatever it needs.
    Three of the four reached for keys that list never mentioned, so an agent
    that parsed exactly what it was told to parse had nothing to answer with
    when the body later asked for `REQUIRED_DIMENSIONS`."""
    text = body(path)
    declared = set()
    for line in re.findall(r"^Parse .*", text, re.MULTILINE):
        declared |= set(re.findall(r"`([A-Z][A-Z_0-9]+)`", line))
    used = set(re.findall(r"`([A-Z][A-Z_0-9]+)`", text)) & gate_keys()
    assert not (used - declared), f"{path.name}: used but never declared -> {sorted(used - declared)}"


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_a_command_does_not_ask_for_a_key_the_gate_never_emits(path):
    """The other direction: a body telling an agent to parse `PRINCIPLES_KIND`
    sends it looking for something that was renamed or never existed."""
    text = body(path)
    declared = set()
    for line in re.findall(r"^Parse .*", text, re.MULTILINE):
        declared |= set(re.findall(r"`([A-Z][A-Z_0-9]+)`", line))
    unknown = declared - gate_keys() - {"JSON"}
    assert not unknown, f"{path.name}: no such gate key -> {sorted(unknown)}"


# --- one vocabulary -----------------------------------------------------------


# The anchor is the head of the list, not the whole of it: a drifting list
# drops or rewords its tail, so anchoring on the tail matches nothing and the
# guard passes by finding no list at all.
STATES_HEAD = "default, hover, focus, active"
STATES_TAIL = ["disabled", "loading", "error", "empty"]


@pytest.mark.parametrize("path", PROSE, ids=lambda p: p.name)
def test_the_state_list_does_not_drift(path):
    """Four places name the states every instance must handle, and one of them
    used to stop at `error` while the others went on to `empty`. A checker and a
    spec disagreeing by one state is a state nobody implements.

    Matched on whitespace-collapsed text, because the list is wrapped across
    lines in most of these files — which is exactly why the drift survived.
    """
    text = re.sub(r"\s+", " ", body(path))
    for match in re.finditer(re.escape(STATES_HEAD) + r"(.{0,80})", text):
        tail = match.group(1)
        missing = [state for state in STATES_TAIL if state not in tail]
        assert not missing, (
            f"{path.name}: the state list is missing {missing} -> ...{tail!r}"
        )


def test_the_ladder_is_spelled_the_same_way_everywhere():
    """Recall is rung 0 and the reason the ledger exists. It was missing from
    the manifests and from the constitution addendum — the artifact that lands
    in the customer's own repository as a non-negotiable principle."""
    offenders = []
    for path in [REPO / "extension.yml", REPO / "preset" / "preset.yml", *PROSE]:
        for match in re.finditer(r"(\w+)([ ]*(?:->|→)[ ]*Compose[ ]*(?:->|→)[ ]*Extend)", body(path)):
            if match.group(1) != "Reuse":
                continue
            # The ledger stores outcomes, and Recall is not one of them: it is
            # the rung that *reads* the ledger. "a ledger of Reuse -> ... ->
            # Create decisions" is correct and stays.
            tail = body(path)[match.end():match.end() + 30]
            if re.match(r"\s*(?:->|→)\s*Create decisions\b", tail):
                continue
            start = max(0, match.start() - 12)
            if "Recall" not in body(path)[start:match.start()]:
                offenders.append(f"{path.name}: {match.group(0)}")
    assert not offenders, offenders


# --- one gap-record format ----------------------------------------------------


GAP_HEADINGS = ["## What is needed", "## What was searched", "## What we are building instead"]


def test_the_readme_and_the_command_teach_one_gap_record():
    """The README taught `# Gap record: <Component>` with its own four headings;
    the command and the benchmark sample use `# Gap: <capability>` with four
    different ones. Two formats for the artifact that has to travel to the
    design system's owners."""
    readme = body(REPO / "README.md")
    check = body(REPO / "commands" / "speckit.design.check.md")
    for heading in GAP_HEADINGS:
        assert heading in check, f"the command stopped teaching {heading!r}"
        assert heading in readme, f"the README does not match the command: {heading!r}"
    assert "# Gap record:" not in readme, "the retired gap-record heading is back"


def test_the_gap_record_is_named_by_capability_not_by_component():
    """The README's own example titled the record `# Gap record: DateRangePicker`,
    two paragraphs under the rule that naming the component pre-decides the
    ladder."""
    for path in (REPO / "README.md", REPO / "commands" / "speckit.design.check.md"):
        for title in re.findall(r"^# Gap:? ?(.*)$", body(path), re.MULTILINE):
            assert not re.fullmatch(r"[A-Z][a-zA-Z]+", title.strip()), (
                f"{path.name}: gap titled with a component name -> {title!r}"
            )


# --- strict about what goes in, light on how it is used -----------------------


def test_reuse_has_a_short_path_that_ends_the_walk():
    """Every surface used to pay for the full walk: two searches per rung, a
    candidate table, a quota of rejected candidates, even a Button used exactly
    as documented. The short form is what makes Reuse cheap, and a body that
    drops it puts every surface back on the long path."""
    check = body(REPO / "commands" / "speckit.design.check.md")
    assert "#### The short path: Recall, then Reuse" in check
    assert "#### The full walk: Compose, Extend, Create" in check
    assert "the surface is resolved as Reuse and the walk ends" in check

    short = check[check.index("A surface resolved on the short path gets the short form"):]
    short = short[: short.index("A surface that took the full walk")]
    assert "**Resolution**: Reuse" in short
    assert "**Searched**" not in short, "the short form grew the candidate table back"
    assert "**Principles that apply**" in short, "validation reads this line on every surface"


def test_the_candidate_quota_applies_only_where_new_code_enters():
    """`min_candidates_considered` guards against building on a thin search. A
    quota on Reuse only pads tables; on Extend and Create it is the whole point."""
    check = body(REPO / "commands" / "speckit.design.check.md")
    gate = check[re.search(r"^### \d+\. Gate$", check, re.M).start():check.index("## Completion Report")]
    assert "an Extend or Create resolution rests on fewer rejected candidates" in gate
    assert "a rung was rejected on fewer candidates" not in check


@pytest.mark.parametrize(
    "path", [REPO / "commands" / "speckit.design.check.md", REPO / "README.md"], ids=lambda p: p.name
)
def test_what_create_builds_is_a_lab_component(path):
    """Create builds in the project, not in the design system, and says so where
    it is defined. Graduation is the system owners' call, never this run's."""
    text = body(path)
    assert "lab component" in text
    assert "not part of the design system" in text or "not in the design system" in text


def test_the_design_system_is_consulted_once_before_planning():
    """A context hook after specify searched every surface, and the gate searched
    it again. The gate is now the one pass, and it owns the spec section too."""
    import yaml

    manifest = yaml.safe_load((REPO / "extension.yml").read_text(encoding="utf-8"))
    assert "after_specify" not in manifest["hooks"]
    assert manifest["hooks"]["before_plan"]["command"] == "speckit.design.check"
    assert manifest["hooks"]["before_plan"]["optional"] is False
    for command in manifest["provides"]["commands"]:
        assert (REPO / command["file"]).is_file(), command

    check = body(REPO / "commands" / "speckit.design.check.md")
    assert "## Design System Requirements" in check
    assert "principles_source" in check and "query tokens" in check
    for path in PROSE:
        assert "speckit.design.context" not in body(path), f"{path.name} still names the removed command"
