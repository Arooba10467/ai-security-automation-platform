"""
ingest_logs.py — Module 1: Data Ingestion Layer

Collects logs from multiple sources (flat files, a simulated REST API, and a
simulated live stream), normalizes every record to one common schema, and
writes the result as newline-delimited JSON onto the ingest queue that
ti_enricher.py reads from next.

Usage:
    python ingest_logs.py --source file --input data/raw_logs/sample_traffic_logs.csv
    python ingest_logs.py --source api
    python ingest_logs.py --source stream --limit 50
"""
import argparse
import csv
import json
import random
import time
import uuid
from pathlib import Path

from common import load_config, get_logger, resolve_path, write_jsonl

REQUIRED_FEATURES = ["dur", "spkts", "dpkts", "sbytes", "dbytes", "rate"]


def normalize_record(raw: dict, source: str) -> dict:
    """Map an arbitrary raw log row onto the platform's common schema."""
    return {
        "event_id": str(uuid.uuid4()),
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timestamp": raw.get("timestamp"),
        "source": source,
        "src_ip": raw.get("src_ip"),
        "dst_ip": raw.get("dst_ip"),
        "domain": raw.get("domain"),
        "proto": raw.get("proto"),
        "features": {k: float(raw[k]) for k in REQUIRED_FEATURES if k in raw},
    }


def ingest_from_file(path: Path, source_label: str = "file"):
    records = []
    if path.suffix.lower() == ".csv":
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                records.append(normalize_record(row, source_label))
    else:  # .json / .jsonl
        with open(path) as f:
            content = f.read().strip()
            rows = json.loads(content) if content.startswith("[") else [
                json.loads(line) for line in content.splitlines() if line.strip()
            ]
            for row in rows:
                records.append(normalize_record(row, source_label))
    return records


def ingest_from_api(cfg, n=25):
    """
    Simulated API endpoint ingestion. In production this would page through
    a real SIEM/log-forwarder REST API (`requests.get(...)`); here we
    simulate the same shape of response so the module can be demoed and
    tested without a live external dependency.
    """
    records = []
    for _ in range(n):
        raw = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "src_ip": f"10.0.{random.randint(0,5)}.{random.randint(2,254)}",
            "dst_ip": f"203.0.{random.randint(0,20)}.{random.randint(2,254)}",
            "domain": random.choice(["api.github.com", "verify-account-now.xyz", "mail.google.com"]),
            "proto": random.choice(["tcp", "udp"]),
            "dur": round(random.uniform(0.01, 10), 3),
            "spkts": random.randint(1, 80),
            "dpkts": random.randint(1, 80),
            "sbytes": random.randint(40, 9000),
            "dbytes": random.randint(40, 9000),
            "rate": round(random.uniform(1, 150), 2),
        }
        records.append(normalize_record(raw, "api"))
    return records


def ingest_stream(cfg, limit, on_record=None):
    """
    Simulated streaming ingestion: yields one normalized record at a time,
    as a real Kafka/webhook consumer would. `on_record`, if given, is called
    for each record (used by platform.py to feed downstream modules live).
    """
    for rec in ingest_from_api(cfg, n=limit):
        if on_record:
            on_record(rec)
        yield rec
        time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description="Module 1: Data Ingestion Layer")
    parser.add_argument("--source", choices=["file", "api", "stream"], default="file")
    parser.add_argument("--input", default="data/raw_logs/sample_traffic_logs.csv")
    parser.add_argument("--limit", type=int, default=25, help="records for api/stream modes")
    args = parser.parse_args()

    cfg = load_config()
    logger = get_logger("ingest_logs", cfg)
    out_path = resolve_path(cfg, "ingest_queue")

    if args.source == "file":
        records = ingest_from_file(Path(args.input))
    elif args.source == "api":
        records = ingest_from_api(cfg, n=args.limit)
    else:
        records = list(ingest_stream(cfg, limit=args.limit))

    write_jsonl(out_path, records)
    logger.info(f"Ingested {len(records)} records from source='{args.source}' -> {out_path}")
    return records


if __name__ == "__main__":
    main()
