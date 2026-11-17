# Experiment log

Running notes on what was tried, what was measured and what was decided. The README summarises
the outcomes.

## 2026-11-17 · Embedding model

- Plan was `intfloat/multilingual-e5-small` via sentence-transformers. Rejected: pulls PyTorch
  (~1 GB+ in the Docker image) for a 69-chunk corpus.
- Chosen: `paraphrase-multilingual-MiniLM-L12-v2` via fastembed (ONNX, 220 MB, 384 dims, no
  PyTorch). Fallback if retrieval is weak: `paraphrase-multilingual-mpnet-base-v2` (768 dims, 1 GB).

## 2026-11-17 · Chunking, retrieval only (30 labelled queries, 10 per language, k=4)

`uv run python scripts/compare_chunking.py` → `evals/results/chunking_retrieval.json`

| strategy | chunks | avg words | hit@1 | hit@4 | MRR@4 | IT hit@1 |
|---|---|---|---|---|---|---|
| headings (one chunk per `##` section) | 69 | 53 | 0.87 | 0.93 | 0.89 | 0.90 |
| fixed (150 words, 30 overlap) | 31 | 135 | 0.83 | 0.90 | 0.87 | 0.60 |

- Headings wins overall and clearly on Italian. Caveat: a fixed chunk spans ~3 sections, so the
  section-level hit metric is lenient towards it. The end-to-end comparison (answer correctness)
  in M6 is the real test.
- n=30 is small: one query is 3.3 points.

Misses with headings:
- "Quanto costa la tassa di soggiorno?" → Italian idiom; the small model does not map it to
  "tourist tax" (the English phrasing scores 0.68 on the right chunk).
- "Can you pick us up from Florence airport?" → pulled towards Directions by "airport"; the
  Transfers section ranks 6th.

Idea for M4/M6: the classify node (runs first anyway) also outputs a short English search query.
Measure whether retrieving with it fixes these misses without hurting the rest.

## 2026-11-17 · LLM layer and Langfuse

Live smoke test (`uv run pytest -m live`):

| call | model | latency | tokens in/out | cost |
|---|---|---|---|---|
| structured classification, effort low, thinking off | claude-haiku-5-5 | 1.5 s | 308 / 16 | $0.000039 |
| one-word answer, effort low | claude-opus-5-5 | 0.9 s | 21 / 5 | $0.000184 |

Bug found by checking the trace instead of trusting it: every LLM call appeared **twice** in
Langfuse, as my own `detect` generation and as `anthropic.messages.create`. The Anthropic SDK 2.x
emits its own OpenTelemetry GenAI span and Langfuse 5 ingests known LLM instrumentation scopes by
default. Both carried cost, so trace totals were 2x the real spend.

- Fix: `Anthropic(open_telemetry=False)`; keep my own generation, which is named per graph node
  (needed for cost per node) and priced from my own table. Regression test added.
- Side check: Langfuse's built-in price for `claude-haiku-5-5` matched my table to the cent
  fraction ($0.0000388), an independent check of the cost maths.

## 2026-11-17 · First live agent run (9 hand-written messages, routing on)

`uv run python scripts/ask.py --today 2026-11-17 "..."`

| message | path | models | cost | latency |
|---|---|---|---|---|
| IT dogs allowed? | answered | haiku, haiku | $0.0006 | 6.8 s |
| EN room 7-10 May | answered, check_availability + 2x quote_stay | haiku, opus x3 | $0.0444 | 14.8 s |
| DE train + taxi | answered | haiku, haiku | $0.0003 | 3.7 s |
| IT complaint + refund | escalated by guard | haiku, opus | $0.0141 | 6.4 s |
| EN wedding 80 guests | escalated by guard | haiku, opus | $0.0146 | 8.0 s |
| EN prompt injection + 50% off | escalated by guard (discount_request) | haiku, opus | $0.0112 | 6.9 s |
| DE dog, 14-21 Aug | answered, check_availability: dog units booked | haiku, opus x2 | $0.0220 | 9.0 s |
| IT tourist tax 2 adults + child | answered | haiku, haiku | $0.0003 | 3.4 s |
| EN restaurant on Monday | answered | haiku, haiku | $0.0003 | 2.4 s |

Good: tool use correct on both booking questions (3 nights x €115 = €345, deposit €103.50;
August fully booked for dog-friendly units, suggested flexibility). Escalation drafts are usable
and list what Giulia must check. Weekday claims verified.

Problems found by reading the replies (inputs for the eval set and M6):
- **Grounding false negative.** Haiku computed the tourist tax itself (2 x €1.50 x 5 = €15),
  breaking prompt rule 2. Correct by luck, and it passed the amount check only because €15 is
  also the dog fee in the KB. Matching against a set of known numbers is a coarse net.
- **Ungrounded non-numeric fact.** DE reply: taxi from the station takes "etwa 20 Minuten" -
  not in the KB. The amount check cannot see this; the LLM judge must.
- **Register.** "Liebe Gästin, lieber Gast", "Ciao! ... Con affetto": too informal for the
  business. Left unfixed on purpose, to measure the prompt change in M6.
- **Cost spread.** A booking answer on Opus with 3 decide turns costs ~150x a Haiku FAQ answer.
  M6 candidate: Haiku for the tool loop on simple bookings.
