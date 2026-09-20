# Tech Stack & Rationale

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.12 | Single language across all 5 modules — matches every prior week of the internship, keeps the integration surface simple (one interpreter, one dependency set). |
| Data handling | pandas, JSON/JSONL | CSV/JSON log parsing and normalization (Module 1); JSONL is the queue format because it's streamable line-by-line, human-readable for debugging, and needs no schema server. |
| Config | PyYAML (`config.yaml`) | One human-editable file for every threshold, path, and credential *name* (never the credential itself) — keeps modules free of hard-coded values and makes threshold tuning (Task 4's "what would you do differently") a config change, not a code change. |
| Threat intel | `requests` against VirusTotal, AbuseIPDB, AlienVault OTX REST APIs | The three sources named in the brief; each is queried independently and blended so no single vendor's outage or rate limit takes down enrichment. |
| TI caching | JSON file cache (`data/cache/ti_cache.json`), 24h TTL | Avoids re-querying the same indicator (and burning free-tier rate limits) on every pipeline run — a real deployment would swap this for Redis, same interface. |
| ML detection | scikit-learn `IsolationForest` + `StandardScaler`, `joblib` | The exact model trained in Week 05; `joblib` is scikit-learn's standard serialization format, so the Week 05 artifacts load with no retraining. |
| SOAR / case mgmt | Python + JSON file store (`data/cases/cases.json`) | Lightweight stand-in for a real ticketing system (TheHive/Jira); same read/write contract the dashboard consumes directly, no separate DB to provision for a class capstone. |
| Notifications | `smtplib` (stdlib), simulated by default | Real SMTP send is implemented but disabled by default (`soar.notify.smtp_enabled: false` in config) so the demo doesn't depend on live mail credentials; enabling it is a one-line config change. |
| Dashboard | Streamlit + Plotly | Streamlit turns a Python script into a live web dashboard with no separate frontend build step — fastest path to Module 5's real-time KPI/alert/visualization requirements within the time available; Plotly gives interactive, drill-downable charts inside it. |
| Orchestration | `platform.py` CLI (argparse) | One entry point (`--mode full|ingest|enrich|detect|soar|dashboard`) that runs any module standalone or the whole pipeline together, satisfying the "modules run together" integration requirement while still letting each module be graded/demoed independently. |
| Logging | stdlib `logging`, centralized via `common.py` | One formatter, one log file, shared by all 5 modules — see `data_flow.md`. |
| Testing | `pytest` | Fast, minimal-boilerplate unit tests for the core pure functions in each module (normalization, risk scoring, ML inference, SOAR tier routing). |

## Data stores

- **Queues**: flat JSONL files (`data/queue/`) — see `data_flow.md` for why.
- **Cache**: flat JSON (`data/cache/ti_cache.json`).
- **Case DB**: flat JSON (`data/cases/cases.json`).

All three are swappable for Redis / a real database without touching
module logic, because every module only talks to them through
`common.py`'s small set of read/write helpers.
