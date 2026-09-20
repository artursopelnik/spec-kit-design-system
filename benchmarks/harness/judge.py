#!/usr/bin/env python3
"""Blind pairwise judging: which of two runs produced the better result.

The scorer measures what can be counted. "Which one is better" cannot be
counted, so it is asked — under conditions that make the answer worth something:

  * Only implementation files are shown. Specs, plans and design documents are
    left out, because they would identify the arm in the first paragraph, and
    because the claim being tested is about the result, not the paperwork.
  * Which submission is A is randomised, and `--both-orders` judges each pair
    twice with the sides swapped, so a judge that favours the first thing it
    reads cancels out.
  * Mentions of the tooling are redacted from the code before it is shown.
  * The key lives outside the directory the judge runs in, and the verdict is
    recorded blinded. Nothing is unblinded until `tally`.

    python benchmarks/harness/judge.py pair \\
        --a benchmarks/results/<case>/speckit/<run> \\
        --b benchmarks/results/<case>/extension/<run> \\
        --judge 'claude -p "$(cat {prompt_file})"' --both-orders
    python benchmarks/harness/judge.py tally benchmarks/results/judgements

A judge from the same model family as the agent that produced a submission will
flatter it. Use a different one where you can, and say which you used either
way.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
BENCHMARKS = HARNESS.parent

sys.path.insert(0, str(HARNESS))
import score as scoring  # noqa: E402

CRITERIA = (
    "design_system_fit",
    "accessibility",
    "requirement_coverage",
    "maintainability",
    "overall",
)
SIDES = ("A", "B")

# Anything that would name the process rather than the result.
REDACTIONS = [
    (re.compile(r"(?i)\bspec[- ]?kit\b"), "[redacted]"),
    (re.compile(r"(?i)\bspeckit[.\w]*"), "[redacted]"),
    (re.compile(r"(?i)\.specify\b"), "[redacted]"),
    (re.compile(r"(?i)\bdesign-system\.md\b"), "[redacted]"),
    (re.compile(r"(?i)\bdesign system extension\b"), "[redacted]"),
    (re.compile(r"(?i)\bds\.sh\b"), "[redacted]"),
    (re.compile(r"(?i)\bDS-\d{3}\b"), "[redacted]"),
    (re.compile(r"(?i)\bDS-F-\d{3}\b"), "[redacted]"),
    (re.compile(r"(?i)\bgap record\b"), "[redacted]"),
    (re.compile(r"(?i)\breuse ladder\b"), "[redacted]"),
]

MAX_FILE_LINES = 400
MAX_BUNDLE_CHARS = 120_000


def redact(text: str) -> tuple[str, int]:
    count = 0
    for pattern, replacement in REDACTIONS:
        text, hits = pattern.subn(replacement, text)
        count += hits
    return text, count


def load_run(run_dir: Path) -> dict:
    manifest = json.loads((run_dir / "benchmark.json").read_text(encoding="utf-8"))
    return {
        "dir": run_dir,
        "manifest": manifest,
        "case": manifest["case"],
        "arm": manifest.get("arm", "unknown"),
        "workspace": run_dir / manifest.get("workspace", "workspace"),
        "provided": manifest.get("provided") or {},
    }


def implementation_files(run: dict) -> list[dict]:
    """What the run built, with the paperwork left out."""
    files = scoring.collect(run["workspace"], run["provided"])
    return [entry for entry in files if entry["kind"] == "code"]


def submission_markdown(files: list[dict]) -> tuple[str, int]:
    if not files:
        return "_This submission changed no implementation files._\n", 0

    redactions = 0
    parts = ["Files:\n"]
    for entry in files:
        parts.append(f"- `{entry['path']}`")
    parts.append("")

    for entry in files:
        text, hits = redact(entry["text"])
        redactions += hits
        lines = text.splitlines()
        if len(lines) > MAX_FILE_LINES:
            lines = lines[:MAX_FILE_LINES] + [f"... truncated, {len(lines) - MAX_FILE_LINES} more lines"]
        language = Path(entry["path"]).suffix.lstrip(".") or "text"
        parts.append(f"### `{entry['path']}`\n")
        parts.append(f"```{language}\n" + "\n".join(lines) + "\n```\n")
    return "\n".join(parts), redactions


def system_summary(system: dict) -> str:
    inventory = system["_inventory"]
    components = ", ".join(
        entry["name"] for entry in (inventory.get("components") or [])
    )
    patterns = ", ".join(entry["name"] for entry in (inventory.get("patterns") or []))
    breakpoints = ", ".join(
        f"{name} {value}" for name, value in (inventory.get("breakpoints") or {}).items()
    )
    return (
        f"**Design system**: {system['name']}. {system.get('stack', '')}\n\n"
        f"Components it offers: {components}.\n\n"
        f"Documented compositions: {patterns}.\n\n"
        f"Named breakpoints: {breakpoints}.\n"
    )


def build_pair(
    left: dict, right: dict, case: dict, system: dict, seed: str, swap: bool = False
) -> dict:
    """One blinded bundle. `swap` forces the order rather than drawing it."""
    # The seed draws the order, so a pair is reproducible; `swap` flips that draw
    # for the second showing of the same pair.
    first_is_left = random.Random(seed).random() < 0.5
    if swap:
        first_is_left = not first_is_left

    side_to_run = {
        "A": left if first_is_left else right,
        "B": right if first_is_left else left,
    }

    rfc = (Path(case["_dir"]) / case.get("rfc", "rfc.md")).read_text(encoding="utf-8")
    sections = [
        "## The request\n",
        rfc.strip(),
        "\n\n## The design system\n",
        system_summary(system),
    ]
    redactions = 0
    for side in SIDES:
        body, hits = submission_markdown(implementation_files(side_to_run[side]))
        redactions += hits
        sections.append(f"\n## Submission {side}\n")
        sections.append(body)

    bundle = "\n".join(sections)
    truncated = len(bundle) > MAX_BUNDLE_CHARS
    if truncated:
        bundle = bundle[:MAX_BUNDLE_CHARS] + "\n\n_... bundle truncated._\n"

    return {
        "bundle": bundle,
        "redactions": redactions,
        "truncated": truncated,
        "key": {side: side_to_run[side]["arm"] for side in SIDES},
        "runs": {side: str(side_to_run[side]["dir"]) for side in SIDES},
    }


def parse_verdict(output: str) -> dict | None:
    """The last JSON object in the judge's reply, whatever came before it."""
    for match in reversed(list(re.finditer(r"\{[^{}]*\}", output or "", re.DOTALL))):
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "overall" in payload:
            verdict = {}
            for criterion in CRITERIA:
                value = str(payload.get(criterion, "tie")).strip().upper()
                verdict[criterion] = value if value in ("A", "B") else "tie"
            verdict["why"] = str(payload.get("why", ""))[:2000]
            return verdict
    return None


