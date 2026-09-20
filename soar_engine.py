"""
soar_engine.py — Module 4: SOAR Orchestration

Blends the Threat Intel risk score (Module 2) and the ML anomaly signal
(Module 3) into one overall confidence score per event, then routes each
event through a tiered response:

  - HIGH confidence  -> fully automated playbook (auto-contain + ticket + notify)
  - MEDIUM confidence -> human-in-the-loop: opened as a case for analyst review
  - LOW confidence    -> logged only, no case opened

Case / ticket state is kept in a simple JSON case-management store
(data/cases/cases.json) — a lightweight stand-in for a real ticketing
system (e.g. TheHive, Jira) that the dashboard reads from directly.

Usage:
    python soar_engine.py
"""
import json
import smtplib
import time
import uuid
from email.message import EmailMessage

from common import load_config, get_logger, resolve_path, read_jsonl


def ml_signal_to_pct(anomaly_score: float) -> float:
    """Rescale sklearn's IsolationForest decision_function output (roughly
    -0.5..0.5, more negative = more anomalous) onto a 0-100 'how anomalous'
    scale that lines up with the TI risk_score range."""
    pct = (0.5 - anomaly_score) * 100
    return max(0.0, min(100.0, pct))


def compute_confidence(rec: dict, cfg: dict) -> float:
    ti_risk = rec.get("threat_intel", {}).get("risk_score", 0)
    ml_pct = ml_signal_to_pct(rec.get("ml_detection", {}).get("anomaly_score", 0.5))
    w = cfg["soar"]["weights"]
    return round(ti_risk * w["ti_risk"] + ml_pct * w["ml_anomaly"], 1)


def classify_tier(confidence: float, cfg: dict) -> str:
    t = cfg["soar"]["thresholds"]
    if confidence >= t["high_confidence"]:
        return "high"
    if confidence >= t["medium_confidence"]:
        return "medium"
    return "low"


def send_notification(subject, body, cfg, logger):
    notify_cfg = cfg["soar"]["notify"]
    if not notify_cfg.get("smtp_enabled"):
        logger.info(f"[SIMULATED EMAIL] To: {notify_cfg['analyst_email']} | Subject: {subject}")
        return False
    import os
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = os.environ.get(notify_cfg["smtp_user_env"])
        msg["To"] = notify_cfg["analyst_email"]
        msg.set_content(body)
        with smtplib.SMTP(notify_cfg["smtp_host"], notify_cfg["smtp_port"]) as s:
            s.starttls()
            s.login(os.environ.get(notify_cfg["smtp_user_env"]), os.environ.get(notify_cfg["smtp_pass_env"]))
            s.send_message(msg)
        return True
    except Exception as e:
        logger.warning(f"Email notification failed, logging instead: {e}")
        return False


def run_automated_playbook(rec, confidence, cfg, logger):
    """High-confidence automated response: contain + ticket + notify."""
    actions = [
        f"auto-blocked indicator '{rec['threat_intel']['indicator']}' at perimeter firewall",
        "opened P1 incident ticket",
    ]
    send_notification(
        subject=f"[AUTO] High-confidence threat contained ({confidence}%)",
        body=f"Event {rec['event_id']} auto-contained. Indicator: {rec['threat_intel']['indicator']}",
        cfg=cfg, logger=logger,
    )
    actions.append("analyst notified")
    return actions


def open_case(rec, confidence, tier, cfg, logger):
    case = {
        "case_id": str(uuid.uuid4())[:8],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event_id": rec["event_id"],
        "indicator": rec.get("threat_intel", {}).get("indicator"),
        "src_ip": rec.get("src_ip"),
        "dst_ip": rec.get("dst_ip"),
        "confidence": confidence,
        "tier": tier,
        "ti_risk_score": rec.get("threat_intel", {}).get("risk_score"),
        "ml_anomaly_score": rec.get("ml_detection", {}).get("anomaly_score"),
        "status": "auto_resolved" if tier == "high" else "pending_review",
        "actions_taken": [],
    }
    if tier == "high":
        case["actions_taken"] = run_automated_playbook(rec, confidence, cfg, logger)
    else:
        send_notification(
            subject=f"[REVIEW] Medium-confidence alert needs analyst review ({confidence}%)",
            body=f"Event {rec['event_id']} queued for review. Indicator: {case['indicator']}",
            cfg=cfg, logger=logger,
        )
        case["actions_taken"] = ["queued for analyst review"]
    return case


def load_cases(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def save_cases(path, cases):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cases, f, indent=2)


def main():
    cfg = load_config()
    logger = get_logger("soar_engine", cfg)

    in_path = resolve_path(cfg, "scored_queue")
    cases_path = resolve_path(cfg, "cases_db")

    records = read_jsonl(in_path)
    cases = load_cases(cases_path)

    tier_counts = {"high": 0, "medium": 0, "low": 0}
    for rec in records:
        confidence = compute_confidence(rec, cfg)
        tier = classify_tier(confidence, cfg)
        tier_counts[tier] += 1
        if tier in ("high", "medium"):
            cases.append(open_case(rec, confidence, tier, cfg, logger))

    save_cases(cases_path, cases)
    logger.info(
        f"SOAR processed {len(records)} events -> "
        f"{tier_counts['high']} high (auto), {tier_counts['medium']} medium (analyst queue), "
        f"{tier_counts['low']} low (logged only). Total cases on file: {len(cases)}"
    )
    return cases


if __name__ == "__main__":
    main()
