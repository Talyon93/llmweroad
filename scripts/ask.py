"""Ask the assistant one or more messages from the command line.

uv run python scripts/ask.py "Accettate cani?"
uv run python scripts/ask.py --today 2026-11-17 --no-routing "Room for 2 from 7 to 10 May?"
"""

import argparse
from datetime import date

from casavaiano.agent.graph import Assistant
from casavaiano.config import get_settings
from casavaiano.llm.anthropic_client import default_client
from casavaiano.observability import get_tracer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("messages", nargs="+")
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    parser.add_argument("--no-routing", action="store_true")
    args = parser.parse_args()

    settings = get_settings().model_copy(update={"routing_enabled": not args.no_routing})
    assistant = Assistant(default_client(), settings=settings)
    tracer = get_tracer()
    for message in args.messages:
        r = assistant.run(message, today=args.today, tags=["cli"])
        print("=" * 100)
        print(f"> {message}")
        print(f"[{r.status}] intent={r.intent} lang={r.language} reason={r.escalation_reason}")
        for t in r.tools:
            print(f"  tool {t.name}({t.input}) -> {str(t.output)[:200]}")
        print(f"\n{r.reply}\n")
        if r.escalation:
            print(f"  OWNER [{r.escalation.priority}]: {r.escalation.owner_summary}")
            print(f"  DRAFT: {r.escalation.draft_reply}")
            print(f"  CHECK: {r.escalation.missing_info}")
        models = ", ".join(f"{c.node}={c.model.split('-')[1]}" for c in r.calls)
        print(f"  {models} | ${r.cost_usd:.4f} | {r.latency_ms / 1000:.1f}s")
        print(f"  {tracer.trace_url(r.trace_id)}")
    tracer.flush()


if __name__ == "__main__":
    main()
