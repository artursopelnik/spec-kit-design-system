"""What ships, and in what shape.

The extension is installed by copying this repository into a project, so the
form of these files travels with it. Two properties have to hold at rest, not
just on the machine that wrote them.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The files a run actually executes. Everything else is read.
ENTRY_POINTS = ["scripts/bash/ds.sh", "scripts/python/design.py", "examples/setup-demo.sh"]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def test_no_tracked_file_carries_crlf():
    """A `.sh` checked out with CRLF is not executable on Linux at all: the
    shebang resolves to `bash\\r`, and the loader reports a missing interpreter
    rather than a converted file, which sends the reader looking in the wrong
    place entirely.

    Git for Windows converts on checkout by default, so this is enforced by
    `.gitattributes` rather than by whoever cloned. The index is what travels,
    so the index is what is checked.
    """
    offenders = [
        line for line in git("ls-files", "--eol").splitlines()
        if line.startswith(("i/crlf", "i/mixed"))
    ]
    assert not offenders, "CRLF in the index:\n" + "\n".join(offenders)


def test_gitattributes_pins_the_line_endings():
    """The `.editorconfig` asks editors for LF; this is the half git enforces.
    Without it the rule holds only on machines that happen to be configured for
    it, which is the same as not holding."""
    attributes = git("check-attr", "text", "eol", "--", "scripts/bash/ds.sh")
    assert "eol: lf" in attributes


def test_the_entry_points_are_executable():
    for name in ENTRY_POINTS:
        mode = int(git("ls-files", "-s", "--", name).split()[0], 8)
        assert mode & stat.S_IXUSR, f"{name} is not executable in the index"


def test_the_shim_runs_and_emits_json(tmp_path):
    """The shim is the documented entry point, so it is worth actually running
    once. A file mode or a line ending that broke it would otherwise only show
    up in somebody else's project."""
    proc = subprocess.run(
        [str(REPO / "scripts" / "bash" / "ds.sh"), "rfc", "A button that opens a panel."],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.lstrip().startswith("{")
