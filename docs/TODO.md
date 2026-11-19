# TODO

## M6 · Experiments (postponed, next after M7/M8)

Baseline to beat: `evals/results/20261117-230359_routing-baseline-v2judge.json`
(dev split, routing on, headings chunking, judge v2): 88.7% answer correctness, $0.0085/query.
One dev run costs about $1.50 (agent ~$0.53 + judge ~$0.95). Budget for M6: about $12.

**Decided 2026-11-20: the real-question eval is the primary measure.** 70 real cases
(`scripts/real_eval.py`, git-ignored), each labelled with the expected behaviour (answer /
escalate / either; the owner set the rules for weddings, groups and discount requests). Metrics:
right behaviour, escalation precision/recall, agreement with the owner's facts on answered cases,
cost, latency. About $2 per run. The synthetic set stays as the safety check (prompt injection,
complaints, refunds, safety), one run per final configuration.

Owner rules that change today's behaviour (expect failures in the baseline):
- [x] Weddings and private events: Rocco answers "no" himself (live guard, 2026-11-20).
- [x] Discount request in any message: hand the whole message to the owner (already the case).

**First:** re-run the baseline. The answer prompt changed after it was measured (Rocco persona,
virtual-assistant signature, configurable owner name), so 88.7% is no longer the current agent.

Required comparisons:
- [x] Strong model only vs routing: routing wins (same behaviour, -25% cost), real eval 2026-11-20.
- [x] Chunking headings vs fixed, end to end: headings wins, real eval 2026-11-20.

Next, from the comparisons (the same 6 cases fail in every run):
- [x] Weddings and private events: answer "no" in live mode instead of escalating.
- [x] Groups without a head count ("five families", "three apartments"): count apartments or
      families, hand over from three apartments.
- [x] Cooking-evenings question: the KB now says the family cooks, no cooking classes.

Extra experiments, from findings in `docs/experiments.md`:
- [ ] Retrieval query: original vs rewritten vs both (`--retrieval-query`).
- [ ] Haiku answer step with adaptive thinking at low effort instead of thinking disabled
      (leaked reasoning in restaurant-it-02).
- [ ] Classifier risk flags: published offers are not `discount_request`; questions about pool
      rules are not `legal_or_safety` (prices-de-01, policies-it-02).
- [ ] Prompt: formal register (Lei / Sie), no assumptions about the guest's unit
      (restaurant-en-01, restaurant-de-02).
- [ ] booking-en-03: strong model asked for details instead of calling the tools.
- [ ] Haiku grammar slips in Italian ("Gli cani di assistenza", 2026-11-18 live run).
- [ ] Haiku for simple bookings with tools (booking answers on Opus cost ~150x an FAQ).

Rigor:
- [x] Repeat each configuration twice: up to 2 of 70 outcomes flip.
- [ ] Iterate on the dev split only; run the final configurations once on the test split.
- [x] Log every result, including what did not work, in `docs/experiments.md`.
- [x] Update the README results tables (real-question comparisons, 2026-11-20).

## M7 follow-up

- [x] Verify `docker build` and `docker run` locally: image 1.44 GB (model and index baked in),
      runs as non-root, /health and /chat OK, no downloads at startup, healthcheck healthy.
- [ ] Answer prompt: Opus uses markdown bold and numbered lists despite rule 4; the demo page
      renders bold, but replies are meant for email. Measure the prompt fix in M6.

## Real site (Rocco on the CasaVaiano website)

- [x] Availability from Slope's iCal (8 apartments, cached 15 min, July-August Saturday to
      Saturday). `AVAILABILITY_SOURCE=slope`; prices are never given (Smartpricing changes them
      daily): the guest gets the Slope booking link or a quote request to the owner.
- [x] Capacity of each apartment (`capacity` in data/real/lodgings.yaml): 4 + 1 extra bed, confirmed
- [ ] Minimum-stay restrictions set in Smartpricing are not in the iCal: Rocco may call free a
      stay the booking engine refuses. Add the rules or mention them in the reply.
- [x] Real knowledge base in data/real/kb (`KB_DIR=data/real/kb`): home page texts by hand,
      apartments and nearby places generated from the website by scripts/import_site_kb.py.
- [x] Fill the gaps listed in data/real/DA_COMPLETARE.md (check-in, deposit, cancellation,
      pets, minimum stay, opening period, tourist tax...): today those questions are emailed.
- [x] Public /chat response (`EXPOSE_INTERNALS=false`); escalations emailed to the owner over
      SMTP; guest contact via `contact` or `POST /contact` (see docs/widget-api.md).
- [x] SMTP configured (Gmail app password in .env) and real test emails sent: escalation + contact.
- [x] Chat history per session (server-side, 6 turns, 24 h; one instance: a shared
      store is needed if Cloud Run scales to several instances).
- [x] CORS restricted to `ALLOWED_ORIGINS`.
- [x] Per-IP rate limits (chat 20/10 min and 150/day, contact 5/hour) and a daily spend cap
      (1 USD, then 503 until midnight; /contact stays open).
- [x] Privacy notice on the site: messages go to Anthropic and Langfuse (retention wording from the providers' plans).

## Budget

The owner asked to stop spending on API credits (2026-11-20, M6 cost ~$17.5). Any paid eval or
LLM test needs his OK and a cost estimate first; prefer targeted case checks over full runs.

## Later

- [ ] Thumbs up/down in the widget, sent to Langfuse as scores, once traffic grows.
- [ ] A separate Anthropic key with a low limit for experiments, so they cannot stop Rocco.
- [ ] Simple FAQs answered by Opus (e.g. "che giochi ci sono per i bambini?", $0.015): check the
      answer route.

- [x] M9: deployed on Cloud Run (europe-west8), see docs/deploy.md.
- [x] Real knowledge base in `data/real/` (the fictional one stays for the demo eval) and
      re-run the evals.
