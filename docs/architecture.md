# Event-Driven Vendor Ingestion Architecture

This POC is intentionally evolutionary. It keeps the radar/extractor split that already exists, then changes when extraction happens: immediately after a change event, not on an hourly cron schedule.

## Current Domx-Style Batch Flow

```mermaid
flowchart LR
    Domx["Domx vendor"] --> Webhook["Custom webhook endpoint"]
    Webhook --> Radar["Domxradar"]
    Radar --> Topic["Kafka webhook topic<br/>IDs and references"]
    Cron["Kubernetes hourly cronjob"] --> Extractor["Domxtractor"]
    Topic --> Extractor
    API["Domx API"] -->|"record payload"| Extractor
    Extractor --> Warehouse["Warehouse landing tables"]
```

## Proposed Event-Driven Flow

```mermaid
flowchart LR
    Vendor["Vendor webhook"] --> Radar["Radar service"]
    Radar --> Event["VendorChangeEvent"]
    Event --> Bus["MessageBus adapter<br/>Kafka-compatible or Pub/Sub"]
    Bus --> Extractor["Extractor worker"]
    VendorAPI["Vendor API"] -->|"record payload"| Extractor
    Extractor --> Sink["WarehouseSink adapter<br/>Postgres or BigQuery"]
    Extractor --> Audit["AuditSink adapter<br/>local JSONL or GCS JSONL"]
```

The webhook remains a trigger. It says "record X changed." The extractor uses that trigger to fetch the canonical data from the vendor API right away.

## Local Demo Deployment

```mermaid
flowchart TB
    Generator["generator container"] --> MockAPI["mock_vendor_api<br/>FastAPI"]
    Generator --> Radar["radar<br/>FastAPI"]
    Radar --> Redpanda["Redpanda<br/>Kafka-compatible topic"]
    Redpanda --> Extractor["extractor worker"]
    MockAPI -->|"record payload"| Extractor
    Extractor --> Postgres["Postgres<br/>landing_records"]
    Extractor --> AuditFiles["Local audit files<br/>tmp/ingestion_audit"]
```

Run it with:

```bash
docker compose up --build
```

## GCP Cloud Run Deployment

```mermaid
flowchart TB
    GeneratorJob["Cloud Run Job<br/>generator"] --> MockVendor["Cloud Run<br/>mock_vendor_api"]
    GeneratorJob --> RadarRun["Cloud Run<br/>radar"]
    Vendor["External vendor webhook"] --> RadarRun
    RadarRun --> PubSubTopic["Pub/Sub topic<br/>vendor-change-events"]
    PubSubTopic --> PushSub["Pub/Sub push subscription"]
    PushSub --> ExtractorRun["Cloud Run<br/>extractor /pubsub/push"]
    MockVendor -->|"record payload"| ExtractorRun
    VendorAPI["External vendor API"] -->|"record payload"| ExtractorRun
    ExtractorRun --> BigQuery["BigQuery<br/>landing_records"]
    ExtractorRun --> GCS["GCS bucket<br/>JSONL audit proofs"]
```

Cloud Run is the primary GCP target because it keeps the demo small: no cluster, no cron controller, and clear scaling semantics.

## One Change Sequence

```mermaid
sequenceDiagram
    participant Generator
    participant VendorAPI as Mock Vendor API
    participant Radar
    participant Bus as Message Bus
    participant Extractor
    participant Sink as Warehouse Sink
    participant Audit as Audit Sink

    Generator->>VendorAPI: POST /simulate-change
    VendorAPI-->>Generator: vendor_record_id + webhook trigger
    Generator->>Radar: POST /webhooks/domx
    Radar->>Bus: publish VendorChangeEvent
    Bus-->>Extractor: deliver event
    Extractor->>VendorAPI: GET /records/{vendor_record_id}
    VendorAPI-->>Extractor: canonical vendor record
    Extractor->>Sink: write landing record
    Extractor->>Audit: after 15 successful ingestions, write proof file
```

## Why This Is Easier To Sell

- The team does not need to throw away radar/extractor terminology.
- Kafka remains supported locally and for any Kafka-compatible deployment.
- GCP Pub/Sub is the recommended managed path for Cloud Run.
- The event schema makes vendor-specific webhooks look the same downstream.
- The audit proof files give the team a concrete trail of successfully ingested messages.
- The live generator makes latency and throughput visible in a meeting.
