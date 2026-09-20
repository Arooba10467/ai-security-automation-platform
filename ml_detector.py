"""
ml_detector.py — Module 3: ML Threat Detection

Loads the pre-trained Isolation Forest model + StandardScaler from Week 05
and scores every enriched record for anomalousness on real-time streaming
data (or a full batch, for the file-based demo).

Usage:
    python ml_detector.py
"""
import joblib
import numpy as np

from common import load_config, get_logger, resolve_path, read_jsonl, write_jsonl


class MLDetector:
    """Wraps the trained model so both batch (ml_detector.py) and streaming
    (platform.py --mode stream) callers share one inference path."""

    def __init__(self, cfg):
        model_path = resolve_path(cfg, "isolation_forest_model")
        scaler_path = resolve_path(cfg, "standard_scaler")
        self.model = joblib.load(model_path)
        scaler_bundle = joblib.load(scaler_path)
        self.scaler = scaler_bundle["scaler"]
        self.feature_cols = scaler_bundle["feature_cols"]
        self.alert_threshold = cfg["ml_detection"]["alert_threshold"]

    def score(self, features: dict):
        """features: dict with keys matching self.feature_cols.
        Returns (anomaly_score: float, is_anomaly: bool). Lower
        anomaly_score = more anomalous (sklearn IsolationForest convention).
        """
        x = np.array([[features.get(c, 0.0) for c in self.feature_cols]])
        x_scaled = self.scaler.transform(x)
        anomaly_score = float(self.model.decision_function(x_scaled)[0])
        is_anomaly = anomaly_score < self.alert_threshold
        return anomaly_score, is_anomaly

    def score_batch(self, records: list):
        for rec in records:
            score, is_anomaly = self.score(rec.get("features", {}))
            rec["ml_detection"] = {
                "anomaly_score": round(score, 5),
                "is_anomaly": is_anomaly,
                "model": "IsolationForest",
                "feature_cols": self.feature_cols,
            }
        return records


def main():
    cfg = load_config()
    logger = get_logger("ml_detector", cfg)

    in_path = resolve_path(cfg, "enriched_queue")
    out_path = resolve_path(cfg, "scored_queue")

    records = read_jsonl(in_path)
    detector = MLDetector(cfg)
    scored = detector.score_batch(records)

    n_anomalies = sum(1 for r in scored if r["ml_detection"]["is_anomaly"])
    write_jsonl(out_path, scored)
    logger.info(f"Scored {len(scored)} records, flagged {n_anomalies} anomalies -> {out_path}")
    return scored


if __name__ == "__main__":
    main()
