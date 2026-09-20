# Integration Plan

## How the 5 modules connect

Each module is an independent, importable Python module with one pure
entry point (`main()`), so it can be run alone (for grading/testing each
piece) or chained by the orchestrator:

```
python ingest_logs.py --source file      # Module 1 standalone
python ti_enricher.py                    # Module 2 standalone
python ml_detector.py                    # Module 3 standalone
python soar_engine.py                    # Module 4 standalone
streamlit run dashboard.py               # Module 5 standalone
python platform.py --mode full           # all 5, chained
```

Hand-offs between modules are files, not direct function calls or shared
memory — this is intentional decoupling:

| From | To | Contract |
|---|---|---|
| Ingestion | Threat Intel | `data/queue/01_ingested.jsonl` — one normalized record per line |
| Threat Intel | ML Detection | `data/queue/02_enriched.jsonl` — adds `threat_intel{}` |
| ML Detection | SOAR | `data/queue/03_scored.jsonl` — adds `ml_detection{}` |
| SOAR | Dashboard | `data/cases/cases.json` — case/ticket records, read live |

Because the contract is a file format, any module can be re-run
independently against the same input without re-running the whole
pipeline, and a module can be swapped out (e.g. a different ML model) as
long as it still emits the same JSON shape.

## Configuration

All cross-module settings — file paths, API endpoints, cache TTL, SOAR
confidence thresholds, dashboard refresh rate — live in one `config.yaml`,
loaded once per module via `common.load_config()`. No module hard-codes a
path or a threshold.

## Authentication & secrets

- Threat-intel API keys (`VT_API_KEY`, `ABUSEIPDB_API_KEY`, `OTX_API_KEY`)
  and SMTP credentials (`SOAR_SMTP_USER`, `SOAR_SMTP_PASS`) are read from
  environment variables only — never written to `config.yaml` or checked
  into the repo.
- If a key is absent, that specific TI source degrades to a deterministic
  simulated score rather than crashing the pipeline (see
  `ti_enricher.py`'s `_simulated_score`), matching the "graceful
  degradation" requirement.

## Security controls

- No secrets in source control; `.env`/environment-variable based config.
- TI results are cached, reducing the number of outbound calls (smaller
  attack/exposure surface, respects vendor rate limits).
- SOAR's automated playbook only fires above a configurable high-confidence
  threshold; everything else routes to a human, limiting blast radius of a
  false positive.
- All actions taken (auto-contain, notify, case creation) are logged with
  a timestamp and case ID for auditability.

## Scalability approach

The current file-based queue/cache/case-store is intentionally the
simplest thing that satisfies the brief. To scale this beyond a
single-machine class demo:

1. **Queues** — replace `common.read_jsonl`/`write_jsonl` with a Kafka or
   Redis Streams producer/consumer. Each module's internal logic is
   unchanged; only the I/O helper swaps.
2. **TI cache** — move `data/cache/ti_cache.json` to Redis with the same
   24h TTL, so multiple ingestion workers share one cache instead of each
   having its own file.
3. **Case store** — move `data/cases/cases.json` to a real database
   (Postgres, or a dedicated case-management tool like TheHive) once
   concurrent writers are involved.
4. **ML inference** — batch `ml_detector.py` already vectorizes with
   numpy/sklearn; for higher throughput, wrap `MLDetector.score_batch` in
   a small model-serving process (e.g. FastAPI + joblib) so multiple
   ingestion workers can call it over HTTP instead of each loading the
   model in-process.
5. **Horizontal scaling** — because modules only communicate through the
   queue contract, each one can run as multiple parallel workers reading
   from the same Kafka topic/partition once the file queue is replaced.
