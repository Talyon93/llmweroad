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

## 2026-11-17 · M5: eval set, first baseline, judge calibration

Dataset: 82 synthetic cases (62 dev / 20 test held out until the end of M6), IT 26 / EN 34 /
DE 21 / FR 1, all 13 intents, 18 must-escalate, 3 must-clarify. All 11 expected prices were
computed by hand and cross-checked against the tools before the first run (all matched).

### The first judge was wrong, not the agent

First dev run (routing on): **71.0%** answer correctness, judge faithfulness 1.98/3. Reading the
failures: the judge flagged "Giulia confirms after the 30% deposit" as an invented policy in ~10
replies. That fact is in the assistant's system prompt (and in about.md), but the judge only saw
the retrieved chunks. It was also inconsistent: the same sentence passed in other cases.

Calibration against my own labels (28 replies; 19 labelled blind, 9 failures labelled after
reading the first judge's reasoning, so less independent):

| judge version | agreement with human labels | dev answer correctness |
|---|---|---|
| v1: SOURCES = retrieved chunks + tool results | 18/28 (64%) | 71.0% |
| v2: + operator instructions count as sources | 27/28 (96%) | 90.3% |
| v2 + pass requires tone >= 2 | 27/28 (96%) | **88.7%** |

- The remaining disagreement (services-en-01, "roughly a one-hour drive" from the airport) is
  the judge being stricter than me; defensible.
- Tone rule: restaurant-it-02 had correct facts but **leaked English reasoning into the Italian
  reply** ("Rispondo in italiano: ..."). The judge scored tone 1, but the pass rule ignored tone.
  A reply you cannot send is not correct.
- `scripts/rejudge.py` re-runs only the judge on stored responses ($0.98 instead of $1.50 for a
  full run), and `--rescore` recomputes scores with no API calls.

Lesson: an LLM judge is a model under test too. Without the hand labels I would have "fixed"
the agent's prompt to stop mentioning Giulia, i.e. optimised against a broken metric.

### Baseline (routing on, headings chunking, judge v2): 88.7% on dev

Remaining 7 failures, all real:
- Over-escalation by the classifier's risk flags (precision 85.7%): "discount for a week"
  flagged as discount_request (it is a published offer); "children alone in the pool" flagged
  as legal_or_safety.
- Unsupported claims on the Haiku path: assumes the guest is in an apartment (restaurant-en-01);
  implies yogurt and cakes are vegan (restaurant-de-02); "one-hour drive" (services-en-01).
- Leaked reasoning with Haiku + thinking disabled (restaurant-it-02): the failure mode the
  Anthropic docs describe for disabled thinking.
- booking-en-03: Opus asked for guest details instead of calling the tools; Granaio is booked
  and needs 7 nights in high season.

Cost of one dev run: agent $0.53 (62 queries, $0.0085/query), judge $0.88-0.98.

## 2026-11-19 · Real knowledge base, informed by the owner's sent emails

Source: 268 replies to guests from the owner's mailbox (Jan 2025 - Nov 2026), read over IMAP
read-only. Haiku extracted general facts, paraphrased guest questions and style notes per email,
instructed to drop personal data; nothing raw saved, nothing sent to Langfuse. Cost: $0.10.

- Topics guests ask most: availability (140), apartments (137), prices/quote (112),
  deposit/payment (78), cancellation (59), check-in (51), pets (41), children (38).
- About 10 facts the owner repeats consistently (25% deposit, 30/7-day cancellation tiers, extra
  bed €100 per stay, no weddings, three barbecues...) were shown to the owner; he approved 8 and
  dropped 2 (vacuum cleaner, pricing remarks). 3 conflicts resolved by him (check-in time:
  Slope's 16-18 wins over older emails).
- Style: friendly in 216 of 268 replies ("Ciao NAME" / "Hello NAME", "Saluti" / "Best regards").
  Applied to the answer prompt in live mode only, so the demo eval baseline is not affected.

Live checks in real mode, and fixes:
- "Se prenoto e poi devo cancellare?" was classified booking_change and escalated. Classifier
  prompt now says a hypothetical cancellation question is `policies`. Re-test: answered.
- "Pisa airport + restaurant?": the directions section ranked 5th-6th behind long nearby-places
  chunks. Fix 1: section heading names the airport ("Come arrivare: in auto, dall'aeroporto di
  Pisa, strada sterrata") -> ranked 1st (0.60). Fix 2: with two questions in one message, 6 chunks
  dropped the restaurant section; `RETRIEVAL_K=6` (8 chunks after merging) answers both, $0.0004.

## 2026-11-19 · Rocco vs the owner on 30 real guest questions

`scripts/real_eval.py`: 30 replies to guests (Jun 2025 - Nov 2026) spread over 15 topics, each
guest's questions rewritten by Haiku as a new message without names or dates; Rocco answers in
live mode; an Opus judge compares with the facts the owner wrote in the real reply. Cases and
per-case reports stay in evals/real/ (git-ignored). Cost: $0.89 per run.

**First run was invalid, and found a real bug.** Rocco answered with the fictional demo KB
(Fienile, breakfast, pool May-September...). The script switched to live mode on a settings
copy, but `default_retriever()` re-read the global settings. The guard added earlier only checked
the toolbox, not the retriever. Fix: the retriever takes the assistant's settings, and the
assistant now refuses a retriever whose KB differs from its settings (regression test).

Valid run (real KB, live calendars):

| outcome | cases |
|---|---|
| consistent with the owner | 6 |
| consistent but missing points | 8 |
| contradicts the owner | 3 |
| handed to the owner | 13 |

- Escalations: ~9 of 13 genuinely need a human (existing bookings, transfers to verify,
  penalties, weddings, whole-property rental); the rest are topics missing from the KB (wine
  tasting, cooking evenings, convertible rental). No invented facts in guest-facing replies.
- Contradictions: 1 real error - Rocco said the Ginestra apartment does not exist. The embedding
  retrieved Fiordaliso (whose text mentions "ginestre in fiore") instead of the Ginestra chunk.
  Fixes: the apartments overview lists all 8 names, and sections named in the message are always
  retrieved (`Retriever.named`, max 3). Re-test: answered correctly. 1 is a site-vs-owner
  inconsistency (pool towels per person vs per towel); 1 is the judge reading a statement about
  three specific apartments ("all on the ground floor") as general.
- Recurring missing points: the pool is not heated (cold water in April/October), the stone walls
  keep apartments cool, pets €50 per dog.

## 2026-11-19 · Chat memory

Server-side per `session_id` (a client cannot invent earlier turns). The classifier sees the
previous conversation so "E la settimana dopo?" becomes a booking question with the right
dates; the answer model gets the earlier turns as messages; the owner's draft and email include
them; amounts from earlier replies count as grounded. Live check in real mode, 4 messages: the
second turn re-checked 24-31 July on its own and compared it with the week before; the fourth
("which of the free ones has AC?") answered Girasole for both weeks. Follow-ups no longer
greet again (first version opened every reply with "Ciao,").

## 2026-11-20 · Spending protection on Google Cloud

Plan was Google's documented kill switch (budget -> Pub/Sub -> Cloud Function that unlinks
billing). Dropped before deploying it: Cloud Billing now offers native spending caps ("Budgets &
caps"), one project and one eligible service per cap. Budget "Rocco 5 EUR": Cloud Run
(service 152E-C115-5142) only, monthly, 5 EUR, EXCLUDE_ALL_CREDITS (so the 269 EUR welcome credit
cannot hide usage), alerts at 50/80/100%; Cloud Run is paused at the cap and resumes at the start
of the next month. No custom code, no billing-admin permissions, no manual re-linking.
Rocco's own cap on LLM spend (Anthropic, not Google) is 1 USD/day.

## 2026-11-20 · First live bug from the website widget

Guest: "un appartamento al piano terra dal 27 luglio...". Rocco listed 3 ground-floor apartments;
there are 5. Each apartment is its own chunk and no chunk listed them by floor, so the answer
depended on which cards retrieval happened to return. Adding a per-floor list to the apartments
intro was not enough: embeddings ranked the single cards above the list (intro not in top 6).
Fix: floors in data/real/lodgings.yaml, a generated "Al piano terra: ..." line in the intro, and
retrieval now always adds the intro ("Overview") chunk of every document it retrieved from.
Re-test: "Gli alloggi al piano terra sono cinque: Capanna, Girasole, Ginestra, Cipresso e
Castagno". (The date check was right: 27 July 2027 is a Tuesday.)

## 2026-11-20 · Last KB gaps, and a false "I passed it on"

The owner answered the open items: pool towels €10 each (the site still says €5 per person per
week, to fix there), the car is essential (rent at Pisa or Florence, transfers on request), no
smoking indoors, barbecues free without booking, own organic olive oil and wines from a trusted
cellar, pizza or pasta evenings now and then. Retrieval ranks each new section 1st or 2nd.

Live check found a prompt bug: for an uncovered side question ("can we smoke on the terrace?",
before the KB said "terraces") Haiku wrote "I passed your question to Tommaso" and answered
without escalating, so nobody would have read it. Rule 1 told it to "say you will check with the
owner", a promise only escalate_to_owner can keep. Now: say the detail is missing and the owner
can answer it; never claim a hand-off without calling the tool; never mention "the context".
The train answer also stopped saying "the context I have doesn't name a station".

## 2026-11-20 · M6 baseline on 70 real guest questions

The real-question eval becomes M6's primary measure: 70 cases from the owner's sent replies
(Jan 2025 - Nov 2026, 17 topics), each labelled with the expected behaviour: answer 34,
escalate 29, either 7. Labels drafted by me from the owner's real replies; the owner set the
three rules for the doubtful cases: Rocco says "no" to weddings himself, groups needing three or
more apartments go to the owner, any discount request sends the whole message to the owner.
Two labels fixed after the run (rescored, no new API calls): two families in two apartments is
not a large group; adding a child to an existing booking may be answered or handed over.

Baseline (current production config: routing, headings chunking, both queries):

| Metric | Value |
|---|---|
| Right behaviour (answer vs hand over) | **87.1%** |
| Escalation precision / recall | 81.2% / 89.7% |
| Answered cases consistent / partial / contradicting the owner | 12 / 14 / 7 (of 33) |
| Cost per message (Rocco only) | $0.021 |
| Latency p50 / p95 | 8.1 s / 13.2 s |

Run cost $2.18 (Rocco $1.46, judge $0.72).

- Wrong hand-overs: 3 weddings (the guard escalates all events; the owner's rule says answer),
  a cooking-activities question, and two family questions that are answered when asked again.
- Missed hand-overs: five families for a week (no group size given, so the group guard never
  fired), and an existing booking asking "did you get my email, please prepare five towels".
- **Run-to-run noise is large:** re-asking the four wrongly escalated cases flipped two of them.
  Every M6 comparison needs at least two runs per configuration.
- Of the 7 contradictions, 4 are the owner's older emails disagreeing with the approved KB
  (check-in 14:00, "all apartments on the ground floor" about three specific ones) or the judge
  nitpicking. Real ones: (1) towels not found for a mixed message, because the fact lived only
  under "Supplementi" and apartment cards mentioning the pool outranked it; now also stated in
  "La piscina", retrieved 2nd. (2) Rocco inferred towels cost "€10 for the whole stay"; the KB
  says only "€10 per towel". (3) Three emails say June is Saturday-to-Saturday too, the KB says
  July and August only: question for the owner.
