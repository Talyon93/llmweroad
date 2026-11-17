from typing import Any

HEADLINE = [
    ("answer_correctness", "Answer correctness", "pct"),
    ("intent_accuracy", "Intent accuracy", "pct"),
    ("behavior_accuracy", "Behavior accuracy", "pct"),
    ("escalation_precision", "Escalation precision", "pct"),
    ("escalation_recall", "Escalation recall", "pct"),
    ("retrieval_hit_rate", "Retrieval hit rate", "pct"),
    ("tool_accuracy", "Tool accuracy", "pct"),
    ("facts_rate", "Key facts present", "pct"),
    ("judge_faithfulness", "Judge faithfulness (0-3)", "num"),
    ("judge_correctness", "Judge correctness (0-3)", "num"),
    ("judge_tone", "Judge language & tone (0-3)", "num"),
    ("latency_p50_s", "Latency p50 (s)", "num"),
    ("latency_p95_s", "Latency p95 (s)", "num"),
    ("cost_per_query_usd", "Cost per query (USD)", "usd"),
]


def fmt(value: Any, kind: str) -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{value * 100:.1f}%"
    if kind == "usd":
        return f"${value:.4f}"
    return f"{value:.2f}"


def markdown_report(run: dict[str, Any]) -> str:
    s = run["summary"]
    c = run["config"]
    lines = [
        f"# Eval run {run['run_id']}",
        "",
        f"- git: `{run['git']}`, split: `{c['split']}`, cases: {s['n']}, errors: {s['errors']}",
        f"- routing: `{c['routing']}`, chunking: `{c['chunking']}`, "
        f"retrieval query: `{c['retrieval_query']}`",
        f"- models: {run['models']}",
        f"- agent cost: ${s['cost_total_usd']:.4f}, judge cost: ${s['judge_cost_total_usd']:.4f}",
        "",
        "| Metric | Value |",
        "|---|---|",
        *[f"| {label} | {fmt(s.get(key), kind)} |" for key, label, kind in HEADLINE],
        "",
        f"Calls by model: {s['calls_by_model']}  ",
        f"Cost by node: {s['cost_by_node_usd']}",
        "",
        "## Correctness by language",
        "",
        *[
            f"- {k}: {v['correct'] * 100:.0f}% (n={v['n']})"
            for k, v in s["correctness_by_language"].items()
        ],
        "",
        "## Failures",
        "",
    ]
    for r in run["results"]:
        if r["correct"]:
            continue
        case = r["case"]
        lines.append(f"### {case['id']}")
        lines.append(f"> {case['message']}")
        lines.append("")
        if r.get("error"):
            lines.append(f"- error: `{r['error']}`")
            continue
        resp, checks, verdict = r["response"], r["checks"], r.get("judge")
        lines.append(
            f"- expected `{case['behavior']}` / intent `{case['intent']}`; got `{resp['status']}` "
            f"/ `{resp['intent']}` (reason: {resp.get('escalation_reason')})"
        )
        failed = [k for k, v in checks.items() if v is False and k != "escalated"]
        if failed:
            lines.append(f"- failed checks: {', '.join(failed)}")
        if checks["missing_facts"]:
            lines.append(f"- missing facts: {checks['missing_facts']}")
        if verdict:
            lines.append(
                f"- judge: faithfulness {verdict['faithfulness']}, correctness "
                f"{verdict['correctness']}, tone {verdict['language_and_tone']} - "
                f"{verdict['reasoning']}"
            )
            if verdict["unsupported_claims"]:
                lines.append(f"- unsupported: {verdict['unsupported_claims']}")
        reply = resp["reply"].replace("\n", " ")
        lines.append(f"- reply: {reply[:600]}")
        lines.append("")
    return "\n".join(lines) + "\n"
