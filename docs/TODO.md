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

- [ ] Real knowledge base and prices (the demo KB is fictional and names a fictional owner).
- [ ] Availability: real calendar or disable the tool (owner confirms).
- [ ] Public /chat response with reply and status only; owner summary and draft delivered
      to the owner (channel to decide), not to the browser.
- [ ] Chat history across turns in a session.
- [ ] CORS for the site domain, per-IP rate limit, spend cap.
- [ ] Privacy notice on the site: messages go to Anthropic and Langfuse.

## Later

- [ ] M9 (optional): deploy on GCP Cloud Run with Secret Manager and a rate limit.
- [ ] Replace the fictional knowledge base in `data/` with the real CasaVaiano information and
      re-run the evals.
