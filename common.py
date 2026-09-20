"""
common.py — shared config loading and centralized logging setup used by
every module in the platform, so all 5 modules log to the same place in
the same format (Task 2 integration requirement: "Centralized logging
across all modules").
"""
import json
import logging
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def load_config(path: str = "config.yaml") -> dict:
    cfg_path = ROOT / path
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f)


def get_logger(name: str, cfg: dict) -> logging.Logger:
    logs_dir = ROOT / cfg["paths"]["logs_dir"]
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = ROOT / cfg["logging"]["file"]

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers)

    logger.setLevel(cfg["logging"].get("level", "INFO"))
    fmt = logging.Formatter(cfg["logging"]["format"])

    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def resolve_path(cfg: dict, key: str) -> Path:
    """Resolve a path from config['paths'][key] relative to project root."""
    p = ROOT / cfg["paths"][key]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def read_jsonl(path: Path):
    if not path.exists():
        return []
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_jsonl(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def write_jsonl(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
