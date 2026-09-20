from common import load_config
from ml_detector import MLDetector


def _detector():
    cfg = load_config()
    return MLDetector(cfg)


def test_model_and_scaler_load():
    d = _detector()
    assert d.feature_cols == ["dur", "spkts", "dpkts", "sbytes", "dbytes", "rate"]


def test_score_returns_float_and_bool():
    d = _detector()
    score, is_anomaly = d.score(
        {"dur": 0.5, "spkts": 10, "dpkts": 8, "sbytes": 500, "dbytes": 300, "rate": 20.0}
    )
    assert isinstance(score, float)
    assert isinstance(is_anomaly, bool)


def test_extreme_traffic_flags_more_anomalous_than_normal_traffic():
    d = _detector()
    normal_score, _ = d.score(
        {"dur": 0.2, "spkts": 5, "dpkts": 4, "sbytes": 300, "dbytes": 200, "rate": 15.0}
    )
    extreme_score, _ = d.score(
        {"dur": 80, "spkts": 3000, "dpkts": 3000, "sbytes": 700000, "dbytes": 700000, "rate": 2500}
    )
    # Lower decision_function score = more anomalous.
    assert extreme_score < normal_score
