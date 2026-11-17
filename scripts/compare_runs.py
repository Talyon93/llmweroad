"""Compare saved eval runs side by side.

uv run python scripts/compare_runs.py evals/results/A.json evals/results/B.json
uv run python scripts/compare_runs.py --latest 3
"""

import argparse
import json
from pathlib import Path

from casavaiano.evals.report import HEADLINE, fmt
from casavaiano.evals.runner import RESULTS_DIR


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="*", type=Path)
    p.add_argument("--latest", type=int)
    a = p.parse_args()
    paths = a.paths or sorted(RESULTS_DIR.glob("2*.json"))[-(a.latest or 2) :]
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]

    print("| Metric | " + " | ".join(r["config"]["label"] for r in runs) + " |")
    print("|---|" + "---|" * len(runs))
    for key, label, kind in HEADLINE:
        print(f"| {label} | " + " | ".join(fmt(r["summary"].get(key), kind) for r in runs) + " |")
    print("| Cases | " + " | ".join(str(r["summary"]["n"]) for r in runs) + " |")

    ids = [{x["case"]["id"]: x["correct"] for x in r["results"]} for r in runs]
    if len(runs) == 2:
        flipped = sorted(i for i in ids[0] if i in ids[1] and ids[0][i] != ids[1][i])
        print(f"\nCases that changed outcome ({len(flipped)}):")
        for i in flipped:
            print(f"  {i}: {ids[0][i]} -> {ids[1][i]}")


if __name__ == "__main__":
    main()
