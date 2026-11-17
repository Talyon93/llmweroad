# TODO

## M6 · Experiments (postponed, next after M7/M8)

Baseline to beat: `evals/results/20261117-230359_routing-baseline-v2judge.json`
(dev split, routing on, headings chunking, judge v2): 88.7% answer correctness, $0.0085/query.
One dev run costs about $1.50 (agent ~$0.53 + judge ~$0.95). Budget for M6: about $12.

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
- [ ] Haiku for simple bookings with tools (booking answers on Opus cost ~150x an FAQ).

Rigor:
- [ ] Repeat one configuration twice to measure run-to-run noise.
- [ ] Iterate on the dev split only; run the final configurations once on the test split.
- [ ] Log every result, including what did not work, in `docs/experiments.md`.
- [ ] Update the README results tables.

## M7 follow-up

- [ ] Verify `docker build` and `docker run` locally (Docker Desktop was not running when M7
      was committed; the Dockerfile is written but not yet built).
- [ ] Answer prompt: Opus uses markdown bold and numbered lists despite rule 4; the demo page
      renders bold, but replies are meant for email. Measure the prompt fix in M6.

## Later

- [ ] M9 (optional): deploy on GCP Cloud Run with Secret Manager and a rate limit.
- [ ] Replace the fictional knowledge base in `data/` with the real CasaVaiano information and
      re-run the evals.
