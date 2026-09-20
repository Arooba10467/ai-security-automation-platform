from ingest_logs import normalize_record


def test_normalize_record_maps_common_schema():
    raw = {
        "timestamp": "2026-09-19T08:00:00", "src_ip": "10.0.0.1", "dst_ip": "203.0.0.1",
        "domain": "example.com", "proto": "tcp",
        "dur": "1.5", "spkts": "10", "dpkts": "8", "sbytes": "500", "dbytes": "300", "rate": "20.5",
    }
    rec = normalize_record(raw, source="file")
    assert rec["source"] == "file"
    assert rec["src_ip"] == "10.0.0.1"
    assert rec["features"]["dur"] == 1.5
    assert rec["features"]["spkts"] == 10.0
    assert "event_id" in rec and "ingested_at" in rec


def test_normalize_record_handles_missing_features():
    raw = {"timestamp": "2026-09-19T08:00:00", "src_ip": "10.0.0.1"}
    rec = normalize_record(raw, source="api")
    assert rec["features"] == {}
