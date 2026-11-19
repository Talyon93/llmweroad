"""Compare Rocco with the owner on real guest questions.

1. build: pick ~30 replies to guests (from the sent-mail extraction, already free of personal
   data), spread over topics, and have Haiku rewrite each guest's questions as a new message in
   the same language, without names or dates.
2. run: Rocco answers each message in live mode (real KB and calendars); a judge compares the
   answer with the facts the owner wrote in his real reply.

Cases and reports go to evals/real/ (git-ignored): they derive from real emails.

    uv run python scripts/real_eval.py build --extract <sent_extract.jsonl> --n 70
    uv run python scripts/real_eval.py run --label baseline [--no-routing] [--chunking fixed]

labels.jsonl (written with the owner) gives each case the expected behaviour: answer, escalate or
either. The run reports behaviour accuracy and escalation precision/recall against it.
"""

import argparse
import json
import random
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from casavaiano.agent.graph import Assistant
from casavaiano.config import EVALS_DIR, Settings, get_settings
from casavaiano.llm import LLMRequest
from casavaiano.llm.anthropic_client import AnthropicClient
from casavaiano.observability import Tracer

OUT_DIR = EVALS_DIR / "real"
CASES = OUT_DIR / "cases.jsonl"
LABELS = OUT_DIR / "labels.jsonl"
TODAY = date(2026, 11, 19)
SKIP_ONLY = {"availability", "prices_quote", "other"}


class Rewrite(BaseModel):
    message: str = Field(description="The guest message")


class Comparison(BaseModel):
    agreement: Literal["consistent", "partial", "contradicts", "escalated"]
    same_points: list[str] = Field(description="Points where Rocco says what the owner said")
    missing_points: list[str] = Field(
        description="Owner's points relevant to the question that Rocco did not give"
    )
    contradictions: list[str] = Field(
        description="Where Rocco says something different from the owner, quoting both"
    )
    extra_claims: list[str] = Field(description="Facts Rocco states that the owner did not mention")
    note: str = Field(description="One sentence")


REWRITE_SYSTEM = """Write a short, natural message that a guest would send to a Tuscan agriturismo,
asking exactly the questions given. Write it in the language given. No names, no email addresses,
no phone numbers, no specific dates (say "in June" or "for a week" if a period matters). Two to
five sentences."""

COMPARE_SYSTEM = """You compare two answers to the same guest question about CasaVaiano, a family
agriturismo: what the OWNER wrote in a real email, and what ROCCO (the virtual assistant) wrote.
The owner's points are the reference. Judge only facts relevant to the question; ignore greetings,
tone and booking-specific details (prices for specific dates, availability on past dates).
- consistent: Rocco gives the owner's relevant facts, no contradiction
- partial: no contradiction, but Rocco misses relevant points
- contradicts: at least one fact differs
- escalated: Rocco handed the question to the owner instead of answering
Rocco never gives prices on purpose (they change daily): pointing to the booking system or a quote
instead of a price is not a contradiction."""


def build(extract_path: str, n: int, max_per_topic: int, since: str, seed: int = 7) -> None:
    rows = [
        json.loads(line) for line in Path(extract_path).read_text(encoding="utf-8").splitlines()
    ]
    rows = [
        r
        for r in rows
        if r.get("is_guest_correspondence")
        and r["guest_questions"]
        and r["owner_facts"]
        and set(r["topics"]) - SKIP_ONLY
        and r["month"] >= since
    ]
    random.Random(seed).shuffle(rows)
    rows.sort(key=lambda r: r["month"], reverse=True)
    picked, per_topic = [], Counter()
    for r in rows:
        topics = [t for t in r["topics"] if t not in SKIP_ONLY]
        if all(per_topic[t] >= max_per_topic for t in topics):
            continue
        picked.append(r)
        per_topic.update(topics)
        if len(picked) == n:
            break
    settings = get_settings()
    client = AnthropicClient(api_key=settings.anthropic_api_key.get_secret_value(), tracer=_quiet())

    def rewrite(r: dict) -> dict:
        language = r["language"] if len(r["language"]) == 2 else "en"
        result = client.complete(
            LLMRequest(
                model=settings.cheap_model,
                system=REWRITE_SYSTEM,
                max_tokens=1024,
                effort="low",
                disable_thinking=True,
                output_schema=Rewrite,
                name="rewrite",
                messages=[
                    {
                        "role": "user",
                        "content": f"Language: {language}\nQuestions:\n- "
                        + "\n- ".join(r["guest_questions"]),
                    }
                ],
            )
        )
        return {
            "month": r["month"],
            "language": language,
            "topics": r["topics"],
            "message": result.parsed.message,
            "owner_facts": [f"[{f['topic']}] {f['statement']}" for f in r["owner_facts"]],
            "cost": result.cost_usd,
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        cases = list(pool.map(rewrite, picked))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / ".gitignore").write_text("*\n", encoding="utf-8")
    with CASES.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cases, 1):
            f.write(json.dumps({"id": f"real-{i:02d}", **c}, ensure_ascii=False) + "\n")
    print(f"{len(cases)} cases, topics {dict(per_topic)}, ${sum(c['cost'] for c in cases):.4f}")


