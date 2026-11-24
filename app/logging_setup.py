import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"


def setup():
    """Create logs/ automatically and send app events to logs/app.log (+ console)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    if any(getattr(h, "_docapp", False) for h in root.handlers):
        return logging.getLogger("docapp")
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    fh = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"); fh._docapp = True
    sh = logging.StreamHandler(); sh._docapp = True
    for h in (fh, sh):
        h.setFormatter(fmt); root.addHandler(h)
    return logging.getLogger("docapp")
