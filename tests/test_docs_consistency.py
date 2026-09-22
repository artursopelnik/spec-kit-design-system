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
