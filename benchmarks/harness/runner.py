#!/usr/bin/env python3
"""Set up one benchmark arm, optionally run an agent in it, and score the result.

An arm is a workspace plus a prompt. All three arms get the same RFC, the same
design system, in the same place, described the same way in AGENTS.md. The only
thing that varies is how much machinery sits between the agent and the design
system:

    unaided      the agent and the RFC
    speckit      plus Spec Kit
    extension    plus Spec Kit and this extension

Anything else that differs between the arms is a bug in this file, because it
would end up attributed to the extension.

    python benchmarks/harness/runner.py --case date-range-filter --arm extension --no-agent
    python benchmarks/harness/runner.py --case date-range-filter --arm speckit \
        --agent 'claude --permission-mode acceptEdits -p "$(cat {prompt_file})"' --score

One JSON object on stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
BENCHMARKS = HARNESS.parent
REPO = BENCHMARKS.parent

sys.path.insert(0, str(HARNESS))
import score as scoring  # noqa: E402

ARMS = ("unaided", "speckit", "extension")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_tree(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copytree(source, target, dirs_exist_ok=True)


def run(command: list[str] | str, cwd: Path, shell: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=cwd, shell=shell, capture_output=True, text=True, check=False
    )


# --- what the run cost --------------------------------------------------------
#
# The scored metrics say what came out. This says what it took to get there,
# which is the other half of the question: an arm that scores higher and costs
# four times as much is a trade, not a win, and hiding the price is how a
# benchmark becomes an advertisement.
#
# Nothing here is scored. It is recorded, and the report prints it beside the
# scores.


def _sum_usage(usage: dict) -> dict:
    fields = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    counted = {field: int(usage.get(field) or 0) for field in fields}
    # Every token the model read or wrote, cache included. The breakdown stays
    # so anyone who bills cache reads differently can recompute.
    counted["total_tokens"] = sum(counted.values())
    return counted


def extract_usage(stdout: str, workspace: Path) -> dict | None:
    """Read the agent's own accounting, whatever shape it came in.

    Claude Code's `--output-format json` (and the last result line of
    `stream-json`) is understood directly. Any other agent can write a
    `usage.json` into the workspace and be counted the same way.
    """
    candidates: list[tuple[str, dict]] = []

    stripped = (stdout or "").strip()
    if stripped:
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                candidates.append(("agent-json", payload))
        except json.JSONDecodeError:
            for line in reversed(stripped.splitlines()):
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and (
                    payload.get("type") == "result" or "usage" in payload
                ):
                    candidates.append(("agent-stream-json", payload))
                    break

    usage_file = workspace / "usage.json"
    if usage_file.exists():
        try:
            payload = json.loads(usage_file.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                candidates.append(("usage.json", payload))
        except json.JSONDecodeError:
            pass

    for source, payload in candidates:
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
        counted = _sum_usage(usage)
        if not counted["total_tokens"]:
            continue
        record = {"source": source, **counted}
        for key, field in (
            ("cost_usd", "total_cost_usd"),
            ("cost_usd", "cost_usd"),
            ("turns", "num_turns"),
            ("turns", "turns"),
        ):
            value = payload.get(field)
            if value is not None and key not in record:
                record[key] = value
        duration_ms = payload.get("duration_ms")
        if duration_ms is not None:
            record["agent_duration_s"] = round(float(duration_ms) / 1000, 1)
        return record
    return None


def specify_available(binary: str) -> bool:
    return shutil.which(binary) is not None


def build_workspace(workspace: Path, case: dict, system: dict, arm: str, specify_bin: str) -> dict:
    """Everything that is identical across arms happens first, and on purpose."""
    workspace.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    if arm in ("speckit", "extension"):
        result = run(
            [specify_bin, "init", ".", "--here", "--integration", "claude",
             "--non-interactive", "--ignore-agent-tools", "--force"],
            cwd=workspace,
        )
        if result.returncode != 0:
            raise RuntimeError(f"specify init failed:\n{result.stdout}\n{result.stderr}")
        notes.append("spec kit initialised")

    if arm == "extension":
        for command in (
            [specify_bin, "extension", "add", "--dev", str(REPO)],
            [specify_bin, "preset", "add", "--dev", str(REPO / "preset")],
        ):
            result = run(command, cwd=workspace)
            if result.returncode != 0:
                raise RuntimeError(f"{' '.join(command)} failed:\n{result.stdout}\n{result.stderr}")
        config = workspace / ".specify" / "extensions" / "design" / "design-config.yml"
        install = system.get("install") or {}
        lines = [
            f"adapter: {system.get('adapter', 'static-json')}",
            f"source: \"{install.get('inventory_path', '.design-system/inventory.json')}\"",
        ]
        if system.get("guidelines"):
            lines.append("guidelines:")
            lines.append(f"  source: \"{install['guidelines_path']}\"")
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")
        notes.append("extension and preset installed")

    # The design system, in the same place for every arm.
    install = system.get("install") or {}
    inventory_target = workspace / install.get("inventory_path", ".design-system/inventory.json")
    inventory_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(system["_dir"]) / system["inventory"], inventory_target)
    guidelines_target = None
    if system.get("guidelines"):
        guidelines_target = workspace / install["guidelines_path"]
        guidelines_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(system["_dir"]) / system["guidelines"], guidelines_target)

    # The starting point the RFC talks about.
    copy_tree(Path(case["_dir"]) / "seed", workspace)
    shutil.copy(Path(case["_dir"]) / case.get("rfc", "rfc.md"), workspace / "rfc.md")

    guidelines_line = (
        f"- `{install['guidelines_path']}` — the rules the work is held to."
        if guidelines_target
        else "- The system publishes no rule file; its principles are the `guidelines`\n"
        "  field of the inventory and the `usage` and `avoid` notes on each entry."
    )
    brief = (HARNESS / "prompts" / "agents-brief.md").read_text(encoding="utf-8")
    (workspace / "AGENTS.md").write_text(
        brief.format(
            system_name=system["name"],
            stack=system.get("stack", ""),
            inventory_path=install.get("inventory_path", ".design-system/inventory.json"),
            guidelines_line=guidelines_line,
        ),
        encoding="utf-8",
    )
    for mirror in ("CLAUDE.md",):
        (workspace / mirror).write_text(
            f"See AGENTS.md.\n", encoding="utf-8"
        )

    return {"notes": notes}


def manifest_provided(workspace: Path, case: dict) -> dict[str, str]:
    """Hash everything the harness put there, minus the files the RFC is about.

    A provided file that the run edits is scored, because changing it was the
    run's decision. The subject files are scored either way.
    """
    always = set(case.get("always_score") or [])
    provided: dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel in always:
            continue
        provided[rel] = digest(path)
    return provided


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--arm", required=True, choices=ARMS)
    parser.add_argument(
        "--agent",
        help="command to run in the workspace; {prompt_file} and {workspace} are substituted. "
             "Omit it (or pass --no-agent) to set the workspace up and stop. Token and cost "
             "accounting is picked up from the agent's own JSON output, or from a usage.json "
             "it leaves in the workspace.",
    )
    parser.add_argument("--no-agent", action="store_true")
    parser.add_argument("--repeat", type=int, default=1, help="runs of the same arm")
    parser.add_argument("--timeout", type=int, default=3600, help="seconds per run")
    parser.add_argument("--out", default=str(BENCHMARKS / "results"))
    parser.add_argument("--label", default="", help="groups runs of one sitting together")
    parser.add_argument("--specify-bin", default="specify")
    parser.add_argument("--cases-dir", default=str(BENCHMARKS / "cases"))
    parser.add_argument("--systems-dir", default=str(BENCHMARKS / "systems"))
    parser.add_argument("--score", action="store_true", help="score each run when it finishes")
    args = parser.parse_args()

    case = scoring.load_case(args.case, Path(args.cases_dir))
    system = scoring.load_system(case["design_system"], Path(args.systems_dir))

    if args.arm in ("speckit", "extension") and not specify_available(args.specify_bin):
        print(json.dumps({
            "error": f"{args.arm} needs Spec Kit: pip install specify-cli "
                     f"(or point --specify-bin at it)",
        }))
        sys.exit(1)

    label = args.label or now()
    runs = []
    for index in range(1, args.repeat + 1):
        run_dir = Path(args.out) / args.case / args.arm / f"{label}-{index:02d}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        workspace = run_dir / "workspace"

        try:
            setup = build_workspace(workspace, case, system, args.arm, args.specify_bin)
        except RuntimeError as error:
            print(json.dumps({"error": str(error)}))
            sys.exit(1)

        prompt = (HARNESS / "prompts" / f"{args.arm}.md").read_text(encoding="utf-8")
        prompt_file = run_dir / "prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")

        record = {
            "case": args.case,
            "arm": args.arm,
            "design_system": case["design_system"],
            "workspace": "workspace",
            "label": label,
            "index": index,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "setup": setup["notes"],
            "agent": args.agent or None,
            "provided": manifest_provided(workspace, case),
        }

        if args.agent and not args.no_agent:
            command = args.agent.format(
                prompt_file=str(prompt_file.resolve()), workspace=str(workspace.resolve())
            )
            started = time.monotonic()
            try:
                result = subprocess.run(
                    command, cwd=workspace, shell=True, capture_output=True,
                    text=True, timeout=args.timeout, check=False,
                )
                record["exit_code"] = result.returncode
                record["timed_out"] = False
                (run_dir / "agent.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
                (run_dir / "agent.stderr.txt").write_text(result.stderr or "", encoding="utf-8")
            except subprocess.TimeoutExpired:
                record["exit_code"] = None
                record["timed_out"] = True
            record["duration_s"] = round(time.monotonic() - started, 1)
            usage = extract_usage(
                (run_dir / "agent.stdout.txt").read_text(encoding="utf-8")
                if (run_dir / "agent.stdout.txt").exists()
                else "",
                workspace,
            )
            if usage:
                record["usage"] = usage
        else:
            record["agent_skipped"] = True

        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        (run_dir / "benchmark.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )

        entry = {"run": str(run_dir), "arm": args.arm, "index": index}
        if args.score:
            result = scoring.score_run(
                workspace, case, system, record["provided"],
                {k: v for k, v in record.items() if k != "provided"},
            )
            (run_dir / "score.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            entry["score"] = result["score"]
        runs.append(entry)

    print(json.dumps({
        "case": args.case,
        "arm": args.arm,
        "design_system": case["design_system"],
        "label": label,
        "runs": runs,
        "next": "score with benchmarks/harness/score.py --run <run>, "
                "aggregate with benchmarks/harness/report.py",
    }, indent=2))


if __name__ == "__main__":
    main()
