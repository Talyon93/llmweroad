"""Run the eval set and save results to evals/results/.

uv run python scripts/run_evals.py --label routing
uv run python scripts/run_evals.py --label strong-only --no-routing
uv run python scripts/run_evals.py --label fixed --chunking fixed --split all
uv run python scripts/run_evals.py --label smoke --ids pets-it-01 booking-en-01 --no-judge
"""

import argparse

from casavaiano.evals.report import HEADLINE, fmt
from casavaiano.evals.runner import RunConfig, run_eval, save_run
from casavaiano.llm.anthropic_client import default_client


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--no-routing", action="store_true")
    p.add_argument("--chunking", choices=["headings", "fixed"], default="headings")
    p.add_argument("--retrieval-query", choices=["original", "rewritten", "both"], default="both")
    p.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    p.add_argument("--ids", nargs="*", default=[])
    p.add_argument("--limit", type=int)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--no-judge", action="store_true")
    a = p.parse_args()

    config = RunConfig(
        label=a.label,
        routing=not a.no_routing,
        chunking=a.chunking,
        retrieval_query=a.retrieval_query,
        split=a.split,
        ids=a.ids,
        limit=a.limit,
        concurrency=a.concurrency,
        judge=not a.no_judge,
    )
    run = run_eval(config, default_client())
    json_path, md_path = save_run(run)
    s = run["summary"]
    print(f"\n{run['run_id']}  ({s['n']} cases, {s['errors']} errors)")
    for key, label, kind in HEADLINE:
        print(f"  {label:32} {fmt(s.get(key), kind)}")
    print(f"  agent cost ${s['cost_total_usd']:.4f}   judge cost ${s['judge_cost_total_usd']:.4f}")
    print(f"\n{json_path}\n{md_path}")


if __name__ == "__main__":
    main()
