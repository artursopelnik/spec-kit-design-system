#!/usr/bin/env python3
"""Aggregate scored runs into a table you can put in front of someone.

Reports the median, not the mean: agent runs are noisy and one catastrophic run
should not decide the number. The spread is printed next to it, because a median
without a spread is how benchmarks start lying.

    python benchmarks/harness/report.py benchmarks/results
    python benchmarks/harness/report.py benchmarks/results --format json
    python benchmarks/harness/report.py benchmarks/results --out benchmarks/results/REPORT.md
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

METRIC_ORDER = [
    "inventory_fidelity",
    "ladder_outcome",
    "token_discipline",
    "guideline_coverage",
    "criteria_traceability",
]
METRIC_LABEL = {
    "inventory_fidelity": "Fidelity",
    "ladder_outcome": "Ladder",
    "token_discipline": "Tokens",
    "guideline_coverage": "Guidelines",
    "criteria_traceability": "Criteria",
}
ARM_ORDER = ["unaided", "speckit", "extension"]

# Below this many runs per arm, a difference is an anecdote.
CONFIDENT_N = 5


def load(results: Path) -> list[dict]:
    runs = []
    for path in sorted(results.rglob("score.json")):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return runs


def summarize(runs: list[dict]) -> dict:
    scores = [run["score"] for run in runs]
    summary = {
        "n": len(runs),
        "score": {
            "median": round(statistics.median(scores), 3),
            "min": round(min(scores), 3),
            "max": round(max(scores), 3),
        },
        "metrics": {},
        "observations": {},
    }
    for metric_id in METRIC_ORDER:
        values = [
            metric["score"]
            for run in runs
            for metric in run["metrics"]
            if metric["id"] == metric_id and metric["applicable"]
        ]
        summary["metrics"][metric_id] = (
            {"median": round(statistics.median(values), 3), "n": len(values)} if values else None
        )
    for key in ("files_written", "validation_rounds", "gap_records", "ledger_entries",
                "numbered_requirements", "findings_open"):
        values = []
        for run in runs:
            value = run.get("observations", {}).get(key)
            values.append(len(value) if isinstance(value, list) else (value or 0))
        if values:
            summary["observations"][key] = round(statistics.median(values), 2)
    durations = [run.get("run", {}).get("duration_s") for run in runs]
    durations = [d for d in durations if isinstance(d, (int, float))]
    if durations:
        summary["observations"]["duration_s"] = round(statistics.median(durations), 1)
    return summary


def group(runs: list[dict]) -> dict:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for run in runs:
        grouped.setdefault((run["case"], run["arm"]), []).append(run)
    return {key: summarize(value) for key, value in sorted(grouped.items())}


def cell(value) -> str:
    return "—" if value is None else f"{value['median']:.2f}"


def markdown(grouped: dict, runs: list[dict]) -> str:
    cases = sorted({case for case, _ in grouped})
    arms = [arm for arm in ARM_ORDER if any(a == arm for _, a in grouped)]
    lines: list[str] = ["# Benchmark results", ""]

    total_runs = sum(summary["n"] for summary in grouped.values())
    thin = [f"{case}/{arm} (n={grouped[(case, arm)]['n']})"
            for case, arm in grouped if grouped[(case, arm)]["n"] < CONFIDENT_N]
    lines += [
        f"{total_runs} scored run(s) across {len(cases)} case(s) and {len(arms)} arm(s). "
        "Median of each column, with the observed range on the total.",
        "",
    ]
    if thin:
        lines += [
            f"> Fewer than {CONFIDENT_N} runs per arm in: {', '.join(thin)}. "
            "Agent runs vary; read these as observations, not as measurements.",
            "",
        ]

    header = "| Case | Arm | n | Score | Range | " + " | ".join(
        METRIC_LABEL[m] for m in METRIC_ORDER
    ) + " |"
    lines += [header, "|" + "---|" * (5 + len(METRIC_ORDER))]
    for case in cases:
        for arm in arms:
            summary = grouped.get((case, arm))
            if not summary:
                continue
            lines.append(
                f"| {case} | {arm} | {summary['n']} | {summary['score']['median']:.2f} | "
                f"{summary['score']['min']:.2f}–{summary['score']['max']:.2f} | "
                + " | ".join(cell(summary["metrics"][m]) for m in METRIC_ORDER)
                + " |"
            )

    # Per-arm rollup across cases, computed from the runs rather than from the
    # medians above, so one case with more runs does not count twice.
    lines += ["", "## By arm, across every case", ""]
    lines += ["| Arm | n | Score | " + " | ".join(METRIC_LABEL[m] for m in METRIC_ORDER) + " |"]
    lines += ["|" + "---|" * (3 + len(METRIC_ORDER))]
    rollup: dict[str, dict] = {}
    for arm in arms:
        arm_runs = [run for run in runs if run["arm"] == arm]
        if not arm_runs:
            continue
        rollup[arm] = summarize(arm_runs)
        lines.append(
            f"| {arm} | {rollup[arm]['n']} | {rollup[arm]['score']['median']:.2f} | "
            + " | ".join(cell(rollup[arm]["metrics"][m]) for m in METRIC_ORDER)
            + " |"
        )

    if "extension" in rollup and len(rollup) > 1:
        lines += ["", "## Difference", ""]
        for other in [a for a in ARM_ORDER if a in rollup and a != "extension"]:
            delta = rollup["extension"]["score"]["median"] - rollup[other]["score"]["median"]
            lines.append(
                f"- extension − {other}: **{delta:+.2f}** on the total "
                f"(n={rollup['extension']['n']} vs {rollup[other]['n']})"
            )
            for metric_id in METRIC_ORDER:
                left, right = rollup["extension"]["metrics"][metric_id], rollup[other]["metrics"][metric_id]
                if left and right:
                    lines.append(
                        f"  - {METRIC_LABEL[metric_id]}: {left['median']:.2f} vs "
                        f"{right['median']:.2f} ({left['median'] - right['median']:+.2f})"
                    )

    lines += [
        "",
        "## What was observed, not scored",
        "",
        "| Arm | Files written | Validation rounds | Gap records | Ledger entries | "
        "Numbered requirements |",
        "|" + "---|" * 6,
    ]
    for arm in arms:
        if arm not in rollup:
            continue
        obs = rollup[arm]["observations"]
        lines.append(
            f"| {arm} | {obs.get('files_written', 0):g} | {obs.get('validation_rounds', 0):g} | "
            f"{obs.get('gap_records', 0):g} | {obs.get('ledger_entries', 0):g} | "
            f"{obs.get('numbered_requirements', 0):g} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="?", default="benchmarks/results")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--out")
    args = parser.parse_args()

    runs = load(Path(args.results))
    if not runs:
        print(f"no score.json under {args.results}. Run and score something first.")
        raise SystemExit(1)

    grouped = group(runs)
    if args.format == "json":
        payload = json.dumps(
            {f"{case}/{arm}": summary for (case, arm), summary in grouped.items()},
            indent=2,
        )
    else:
        payload = markdown(grouped, runs)

    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
