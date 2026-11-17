"""Retrieval-only comparison of the two chunking strategies on labelled queries.

Prints hit@1, hit@4, MRR@4 per strategy and per language, and saves the numbers to
evals/results/chunking_retrieval.json.
"""

import json
from collections import defaultdict

from casavaiano.config import EVALS_DIR
from casavaiano.rag.chunking import chunk_kb
from casavaiano.rag.metrics import first_hit_rank, hit_at, reciprocal_rank
from casavaiano.rag.retriever import default_retriever

K = 4


def evaluate(strategy: str, queries: list[dict]) -> dict:
    retriever = default_retriever(strategy)
    retriever.ensure_index()
    rows, misses = defaultdict(list), []
    for q in queries:
        rank = first_hit_rank(retriever.search(q["query"], K), q["relevant"])
        for group in ("all", q["lang"]):
            rows[group].append(rank)
        if not hit_at(rank, K):
            misses.append(q["query"])
    chunks = chunk_kb(strategy)
    summary = {
        group: {
            "n": len(ranks),
            "hit@1": round(sum(hit_at(r, 1) for r in ranks) / len(ranks), 3),
            f"hit@{K}": round(sum(hit_at(r, K) for r in ranks) / len(ranks), 3),
            f"mrr@{K}": round(sum(reciprocal_rank(r) for r in ranks) / len(ranks), 3),
        }
        for group, ranks in rows.items()
    }
    avg_words = sum(len(c.text.split()) for c in chunks) / len(chunks)
    return {
        "chunks": len(chunks),
        "avg_words": round(avg_words),
        "metrics": summary,
        "misses": misses,
    }


def main() -> None:
    path = EVALS_DIR / "retrieval_queries.jsonl"
    queries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    results = {s: evaluate(s, queries) for s in ("headings", "fixed")}

    print(f"| strategy | chunks | avg words | group | hit@1 | hit@{K} | MRR@{K} |")
    print("|---|---|---|---|---|---|---|")
    for strategy, r in results.items():
        for group, m in r["metrics"].items():
            print(
                f"| {strategy} | {r['chunks']} | {r['avg_words']} | {group} (n={m['n']}) "
                f"| {m['hit@1']:.2f} | {m[f'hit@{K}']:.2f} | {m[f'mrr@{K}']:.2f} |"
            )
    for strategy, r in results.items():
        print(f"\n{strategy} misses@{K}: {r['misses'] or 'none'}")

    out = EVALS_DIR / "results" / "chunking_retrieval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {out.relative_to(EVALS_DIR.parent)}")


if __name__ == "__main__":
    main()
