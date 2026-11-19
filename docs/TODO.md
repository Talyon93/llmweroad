# TODO

## M6 · Experiments (postponed, next after M7/M8)

Baseline to beat: `evals/results/20261117-230359_routing-baseline-v2judge.json`
(dev split, routing on, headings chunking, judge v2): 88.7% answer correctness, $0.0085/query.
One dev run costs about $1.50 (agent ~$0.53 + judge ~$0.95). Budget for M6: about $12.

**First:** re-run the baseline. The answer prompt changed after it was measured (Rocco persona,
virtual-assistant signature, configurable owner name), so 88.7% is no longer the current agent.

Required comparisons:
- [ ] Strong model only vs routing (`--no-routing`): quality delta vs cost and latency.
- [ ] Chunking headings vs fixed, end to end (`--chunking fixed`).

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
- [ ] Repeat one configuration twice to measure run-to-run noise.
- [ ] Iterate on the dev split only; run the final configurations once on the test split.
- [ ] Log every result, including what did not work, in `docs/experiments.md`.
- [ ] Update the README results tables.

## M7 follow-up

- [x] Verify `docker build` and `docker run` locally: image 1.44 GB (model and index baked in),
      runs as non-root, /health and /chat OK, no downloads at startup, healthcheck healthy.
- [ ] Answer prompt: Opus uses markdown bold and numbered lists despite rule 4; the demo page
      renders bold, but replies are meant for email. Measure the prompt fix in M6.

## Real site (Rocco on the CasaVaiano website)

- [x] Availability from Slope's iCal (8 apartments, cached 15 min, July-August Saturday to
      Saturday). `AVAILABILITY_SOURCE=slope`; prices are never given (Smartpricing changes them
      daily): the guest gets the Slope booking link or a quote request to the owner.
- [ ] Capacity of each apartment (`capacity` in data/real/lodgings.yaml): until then Rocco
      cannot say which apartment fits the party and hands those requests to the owner.
- [ ] Minimum-stay restrictions set in Smartpricing are not in the iCal: Rocco may call free a
      stay the booking engine refuses. Add the rules or mention them in the reply.
- [x] Real knowledge base in data/real/kb (`KB_DIR=data/real/kb`): home page texts by hand,
      apartments and nearby places generated from the website by scripts/import_site_kb.py.
- [ ] Fill the gaps listed in data/real/DA_COMPLETARE.md (check-in, deposit, cancellation,
      pets, minimum stay, opening period, tourist tax...): today those questions are emailed.
- [x] Public /chat response (`EXPOSE_INTERNALS=false`); escalations emailed to the owner over
      SMTP; guest contact via `contact` or `POST /contact` (see docs/widget-api.md).
- [x] SMTP configured (Gmail app password in .env) and real test emails sent: escalation + contact.
- [x] Chat history per session (server-side, 6 turns, 24 h; one instance: a shared
      store is needed if Cloud Run scales to several instances).
- [x] CORS restricted to `ALLOWED_ORIGINS`.
- [x] Per-IP rate limits (chat 20/10 min and 150/day, contact 5/hour) and a daily spend cap
      (1 USD, then 503 until midnight; /contact stays open).
- [ ] Privacy notice on the site: messages go to Anthropic and Langfuse.

## Later

- [ ] M9 (optional): deploy on GCP Cloud Run with Secret Manager and a rate limit.
- [ ] Replace the fictional knowledge base in `data/` with the real CasaVaiano information and
      re-run the evals.
