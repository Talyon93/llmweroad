"""Re-run the judge on a saved run and save it as a new run, then report agreement with the
hand labels in evals/judge_labels.jsonl.

uv run python scripts/rejudge.py evals/results/<run>.json --label <new-label>
"""

import argparse
import json
from pathlib import Path

from casavaiano.config import EVALS_DIR
from casavaiano.evals.judge import JudgeVerdict
from casavaiano.evals.runner import rejudge_run, rescore_run, save_run
from casavaiano.llm.anthropic_client import default_client


def agreement(run: dict) -> None:
    labels_path = EVALS_DIR / "judge_labels.jsonl"
    labels = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines()]
    by_id = {r["case"]["id"]: r for r in run["results"]}
    rows = []
    for label in labels:
        verdict = by_id[label["id"]]["judge"]
        judge_pass = JudgeVerdict.model_validate(verdict).passed
        rows.append((label["id"], label["pass"], judge_pass, verdict))
    agree = sum(human == judge for _, human, judge, _ in rows)
    print(f"\nJudge vs human labels: {agree}/{len(rows)} agree ({agree / len(rows):.0%})")
    for case_id, human, judge, v in rows:
        if human != judge:
            print(
                f"  {case_id}: human={human} judge={judge} "
                f"(F{v['faithfulness']} C{v['correctness']}) {v['reasoning'][:200]}"
            )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--label", required=True)
    p.add_argument("--agreement-only", action="store_true")
    p.add_argument("--rescore", action="store_true", help="recompute scores, no API calls")
    a = p.parse_args()
    run = json.loads(a.run.read_text(encoding="utf-8"))
    if a.rescore:
        run = rescore_run(run)
        save_run(run)
        print(f"rescored: answer correctness {run['summary']['answer_correctness']:.1%}")
    elif not a.agreement_only:
        run = rejudge_run(run, default_client(), a.label)
        json_path, _ = save_run(run)
        s = run["summary"]
        print(
            f"{json_path}\nanswer correctness {s['answer_correctness']:.1%}, "
            f"faithfulness {s['judge_faithfulness']}, judge cost ${s['judge_cost_total_usd']}"
        )
    agreement(run)


if __name__ == "__main__":
    main()