def cmd_pair(args: argparse.Namespace) -> None:
    left, right = load_run(Path(args.a).resolve()), load_run(Path(args.b).resolve())
    if left["case"] != right["case"]:
        print(json.dumps({"error": f"different cases: {left['case']} vs {right['case']}"}))
        sys.exit(1)
    if left["arm"] == right["arm"]:
        print(json.dumps({"error": f"both runs are the {left['arm']} arm; nothing to compare"}))
        sys.exit(1)

    case = scoring.load_case(left["case"], Path(args.cases_dir))
    system = scoring.load_system(case["design_system"], Path(args.systems_dir))

    out = Path(args.out)
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    (out / "keys").mkdir(parents=True, exist_ok=True)

    template = (HARNESS / "prompts" / "judge.md").read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = hashlib.sha256(f"{left['dir']}|{right['dir']}".encode()).hexdigest()[:8]

    orders: list[bool] = [False, True] if args.both_orders else [False]
    written = []
    for index, swap in enumerate(orders):
        pair_id = f"{left['case']}-{base}-{stamp}-{index + 1}"
        pair_dir = out / "pairs" / pair_id
        pair_dir.mkdir(parents=True, exist_ok=True)

        built = build_pair(left, right, case, system, seed=base, swap=swap)
        (pair_dir / "bundle.md").write_text(built["bundle"], encoding="utf-8")
        prompt_file = pair_dir / "prompt.md"
        prompt_file.write_text(template + built["bundle"], encoding="utf-8")

        # The key never sits in the directory the judge works in.
        (out / "keys" / f"{pair_id}.json").write_text(
            json.dumps(
                {
                    "pair": pair_id,
                    "case": left["case"],
                    "design_system": case["design_system"],
                    "key": built["key"],
                    "runs": built["runs"],
                    "swapped": swap,
                    "redactions": built["redactions"],
                    "truncated": built["truncated"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        entry = {"pair": pair_id, "dir": str(pair_dir)}
        if args.judge:
            command = args.judge.format(
                prompt_file=str(prompt_file.resolve()), bundle=str((pair_dir / "bundle.md").resolve())
            )
            result = subprocess.run(
                command, cwd=pair_dir, shell=True, capture_output=True,
                text=True, timeout=args.timeout, check=False,
            )
            (pair_dir / "judge.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
            verdict = parse_verdict(result.stdout or "")
            if verdict is None:
                entry["error"] = "no verdict JSON in the judge's reply"
            else:
                verdict["judge"] = args.judge_name or "unnamed judge"
                (pair_dir / "verdict.json").write_text(
                    json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
                )
                entry["verdict"] = {c: verdict[c] for c in CRITERIA}
        written.append(entry)

    print(json.dumps({"case": left["case"], "pairs": written,
                      "next": f"python benchmarks/harness/judge.py tally {out}"}, indent=2))


def tally(directory: Path) -> dict:
    results: dict = {
        "pairs": 0, "unjudged": 0, "cases": {}, "criteria": {}, "judges": set(), "arms": set(),
    }
    for key_file in sorted((directory / "keys").glob("*.json")):
        key = json.loads(key_file.read_text(encoding="utf-8"))
        # Every arm that was shown, not only the ones that won something: an arm
        # with no wins is a result, and dropping its column would hide it.
        results["arms"].update(key["key"].values())
        verdict_file = directory / "pairs" / key["pair"] / "verdict.json"
        if not verdict_file.exists():
            results["unjudged"] += 1
            continue
        verdict = json.loads(verdict_file.read_text(encoding="utf-8"))
        results["pairs"] += 1
        results["judges"].add(verdict.get("judge", "unnamed judge"))
        case = key["case"]
        results["cases"].setdefault(case, 0)
        results["cases"][case] += 1
        for criterion in CRITERIA:
            side = verdict.get(criterion, "tie")
            bucket = results["criteria"].setdefault(criterion, {})
            if side == "tie":
                bucket["tie"] = bucket.get("tie", 0) + 1
                continue
            arm = key["key"][side]
            bucket[arm] = bucket.get(arm, 0) + 1
    results["judges"] = sorted(results["judges"])
    results["arms"] = sorted(results["arms"])
    return results


def cmd_tally(args: argparse.Namespace) -> None:
    directory = Path(args.directory)
    results = tally(directory)
    if not results["pairs"]:
        print(f"no judged pairs under {directory}")
        raise SystemExit(1)

    arms = results["arms"]
    lines = [
        "# Blind pairwise judging",
        "",
        f"{results['pairs']} judged pair(s) across {len(results['cases'])} case(s), "
        f"judged by: {', '.join(results['judges'])}.",
        "",
        "| Criterion | " + " | ".join(arms) + " | tie |",
        "|" + "---|" * (2 + len(arms)),
    ]
    for criterion in CRITERIA:
        bucket = results["criteria"].get(criterion, {})
        total = sum(bucket.values()) or 1
        cells = [f"{bucket.get(arm, 0)} ({bucket.get(arm, 0) / total:.0%})" for arm in arms]
        lines.append(
            f"| {criterion} | " + " | ".join(cells) + f" | {bucket.get('tie', 0)} |"
        )
    lines += [
        "",
        "Read with the obvious caveats: a judge from the same model family as the agent "
        "that wrote a submission will flatter it; each pair was shown in both orders only "
        "if it was created with `--both-orders`; and a preference is not a measurement of "
        "whether the thing works.",
    ]
    if results["unjudged"]:
        lines.append(f"\n{results['unjudged']} pair(s) have no verdict yet.")

    payload = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pair = sub.add_parser("pair", help="build a blinded pair, and judge it when --judge is given")
    pair.add_argument("--a", required=True, help="a run directory")
    pair.add_argument("--b", required=True, help="a run directory from a different arm")
    pair.add_argument("--judge", help="command to run; {prompt_file} and {bundle} are substituted")
    pair.add_argument("--judge-name", help="what to record as the judge, e.g. the model id")
    pair.add_argument("--both-orders", action="store_true",
                      help="judge the pair twice with the sides swapped")
    pair.add_argument("--timeout", type=int, default=900)
    pair.add_argument("--out", default=str(BENCHMARKS / "results" / "judgements"))
    pair.add_argument("--cases-dir", default=str(BENCHMARKS / "cases"))
    pair.add_argument("--systems-dir", default=str(BENCHMARKS / "systems"))
    pair.set_defaults(func=cmd_pair)

    tally_parser = sub.add_parser("tally", help="unblind the verdicts and count them")
    tally_parser.add_argument("directory", nargs="?",
                              default=str(BENCHMARKS / "results" / "judgements"))
    tally_parser.add_argument("--out")
    tally_parser.set_defaults(func=cmd_tally)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
