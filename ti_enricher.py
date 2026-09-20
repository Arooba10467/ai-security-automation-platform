"""
ti_enricher.py — Module 2: Threat Intelligence Enrichment

Looks up the IP / domain in each ingested record against VirusTotal,
AbuseIPDB and AlienVault OTX, caches results to avoid re-querying the same
indicator, and produces a blended 0-100 risk score.

If an API key isn't configured (VT_API_KEY / ABUSEIPDB_API_KEY / OTX_API_KEY
environment variables), that source degrades gracefully to a deterministic
simulated lookup instead of failing the whole pipeline — this keeps
Task 2's "graceful degradation if one module fails" requirement intact and
lets the platform be demoed without needing paid/rate-limited API access.

Usage:
    python ti_enricher.py
"""
import hashlib
import os
import time

import requests

from common import load_config, get_logger, resolve_path, read_jsonl, write_jsonl

SUSPICIOUS_HINTS = ["verify", "secure", "update", "login", "gift", "account", "support", "bank"]


def _simulated_score(indicator: str) -> int:
    """Deterministic 0-100 pseudo-score derived from the indicator itself,
    used when a live TI API key isn't available. Domains containing
    phishing-style keywords score higher, so demo data still looks
    realistic."""
    h = int(hashlib.sha256(indicator.encode()).hexdigest(), 16)
    base = h % 40  # 0-39 baseline
    if any(hint in indicator.lower() for hint in SUSPICIOUS_HINTS):
        base += 55
    return min(base, 100)


def query_virustotal(indicator, cfg, logger):
    key = os.environ.get(cfg["threat_intel"]["virustotal"]["api_key_env"])
    if not key:
        return {"source": "virustotal", "score": _simulated_score(indicator), "simulated": True}
    try:
        url = f'{cfg["threat_intel"]["virustotal"]["base_url"]}/domains/{indicator}'
        resp = requests.get(url, headers={"x-apikey": key}, timeout=5)
        resp.raise_for_status()
        stats = resp.json()["data"]["attributes"]["last_analysis_stats"]
        total = sum(stats.values()) or 1
        score = round(100 * (stats.get("malicious", 0) + stats.get("suspicious", 0)) / total)
        return {"source": "virustotal", "score": score, "simulated": False}
    except Exception as e:
        logger.warning(f"VirusTotal lookup failed for {indicator}: {e}; falling back to simulated score")
        return {"source": "virustotal", "score": _simulated_score(indicator), "simulated": True}


def query_abuseipdb(indicator, cfg, logger):
    key = os.environ.get(cfg["threat_intel"]["abuseipdb"]["api_key_env"])
    if not key:
        return {"source": "abuseipdb", "score": _simulated_score(indicator), "simulated": True}
    try:
        url = f'{cfg["threat_intel"]["abuseipdb"]["base_url"]}/check'
        resp = requests.get(
            url, headers={"Key": key, "Accept": "application/json"},
            params={"ipAddress": indicator}, timeout=5,
        )
        resp.raise_for_status()
        score = resp.json()["data"]["abuseConfidenceScore"]
        return {"source": "abuseipdb", "score": score, "simulated": False}
    except Exception as e:
        logger.warning(f"AbuseIPDB lookup failed for {indicator}: {e}; falling back to simulated score")
        return {"source": "abuseipdb", "score": _simulated_score(indicator), "simulated": True}


def query_otx(indicator, cfg, logger):
    key = os.environ.get(cfg["threat_intel"]["alienvault_otx"]["api_key_env"])
    if not key:
        return {"source": "otx", "score": _simulated_score(indicator), "simulated": True}
    try:
        url = f'{cfg["threat_intel"]["alienvault_otx"]["base_url"]}/indicators/domain/{indicator}/general'
        resp = requests.get(url, headers={"X-OTX-API-KEY": key}, timeout=5)
        resp.raise_for_status()
        pulse_count = resp.json().get("pulse_info", {}).get("count", 0)
        score = min(pulse_count * 10, 100)
        return {"source": "otx", "score": score, "simulated": False}
    except Exception as e:
        logger.warning(f"OTX lookup failed for {indicator}: {e}; falling back to simulated score")
        return {"source": "otx", "score": _simulated_score(indicator), "simulated": True}


def enrich_indicator(indicator, cfg, logger, cache):
    now = time.time()
    ttl = cfg["threat_intel"]["cache_ttl_hours"] * 3600
    cached = cache.get(indicator)
    if cached and (now - cached["cached_at"]) < ttl:
        return cached["result"]

    vt = query_virustotal(indicator, cfg, logger)
    abuse = query_abuseipdb(indicator, cfg, logger)
    otx = query_otx(indicator, cfg, logger)

    w = cfg["threat_intel"]["risk_weights"]
    risk_score = round(
        vt["score"] * w["virustotal"] + abuse["score"] * w["abuseipdb"] + otx["score"] * w["otx"]
    )
    result = {"indicator": indicator, "risk_score": risk_score, "sources": [vt, abuse, otx]}
    cache[indicator] = {"cached_at": now, "result": result}
    return result


def load_cache(path):
    import json
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_cache(path, cache):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def main():
    cfg = load_config()
    logger = get_logger("ti_enricher", cfg)

    in_path = resolve_path(cfg, "ingest_queue")
    out_path = resolve_path(cfg, "enriched_queue")
    cache_path = resolve_path(cfg, "ti_cache")

    records = read_jsonl(in_path)
    cache = load_cache(cache_path)

    enriched = []
    for rec in records:
        indicator = rec.get("domain") or rec.get("dst_ip")
        ti_result = enrich_indicator(indicator, cfg, logger, cache) if indicator else {
            "indicator": None, "risk_score": 0, "sources": []
        }
        rec["threat_intel"] = ti_result
        enriched.append(rec)

    write_jsonl(out_path, enriched)
    save_cache(cache_path, cache)
    logger.info(f"Enriched {len(enriched)} records ({len(cache)} unique indicators cached) -> {out_path}")
    return enriched


if __name__ == "__main__":
    main()
