"""What ships, and in what shape.

The extension is installed by copying this repository into a project, so the
form of these files travels with it. Two properties have to hold at rest, not
just on the machine that wrote them.
"""

from __future__ import annotations

import fnmatch
import re
import stat
import subprocess
from pathlib import Path

import yaml

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


# --- the catalog entry ---------------------------------------------------------
#
# The community catalog copies these fields from the manifest, and a submission
# is reviewed against the publishing guide's checklist. Holding them here means
# an edit that would get the entry bounced fails in this repository first.

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# What a run reads or executes once installed. `.extensionignore` must leave
# every one of these in place.
RUNTIME = [
    "extension.yml", "config-template.yml", "LICENSE", "README.md", "CHANGELOG.md",
    "commands", "scripts", "adapters", "principles", "preset", "templates", "docs",
]


def manifest() -> dict:
    return yaml.safe_load((REPO / "extension.yml").read_text(encoding="utf-8"))


def test_the_manifest_meets_the_catalog_checklist():
    ext = manifest()["extension"]
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", ext["id"])
    assert SEMVER.match(ext["version"])
    assert len(ext["description"]) < 100, "the publishing guide asks for under 100"
    assert ext["repository"].startswith("https://github.com/")
    tags = manifest()["tags"]
    assert 2 <= len(tags) <= 5
    assert all(tag == tag.lower() and " " not in tag for tag in tags)


def test_every_command_and_template_file_exists():
    data = manifest()
    files = [c["file"] for c in data["provides"]["commands"]]
    files += [c["template"] for c in data["provides"].get("config", [])]
    missing = [f for f in files if not (REPO / f).is_file()]
    assert not missing, missing


def test_one_version_everywhere():
    """The release workflow refuses a tag that disagrees with either manifest or
    has no dated changelog section; this is the same check, earlier."""
    version = manifest()["extension"]["version"]
    preset = yaml.safe_load((REPO / "preset" / "preset.yml").read_text(encoding="utf-8"))
    assert preset["preset"]["version"] == version
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M)
    assert f"version-{version}-" in (REPO / "README.md").read_text(encoding="utf-8")


def test_the_extensionignore_keeps_what_runs():
    """Spec Kit applies these patterns when it copies the extension into a
    project. CI checks the result against the real matcher; this catches the
    obvious mistake without installing anything."""
    patterns = [
        line.strip().rstrip("/")
        for line in (REPO / ".extensionignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "!"))
    ]
    dropped = [
        path for path in RUNTIME
        if any(fnmatch.fnmatch(path, pattern.lstrip("/")) for pattern in patterns)
    ]
    assert not dropped, f".extensionignore would drop {dropped}"
    for dev_only in ("tests", "benchmarks"):
        assert dev_only in patterns