def run(label: str, overrides: dict) -> None:
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
    expected = _labels()
    base = get_settings()
    settings = base.model_copy(
        update={
            "availability_source": "slope",
            "kb_dir": "data/real/kb",
            "retrieval_k": 6,
            **overrides,
        }
    )
    quiet = _quiet()
    client = AnthropicClient(api_key=base.anthropic_api_key.get_secret_value(), tracer=quiet)
    assistant = Assistant(client, settings=settings, tracer=quiet)

    def evaluate(case: dict) -> dict:
        response = assistant.run(case["message"], today=TODAY)
        rocco = response.reply
        if response.status == "escalated" and response.escalation:
            rocco += f"\n\n[ESCALATED to the owner. Draft: {response.escalation.draft_reply}]"
        owner = "\n".join(case["owner_facts"])
        result = client.complete(
            LLMRequest(
                model=base.judge_model,
                system=COMPARE_SYSTEM,
                max_tokens=4096,
                effort="medium",
                output_schema=Comparison,
                name="compare",
                messages=[
                    {
                        "role": "user",
                        "content": f"GUEST QUESTION:\n{case['message']}\n\n"
                        f"OWNER (real reply, {case['month']}):\n{owner}\n\nROCCO:\n{rocco}",
                    }
                ],
            )
        )
        return {
            **case,
            "expected": expected.get(case["id"], "either"),
            "latency_ms": response.latency_ms,
            "status": response.status,
            "rocco": response.reply,
            "rocco_cost": response.cost_usd,
            "judge_cost": result.cost_usd,
            **result.parsed.model_dump(),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(evaluate, cases))
    summary = {"label": label, "overrides": overrides, **behaviour_metrics(results)}
    (OUT_DIR / f"results_{label}.json").write_text(
        json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (OUT_DIR / f"report_{label}.md").write_text(_report(results, summary), encoding="utf-8")
    cost = sum(r["judge_cost"] for r in results)
    print(json.dumps(summary, indent=1))
    print(f"judge ${cost:.4f}  report: {OUT_DIR / f'report_{label}.md'}")


def _labels() -> dict[str, str]:
    if not LABELS.exists():
        return {}
    rows = [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines()]
    return {r["id"]: r["expected"] for r in rows}


def behaviour_metrics(results: list[dict]) -> dict:
    """Right behaviour against the owner's labels, escalation precision/recall, agreement with
    the owner's facts on answered cases, cost and latency of Rocco alone."""
    escalated = [r["status"] == "escalated" for r in results]
    right = [
        r["expected"] == "either" or (r["expected"] == "escalate") == e
        for r, e in zip(results, escalated, strict=True)
    ]
    labelled = [(r["expected"], e) for r, e in zip(results, escalated, strict=True)]
    tp = sum(1 for x, e in labelled if x == "escalate" and e)
    fp = sum(1 for x, e in labelled if x == "answer" and e)
    fn = sum(1 for x, e in labelled if x == "escalate" and not e)
    answered = [r for r in results if r["status"] != "escalated"]
    good = sum(1 for r in answered if r["agreement"] == "consistent")
    wrong = sum(1 for r in answered if r["agreement"] == "contradicts")
    latencies = sorted(r["latency_ms"] for r in results)
    return {
        "cases": len(results),
        "right_behaviour": round(sum(right) / len(results), 3),
        "escalation_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "escalation_recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "answered": len(answered),
        "answered_consistent": good,
        "answered_contradicts": wrong,
        "agreement": dict(Counter(r["agreement"] for r in results)),
        "cost_per_message": round(sum(r["rocco_cost"] for r in results) / len(results), 5),
        "latency_p50_s": round(latencies[len(latencies) // 2] / 1000, 1),
        "latency_p95_s": round(latencies[int(len(latencies) * 0.95) - 1] / 1000, 1),
    }


def _report(results: list[dict], summary: dict) -> str:
    counts = Counter(r["agreement"] for r in results)
    by_topic = defaultdict(Counter)
    for r in results:
        for t in r["topics"]:
            by_topic[t][r["agreement"]] += 1
    lines = [
        "# Rocco vs the owner on real guest questions",
        "",
        f"Cases: {len(results)} · {dict(counts)}",
        "",
        "```",
        json.dumps(summary, indent=1),
        "```",
        "",
        "## By topic",
        "",
    ]
    lines += [f"- {t}: {dict(c)}" for t, c in sorted(by_topic.items())]
    lines += ["", "## Cases", ""]
    order = {"contradicts": 0, "partial": 1, "escalated": 2, "consistent": 3}
    for r in sorted(results, key=lambda r: order[r["agreement"]]):
        lines += [
            f"### {r['id']} · {r['agreement']} · expected {r['expected']}, got {r['status']}"
            f" · {', '.join(r['topics'])}",
            "",
            f"> {r['message']}",
            "",
            "Owner said:",
            *[f"- {f}" for f in r["owner_facts"]],
            "",
            f"Rocco ({r['status']}): {r['rocco']}",
            "",
        ]
        for key in ("contradictions", "missing_points", "extra_claims"):
            if r[key]:
                lines.append(f"- {key}: {r[key]}")
        lines += [f"- note: {r['note']}", ""]
    return "\n".join(lines)


def _quiet() -> Tracer:
    return Tracer(Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--extract", required=True)
    b.add_argument("--n", type=int, default=70)
    b.add_argument("--max-per-topic", type=int, default=7)
    b.add_argument("--since", default="2025-01")
    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--no-routing", action="store_true")
    r.add_argument("--chunking", choices=["headings", "fixed"])
    r.add_argument("--retrieval-query", choices=["original", "rewritten", "both"])
    args = parser.parse_args()
    if args.cmd == "build":
        build(args.extract, args.n, args.max_per_topic, args.since)
        return
    overrides = {}
    if args.no_routing:
        overrides["routing_enabled"] = False
    if args.chunking:
        overrides["chunking_strategy"] = args.chunking
    if args.retrieval_query:
        overrides["retrieval_query"] = args.retrieval_query
    run(args.label, overrides)


if __name__ == "__main__":
    main()
