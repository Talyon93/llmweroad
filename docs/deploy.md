# Deploy (Google Cloud Run)

Live: https://rocco-966891647846.europe-west8.run.app · project `casavaiano-rocco-bot` ·
region `europe-west8` (Milan).

## Cost protection

- Budget "Rocco 5 EUR": native spending cap on Cloud Run, 5 EUR/month, gross cost (credits
  excluded); Cloud Run is paused at the cap and resumes next month. Alerts at 50/80/100%.
- Budget "Progetto 5 EUR (solo avvisi)": whole project, email alerts only.
- Rocco's own cap on Claude spend: `DAILY_BUDGET_USD=1`; per-IP rate limits in the app.
- Cloud Run: `min-instances=0`, `max-instances=1` (chat memory and limits are in process),
  CPU billed only during requests.

## Service

- Image built by Cloud Build from this repo (`.gcloudignore` keeps `.env` and eval data out):
  `europe-west8-docker.pkg.dev/casavaiano-rocco-bot/rocco/rocco:<tag>`; the image bakes the
  embedding model and both indexes (demo KB and real KB).
- 1 vCPU, **2 GiB** (1 GiB ran out of memory loading the embedding model), concurrency 8,
  timeout 120 s, service account `rocco-run` with read access to its secrets only.
- Secrets (Secret Manager, europe-west8): `anthropic-api-key`, `langfuse-public-key`,
  `langfuse-secret-key`, `smtp-password`, `casa-ical-<apartment>` (8).
- Plain env vars: `AVAILABILITY_SOURCE=slope`, `KB_DIR=data/real/kb`, `RETRIEVAL_K=6`,
  `EXPOSE_INTERNALS=false`, `ALLOWED_ORIGINS` (site domains), `TRUST_FORWARDED_FOR=true`,
  `DAILY_BUDGET_USD=1`, `OWNER_NAME`, `BOOKING_URL`, SMTP host/user/recipient, `LANGFUSE_HOST`.

## Update after a change

```bash
gcloud builds submit --region=europe-west8 --tag europe-west8-docker.pkg.dev/casavaiano-rocco-bot/rocco/rocco:v2
gcloud run deploy rocco --image=europe-west8-docker.pkg.dev/casavaiano-rocco-bot/rocco/rocco:v2 --region=europe-west8
```

Cold start: the first message after idle takes about 20 s (model loading); then 3-12 s.
`--min-instances=1` removes it at roughly 10-15 EUR/month.
