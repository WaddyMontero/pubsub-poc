# Event-Driven Vendor Ingestion POC

This repo is a runnable architecture demo for replacing hourly vendor extraction jobs with event-triggered ingestion.

The demo keeps the familiar radar/extractor shape:

- `radar` receives Domx-style webhooks and publishes normalized change events.
- `extractor` consumes those events immediately, calls the vendor API, and writes landing records.
- `generator` creates live vendor changes so the flow can be shown without waiting for real vendor traffic.
- `mock_vendor_api` acts as a Domx-like API.

The business logic is adapter-based:

- Local mode: Redpanda, which is Kafka-compatible, plus Postgres.
- GCP mode: Pub/Sub plus BigQuery and GCS audit proof files, with Cloud Run as the primary runtime.

## Local Demo

Start everything:

```bash
docker compose up --build
```

In another terminal, watch records land:

```bash
./scripts/show_local_rows.sh
```

Audit proof files are written locally after every 15 successful ingestions:

```bash
ls -la tmp/ingestion_audit
```

You should see rows appear every few seconds. That is the core point of the POC: webhook events trigger extraction immediately instead of waiting for an hourly cron batch.

## Service Endpoints

- Radar health: <http://localhost:8000/health>
- Radar webhook: `POST http://localhost:8000/webhooks/domx`
- Mock vendor health: <http://localhost:8001/health>
- Mock vendor change generator endpoint: `POST http://localhost:8001/simulate-change`

## GCP Shape

The Terraform-backed Cloud Run deployment is documented in [deploy/gcp/cloud-run.md](deploy/gcp/cloud-run.md).
GitHub Actions deployment and restart workflows are documented in [deploy/gcp/github-actions.md](deploy/gcp/github-actions.md).

Deploy it with:

```bash
PROJECT_ID="your-project-id" ./scripts/gcp/deploy.sh
```

The default cloud smoke test generates 15 messages, writes them to BigQuery, and flushes one JSONL proof file to GCS.
Cloud Run services keep one warm instance by default so the deployed demo appears continuously available until the killswitch is run. Set `CLOUD_RUN_MIN_INSTANCES=0` to allow scale-to-zero.

Tear it down with the killswitch:

```bash
./scripts/gcp/killswitch.sh
```

Or use the guarded `Destroy GCP` GitHub Action, which requires typing `destroy PROJECT_ID` before it runs.

For the team pitch, start with [docs/architecture.md](docs/architecture.md). It includes the current batch flow, the proposed event-driven flow, local deployment, GCP deployment, and a sequence diagram.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
