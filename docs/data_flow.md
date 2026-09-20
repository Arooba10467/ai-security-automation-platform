# Data Flow

## End-to-end path

```
Log sources (files / simulated API / simulated stream)
        │
        ▼
[Module 1: Data Ingestion — ingest_logs.py]
  • parses CSV/JSON/JSONL, or pulls from an API/stream source
  • normalizes every record to one common schema:
      event_id, ingested_at, timestamp, source, src_ip, dst_ip,
      domain, proto, features{dur, spkts, dpkts, sbytes, dbytes, rate}
        │  writes data/queue/01_ingested.jsonl
        ▼
[Module 2: Threat Intel Enrichment — ti_enricher.py]
  • extracts the indicator (domain, else dst_ip) from each record
  • checks data/cache/ti_cache.json (24h TTL) before calling out
  • queries VirusTotal, AbuseIPDB, AlienVault OTX (falls back to a
    deterministic simulated score per source if no API key is set)
  • blends the three source scores into one risk_score (0-100)
  • attaches { threat_intel: { indicator, risk_score, sources[] } }
        │  writes data/queue/02_enriched.jsonl
        ▼
[Module 3: ML Threat Detection — ml_detector.py]
  • loads models/isolation_forest_model.pkl + standard_scaler.pkl
    (trained in Week 05 on 6 flow features)
  • scales features, runs IsolationForest.decision_function()
  • attaches { ml_detection: { anomaly_score, is_anomaly } }
        │  writes data/queue/03_scored.jsonl
        ▼
[Module 4: SOAR Orchestration — soar_engine.py]
  • confidence = 0.5 * ti_risk_score + 0.5 * rescaled_ml_anomaly_score
  • confidence >= 75  -> HIGH:   automated playbook (auto-contain,
                                  ticket, analyst notification)
  • 40 <= confidence < 75 -> MEDIUM: case opened, queued for a human
                                  analyst (human-in-the-loop)
  • confidence < 40   -> LOW:    logged only, no case opened
        │  writes/updates data/cases/cases.json
        ▼
[Module 5: Dashboard — dashboard.py]
  • reads data/cases/cases.json and data/queue/03_scored.jsonl directly
  • renders live alert feed, TI risk distribution, ML anomaly
    histogram, and SOAR tier breakdown; auto-refreshes every
    config.dashboard.refresh_seconds
```

## Why a file-based queue

Modules communicate through newline-delimited JSON files under
`data/queue/` rather than a message broker. This was a deliberate choice
for this capstone: it keeps the platform runnable with `python
platform.py --mode full` and zero external infrastructure (no Kafka/Redis
cluster to stand up for grading), while still giving each module a single,
inspectable hand-off contract. `integration_plan.md` documents how this
would be swapped for Kafka/Redis Streams in a production deployment
without changing any module's internal logic — only `common.py`'s
`read_jsonl`/`write_jsonl` helpers would be replaced with a
`consume()`/`produce()` client.

## Centralized logging

Every module calls `common.get_logger(name, cfg)`, which attaches the same
formatter and writes to the same file (`logs/platform.log`) plus stdout,
so a full pipeline run produces one interleaved, timestamped log rather
than five disconnected ones.
