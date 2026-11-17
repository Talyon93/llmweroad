import math
from collections import Counter, defaultdict
from typing import Any

from casavaiano.evals.checks import CaseChecks
from casavaiano.evals.dataset import EvalCase
from casavaiano.evals.judge import JudgeVerdict


def is_correct(case: EvalCase, checks: CaseChecks, verdict: JudgeVerdict | None) -> bool:
    """Headline per-case outcome."""
    if not checks.behavior_ok:
        return False
    if case.must_escalate:
        return True
    hard_checks = (checks.tools_ok, checks.tool_args_ok, checks.facts_ok)
    if any(check is False for check in hard_checks) or checks.forbidden_found:
        return False
    if verdict is None:
        return True
    if not verdict.passed:
        return False
    if case.behavior == ["clarify"] and not checks.escalated:
        return verdict.asks_for_missing_info
    return True


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(math.ceil(pct / 100 * len(ordered)) - 1, 0)
    return ordered[rank]


def rate(flags: list[bool | None]) -> float | None:
    known = [f for f in flags if f is not None]
    return round(sum(known) / len(known), 3) if known else None


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in results if not r.get("error")]
    checks = [r["checks"] for r in ok]
    must = [r for r in ok if r["case"]["behavior"] == ["escalate"]]
    escalated = [r for r in ok if r["checks"]["escalated"]]
    true_positive = [r for r in escalated if "escalate" in r["case"]["behavior"]]
    answered_verdicts = [r["judge"] for r in ok if r.get("judge") and not r["checks"]["escalated"]]
    draft_verdicts = [r["judge"] for r in ok if r.get("judge") and r["checks"]["escalated"]]
    latencies = [r["response"]["latency_ms"] for r in ok]
    costs = [r["response"]["cost_usd"] for r in ok]

    calls_by_model: Counter = Counter()
    cost_by_node: defaultdict[str, float] = defaultdict(float)
    for r in ok:
        for call in r["response"]["calls"]:
            calls_by_model[call["model"]] += 1
            cost_by_node[call["node"]] += call["cost_usd"]

    def mean(verdicts: list[dict], key: str) -> float | None:
        return round(sum(v[key] for v in verdicts) / len(verdicts), 2) if verdicts else None

    return {
        "n": len(results),
        "errors": len(results) - len(ok),
        "answer_correctness": rate([r["correct"] for r in results]),
        "intent_accuracy": rate([c["intent_ok"] for c in checks]),
        "language_accuracy": rate([c["language_ok"] for c in checks]),
        "behavior_accuracy": rate([c["behavior_ok"] for c in checks]),
        "escalation_precision": round(len(true_positive) / len(escalated), 3)
        if escalated
        else None,
        "escalation_recall": (
            round(sum(r["checks"]["escalated"] for r in must) / len(must), 3) if must else None
        ),
        "retrieval_hit_rate": rate([c["retrieval_hit"] for c in checks]),
        "tool_accuracy": rate(
            [
                None
                if c["tools_ok"] is None
                else bool(c["tools_ok"] and c["tool_args_ok"] is not False)
                for c in checks
            ]
        ),
        "facts_rate": rate([c["facts_ok"] for c in checks]),
        "judge_faithfulness": mean(answered_verdicts, "faithfulness"),
        "judge_correctness": mean(answered_verdicts, "correctness"),
        "judge_tone": mean(answered_verdicts, "language_and_tone"),
        "judge_draft_faithfulness": mean(draft_verdicts, "faithfulness"),
        "latency_p50_s": round(percentile(latencies, 50) / 1000, 2),
        "latency_p95_s": round(percentile(latencies, 95) / 1000, 2),
        "cost_per_query_usd": round(sum(costs) / len(costs), 5) if costs else None,
        "cost_total_usd": round(sum(costs), 4),
        "calls_by_model": dict(calls_by_model),
        "cost_by_node_usd": {k: round(v, 4) for k, v in sorted(cost_by_node.items())},
        "correctness_by_language": _group_rate(results, lambda r: [r["case"]["language"]]),
        "correctness_by_tag": _group_rate(results, lambda r: r["case"]["tags"] or ["untagged"]),
    }


def _group_rate(results: list[dict[str, Any]], keys) -> dict[str, dict[str, float]]:
    groups: defaultdict[str, list[bool]] = defaultdict(list)
    for r in results:
        for key in keys(r):
            groups[key].append(r["correct"])
    return {
        k: {"n": len(v), "correct": round(sum(v) / len(v), 3)} for k, v in sorted(groups.items())
    }
