# AI Security Automation Platform

THE ARZENS — AI, Automation & Security Engineering Track — Week 10 Advanced Capstone

An integrated platform combining log ingestion, threat intelligence
enrichment, ML anomaly detection (Isolation Forest), SOAR orchestration,
and a live Streamlit dashboard.

## Snapshots
<p align="center">
  <img src="ss/Screenshot%202026-09-22%20182616.png" alt="Screenshot 182616" width="800"><br><br>
  <img src="ss/Screenshot%202026-09-22%20182708.png" alt="Screenshot 182708" width="800"><br><br>
  <img src="ss/Screenshot%202026-09-22%20182734.png" alt="Screenshot 182734" width="800"><br><br>
  <img src="ss/Screenshot%202026-09-22%20182753.png" alt="Screenshot 182753" width="800"><br><br>
  <img src="ss/Screenshot%202026-09-22%20182817.png" alt="Screenshot 182817" width="800">
</p>

## Architecture

See `docs/architecture_diagram.png`, `docs/data_flow.md`,
`docs/tech_stack.md`, and `docs/integration_plan.md`.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Place your Week 05 model files at:
- `models/isolation_forest_model.pkl`
- `models/standard_scaler.pkl`  (a dict: `{"scaler": StandardScaler, "feature_cols": [...]}`)

(Already included in this repo, trained on `dur, spkts, dpkts, sbytes, dbytes, rate`.)

### Optional: live threat-intel API keys

The platform runs end-to-end with **zero** API keys (each TI source falls
back to a deterministic simulated score). To use real lookups, set any of:

```bash
export VT_API_KEY="..."
export ABUSEIPDB_API_KEY="..."
export OTX_API_KEY="..."
```

### Optional: real email notifications

Off by default. To enable, set `soar.notify.smtp_enabled: true` in
`config.yaml` and export `SOAR_SMTP_USER` / `SOAR_SMTP_PASS`.

## Running it

Run the whole pipeline:

```bash
python platform.py --mode full
```

Run one module at a time (useful for demoing each piece separately):

```bash
python platform.py --mode ingest --source file
python platform.py --mode enrich
python platform.py --mode detect
python platform.py --mode soar
python platform.py --mode dashboard      # or: streamlit run dashboard.py
```

`--source` for ingestion accepts `file` (default, reads
`data/raw_logs/sample_traffic_logs.csv`), `api` (simulated REST pull), or
`stream` (simulated live stream).

## Tests

```bash
pytest tests/ -v
```

> Run the `pytest` command directly (not `python -m pytest`) from this
> directory. Because the orchestrator is named `platform.py` (per the
> assignment spec), `python -m pytest` would insert this directory ahead
> of the standard library on `sys.path` and shadow Python's own
> `platform` module, which several dependencies (`uuid`, `joblib`) import
> internally. `platform.py` itself already works around this for normal
> runs — see the comment at the top of the file — but plain `pytest` is
> the simplest way to run the test suite itself.

## Project layout

```
config.yaml            # all settings — paths, thresholds, API key env var names
common.py               # shared config loader + centralized logging
platform.py              # main orchestrator (CLI)
ingest_logs.py           # Module 1: Data Ingestion
ti_enricher.py            # Module 2: Threat Intel Enrichment
ml_detector.py             # Module 3: ML Threat Detection
soar_engine.py              # Module 4: SOAR Orchestration
dashboard.py                  # Module 5: Dashboard (Streamlit)
models/                        # isolation_forest_model.pkl, standard_scaler.pkl
data/
  raw_logs/                     # sample input log file
  queue/                         # inter-module JSONL hand-offs
  cache/                          # threat-intel cache
  cases/                           # SOAR case/ticket store
logs/platform.log                  # centralized log output
tests/                               # pytest unit tests
docs/                                 # architecture + planning docs
```

## Sample data

`data/raw_logs/sample_traffic_logs.csv` contains 300 synthetic network-flow
records (~12% injected as anomalous — high packet counts/byte volumes/rate)
so a fresh clone demos meaningfully without needing a real log source.
