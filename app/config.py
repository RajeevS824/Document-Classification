"""Configuration. Only 4 values are user-editable (Configuration page / config.json); every other setting is a fixed default below."""
import copy
import json
import os
import threading
from pathlib import Path

from .categories import DEFAULT_FOLDERS, DEFAULT_IGNORE_PHRASES, DEFAULT_IMAGE_PROMPTS, DEFAULT_KEYWORDS

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
_lock = threading.Lock()

DEFAULT_CONFIG = {
    "output_dir": str(Path.home() / "DocClassifierOutput"),
    "split_mode": "by_label",            # by_label: one PDF per type | by_group: one PDF per run of consecutive pages
    "overwrite_existing": False,         # False -> <name>_2, <name>_3 ... when the output folder already exists
    "save_blank_pages": True,
    "merge_unknown_into_others": False,  # True -> UNKNOWN pages are saved in the 'others' folder
    "keep_uploads": False,
    "json_include_ocr_text": True,       # put each page's OCR text inside the JSON file
    "review_any_pair": True,             # flag REVIEW REQUIRED when ANY two top types are close (not only invoice/PO)
    "weights": {"image": 0.40, "ocr": 0.60},
    "thresholds": {"unknown": 0.35, "review_margin": 0.08, "high": 0.65, "medium": 0.40},
    "blank": {"min_chars": 10, "max_ink": 0.01, "require_low_ink": True},
    "ocr": {"render_zoom": 300 / 72, "retry_on_failure": True},
    "image_model": {"enabled": True, "repo": "nutrientdocs/document-classification-v1", "device": "auto",
                    "skip_when_ocr_evidence": 0.0, "prompts": DEFAULT_IMAGE_PROMPTS},
    "ignore_phrases": DEFAULT_IGNORE_PHRASES,
    "keywords": DEFAULT_KEYWORDS,
    "folder_names": DEFAULT_FOLDERS,
}


# ---- the ONLY user-editable values (config.json holds just these four) ----
EDITABLE = {  # public name -> (section, key)
    "IMAGE_WEIGHT": ("weights", "image"),
    "OCR_WEIGHT": ("weights", "ocr"),
    "UNKNOWN_THRESHOLD": ("thresholds", "unknown"),
    "REVIEW_MARGIN": ("thresholds", "review_margin"),
}


def _defaults():
    return {name: DEFAULT_CONFIG[sec][key] for name, (sec, key) in EDITABLE.items()}


def _num(v, name):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")
    if not 0 <= v <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return v


def load_editable():
    vals = _defaults()
    with _lock:
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            for name in vals:
                try:
                    vals[name] = _num(raw[name], name)
                except Exception:
                    pass
    return vals


def load():
    """Full settings used by the engine = fixed defaults + the 4 editable values."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for name, v in load_editable().items():
        sec, key = EDITABLE[name]
        cfg[sec][key] = v
    return cfg


def save(body):
    vals = load_editable()
    for name in vals:
        if name in (body or {}):
            vals[name] = _num(body[name], name)
    if vals["IMAGE_WEIGHT"] + vals["OCR_WEIGHT"] <= 0:
        raise ValueError("IMAGE_WEIGHT + OCR_WEIGHT must be greater than 0")
    with _lock:
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(vals, indent=2), encoding="utf-8")
        os.replace(tmp, CONFIG_PATH)
    return vals
