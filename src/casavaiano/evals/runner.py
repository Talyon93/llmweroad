import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from casavaiano.agent.graph import Assistant
from casavaiano.agent.state import AssistantResponse
from casavaiano.config import EVALS_DIR, ROOT_DIR, Settings, get_settings
from casavaiano.evals.checks import CaseChecks, run_checks
from casavaiano.evals.dataset import EvalCase, load_cases
from casavaiano.evals.judge import JudgeVerdict, judge_response
from casavaiano.evals.metrics import is_correct, summarize
from casavaiano.evals.report import markdown_report
from casavaiano.llm import LLMClient
from casavaiano.observability import Tracer, get_tracer
from casavaiano.rag.chunking import chunk_kb
from casavaiano.rag.retriever import Retriever, default_retriever

RESULTS_DIR = EVALS_DIR / "results"


@dataclass
class RunConfig:
    label: str
    routing: bool = True
    chunking: str = "headings"
    retrieval_query: str = "both"
    split: str = "dev"
    ids: list[str] = field(default_factory=list)
    limit: int | None = None
    concurrency: int = 4
    judge: bool = True

    def settings(self, base: Settings) -> Settings:
        return base.model_copy(
            update={
                "routing_enabled": self.routing,
                "chunking_strategy": self.chunking,
                "retrieval_query": self.retrieval_query,
            }
        )


def run_eval(
    config: RunConfig,
    llm: LLMClient,
    tracer: Tracer | None = None,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    tracer = tracer or get_tracer()
    settings = config.settings(get_settings())
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{config.label}"
    cases = load_cases(split=config.split, ids=config.ids or None)[: config.limit]

    if retriever is None:
        retriever = default_retriever(settings.chunking_strategy)
        retriever.ensure_index()
    chunks = {c.id: c for c in chunk_kb(settings.chunking_strategy)}
    assistant = Assistant(llm, retriever, settings, tracer)

    def evaluate(case: EvalCase) -> dict[str, Any]:
        record: dict[str, Any] = {"case": case.model_dump(mode="json")}
        try:
            response = assistant.run(
                case.message, today=case.today, session_id=run_id, tags=["eval", config.label]
            )
        except Exception as exc:  # a crash is a result, not a reason to stop the run
            return record | {"error": repr(exc), "correct": False}
        checks = run_checks(case, response, chunks)
        verdict, judge_cost = None, 0.0
        if config.judge:
            texts = [chunks[i].text for i in response.sources if i in chunks]
            try:
                verdict, result = judge_response(llm, settings.judge_model, case, response, texts)
                judge_cost = result.cost_usd
            except Exception as exc:
                record["judge_error"] = repr(exc)
        correct = is_correct(case, checks, verdict)
        _send_scores(tracer, response.trace_id, correct, checks.model_dump(), verdict)
        return record | {
            "response": response.model_dump(mode="json"),
            "checks": checks.model_dump(),
            "judge": verdict.model_dump() if verdict else None,
            "judge_cost_usd": judge_cost,
            "correct": correct,
        }

    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        results = list(pool.map(evaluate, cases))
    tracer.flush()

    summary = summarize(results)
    summary["judge_cost_total_usd"] = round(sum(r.get("judge_cost_usd", 0) for r in results), 4)
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "git": _git_version(),
        "config": asdict(config),
        "models": {
            "cheap": settings.cheap_model,
            "strong": settings.strong_model,
            "judge": settings.judge_model,
            "embedding": settings.embedding_model,
        },
        "summary": summary,
        "results": results,
    }


def save_run(run: dict[str, Any], directory: Path = RESULTS_DIR) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{run['run_id']}.json"
    md_path = directory / f"{run['run_id']}.md"
    json_path.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown_report(run), encoding="utf-8")
    return json_path, md_path


def _send_scores(tracer: Tracer, trace_id, correct: bool, checks: dict, verdict) -> None:
    tracer.score(trace_id, "eval_correct", float(correct))
    tracer.score(trace_id, "intent_ok", float(checks["intent_ok"]))
    if checks["retrieval_hit"] is not None:
        tracer.score(trace_id, "retrieval_hit", float(checks["retrieval_hit"]))
    if verdict:
        tracer.score(trace_id, "judge_faithfulness", verdict.faithfulness, verdict.reasoning)
        tracer.score(trace_id, "judge_correctness", verdict.correctness)


def _git_version() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "src", "data", "evals/dataset.jsonl"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return f"{commit}{'+dirty' if dirty else ''}"
    except OSError:
        return "unknown"


def rejudge_run(
    run: dict[str, Any], llm: LLMClient, label: str, tracer: Tracer | None = None
) -> dict[str, Any]:
    """Re-run only the judge on saved responses: cheap way to iterate on the rubric."""
    tracer = tracer or get_tracer()
    settings = get_settings()
    chunks = {c.id: c for c in chunk_kb(run["config"]["chunking"])}

    def evaluate(record: dict[str, Any]) -> dict[str, Any]:
        if record.get("error"):
            return record
        case = EvalCase.model_validate(record["case"])
        response = AssistantResponse.model_validate(record["response"])
        checks = CaseChecks.model_validate(record["checks"])
        texts = [chunks[i].text for i in response.sources if i in chunks]
        verdict, result = judge_response(llm, settings.judge_model, case, response, texts)
        return record | {
            "judge": verdict.model_dump(),
            "judge_cost_usd": result.cost_usd,
            "correct": is_correct(case, checks, verdict),
        }

    with ThreadPoolExecutor(max_workers=run["config"].get("concurrency", 4)) as pool:
        results = list(pool.map(evaluate, run["results"]))
    tracer.flush()
    summary = summarize(results)
    summary["judge_cost_total_usd"] = round(sum(r.get("judge_cost_usd", 0) for r in results), 4)
    config = run["config"] | {"label": label}
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}_{label}"
    return run | {
        "run_id": run_id,
        "rejudged_from": run["run_id"],
        "config": config,
        "summary": summary,
        "results": results,
    }


def rescore_run(run: dict[str, Any]) -> dict[str, Any]:
    """Recompute per-case correctness and the summary from stored checks and verdicts."""
    results = []
    for record in run["results"]:
        if record.get("error"):
            results.append(record)
            continue
        case = EvalCase.model_validate(record["case"])
        checks = CaseChecks.model_validate(record["checks"])
        verdict = JudgeVerdict.model_validate(record["judge"]) if record.get("judge") else None
        results.append(record | {"correct": is_correct(case, checks, verdict)})
    summary = summarize(results)
    summary["judge_cost_total_usd"] = run["summary"]["judge_cost_total_usd"]
    return run | {"summary": summary, "results": results}
