from common import load_config
from soar_engine import classify_tier, compute_confidence, ml_signal_to_pct


def test_ml_signal_to_pct_range():
    assert 0 <= ml_signal_to_pct(-0.5) <= 100
    assert 0 <= ml_signal_to_pct(0.5) <= 100
    assert ml_signal_to_pct(-0.5) > ml_signal_to_pct(0.5)


def test_classify_tier_boundaries():
    cfg = load_config()
    t = cfg["soar"]["thresholds"]
    assert classify_tier(t["high_confidence"], cfg) == "high"
    assert classify_tier(t["medium_confidence"], cfg) == "medium"
    assert classify_tier(t["medium_confidence"] - 1, cfg) == "low"


def test_compute_confidence_blends_ti_and_ml():
    cfg = load_config()
    rec = {
        "threat_intel": {"risk_score": 90},
        "ml_detection": {"anomaly_score": -0.4},
    }
    confidence = compute_confidence(rec, cfg)
    assert confidence > cfg["soar"]["thresholds"]["high_confidence"]
