"""Page classification engine: RapidOCR + weighted keywords (+ optional Nutrient v1 image model) -> final label."""
import json
import logging
import re
import threading
import time

import cv2
import numpy as np
from PIL import Image

try:
    import pymupdf
except ImportError:                      # older PyMuPDF
    import fitz as pymupdf

from .categories import LABELS

log = logging.getLogger("docapp.engine")


# ------------------------------------------------------------------ text helpers
def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r"['\u2019`]", "", text)                 # father's -> fathers
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_ignored(norm_text, patterns):
    for p in patterns:
        norm_text = re.sub(p, " ", norm_text)
    return re.sub(r"\s+", " ", norm_text).strip()


def kw_match(norm_text, compact_text, phrase):
    """Whole-word match (so 'pay' does not match 'payment'); spaces-removed fallback for long phrases (OCR drops spaces)."""
    p = normalize_text(phrase)
    if not p:
        return False
    if re.search(r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, p.split())) + r"(?![a-z0-9])", norm_text):
        return True
    c = p.replace(" ", "")
    return " " in p and len(c) >= 8 and c in compact_text


def text_evidence(raw_text, cfg):
    norm = strip_ignored(normalize_text(raw_text), cfg["ignore_phrases"])
    compact = norm.replace(" ", "")
    scores, matched = {}, {}
    for label in LABELS:
        entry = cfg["keywords"][label]
        m = {w: wt for w, wt in entry["keywords"].items() if kw_match(norm, compact, w)}
        matched[label] = m
        scores[label] = min(sum(m.values()) / entry["scale"], 1.0)
    return scores, matched


# ------------------------------------------------------------------ image helpers
def ink_ratio(image):
    """Share of clearly-dark pixels vs the LOCAL background (robust to shadows/tints), ignoring a 6% border."""
    g = np.asarray(image.convert("L").resize((300, max(1, int(300 * image.height / image.width)))), dtype=np.uint8)
    h, w = g.shape; g = g[int(h * .06):max(int(h * .94), int(h * .06) + 1), int(w * .06):max(int(w * .94), int(w * .06) + 1)]
    bg = cv2.medianBlur(g, 31)
    return float(((bg.astype(np.int16) - g.astype(np.int16)) > 40).mean())


def normalise_illumination(rgb):
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    bg = cv2.GaussianBlur(cv2.dilate(g, np.ones((25, 25), np.uint8)), (0, 0), 15)
    n = np.clip(g.astype(np.float32) / np.maximum(bg, 1) * 255, 0, 255).astype(np.uint8)
    return cv2.cvtColor(n, cv2.COLOR_GRAY2RGB)


MAX_RENDER_PX = 3000        # longest side; an A4 page at zoom 2 is ~1700 px, so normal PDFs are unaffected


def render_page(page, zoom):
    longest = max(page.rect.width, page.rect.height) * zoom
    if longest > MAX_RENDER_PX:                       # e.g. a large photo converted from JPG/TIFF
        zoom = zoom * MAX_RENDER_PX / longest
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


# ------------------------------------------------------------------ OCR (RapidOCR, loaded once)
_ocr = None
_ocr_lock = threading.Lock()


def ocr_engine():
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR(); log.info("RapidOCR loaded")
    return _ocr


def run_ocr(rgb):
    result, _ = ocr_engine()(rgb)
    lines = [{"text": str(r[1]), "confidence": float(r[2])} for r in (result or [])]
    return "\n".join(l["text"] for l in lines), lines


# ------------------------------------------------------------------ Nutrient v1 image model (optional, local, Apache-2.0)
class ImageModel:
    def __init__(self):
        self.state, self.message, self.providers = "idle", "not loaded", []
        self._sig, self._lock, self._predict = None, threading.Lock(), None

    def status(self):
        return {"state": self.state, "message": self.message, "providers": self.providers}

    def ensure(self, cfg):
        """Load (or reload when image-model settings changed). Never raises: on failure the app runs OCR-only."""
        m = cfg["image_model"]
        sig = json.dumps([m["enabled"], m["repo"], m["device"], m["prompts"]], sort_keys=True)
        with self._lock:
            if sig == self._sig:
                return self.state == "ready"
            self._sig = sig
            if not m["enabled"]:
                self.state, self.message, self._predict = "disabled", "disabled in configuration (OCR keywords only)", None
                return False
            self.state, self.message = "loading", "downloading / loading Nutrient v1 (first run downloads ~2.2 GB)"
            try:
                self._predict = self._load(m)
                self.state, self.message = "ready", f"Nutrient v1 ready ({', '.join(self.providers)})"
                log.info(self.message); return True
            except Exception as e:
                self._predict, self.state = None, "error"
                self.message = f"image model unavailable, using OCR keywords only: {type(e).__name__}: {e}"
                log.error(self.message); return False

    def _load(self, m):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from transformers import AutoImageProcessor, AutoTokenizer
        repo, sub = m["repo"], "modules/omni-image"
        paths = {n: hf_hub_download(repo_id=repo, filename=f"{sub}/{n}") for n in ("image_model.onnx", "text_model.onnx", "config.json")}
        cal = json.load(open(paths["config.json"], encoding="utf-8"))["calibration"]
        avail = ort.get_available_providers()
        want_gpu = m["device"] == "cuda" or (m["device"] == "auto" and "CUDAExecutionProvider" in avail)
        if m["device"] == "cuda" and "CUDAExecutionProvider" not in avail:
            log.warning("device=cuda requested but onnxruntime has no CUDA provider (install onnxruntime-gpu); using CPU")
            want_gpu = False
        provs = (["CUDAExecutionProvider"] if want_gpu else []) + ["CPUExecutionProvider"]
        img_s = ort.InferenceSession(paths["image_model.onnx"], providers=provs)
        txt_s = ort.InferenceSession(paths["text_model.onnx"], providers=provs)
        self.providers = img_s.get_providers()
        proc = AutoImageProcessor.from_pretrained(repo, subfolder=sub)
        tok = AutoTokenizer.from_pretrained(repo, subfolder=sub)
        names = list(m["prompts"].keys())
        t = tok([m["prompts"][n] for n in names], padding=True, truncation=True, max_length=64, return_tensors="np")
        emb = txt_s.run(["text_emb"], {"input_ids": t["input_ids"].astype(np.int64), "attention_mask": t["attention_mask"].astype(np.int64)})[0]
        scale, bias = float(cal["scale"]), float(cal["bias"])

        def predict(image):
            pv = proc(images=[image.convert("RGB")], return_tensors="np")["pixel_values"].astype(np.float16)
            ie = img_s.run(["image_emb"], {"pixel_values": pv})[0]
            p = 1.0 / (1.0 + np.exp(-(scale * (ie @ emb.T)[0] + bias)))
            return {names[i]: float(p[i]) for i in range(len(names))}
        return predict

    def predict(self, image):
        return self._predict(image) if self._predict else None


IMAGE = ImageModel()


# ------------------------------------------------------------------ fusion + decision
def combine(image_scores, ocr_scores, cfg):
    wi, wo = cfg["weights"]["image"], cfg["weights"]["ocr"]
    if image_scores is None:                       # OCR-only mode: the OCR evidence carries full weight
        wi, wo = 0.0, 1.0
    final = {l: wi * (image_scores or {}).get(l, 0.0) + wo * ocr_scores[l] for l in LABELS}
    return dict(sorted(final.items(), key=lambda x: x[1], reverse=True))


def decide(final, matched, cfg):
    t = cfg["thresholds"]
    ranked = list(final.items()); best, score = ranked[0]; second, s2 = ranked[1]
    if not any(matched[l] for l in LABELS):
        return "UNKNOWN", score, "LOW EVIDENCE", "no keyword matched any known document type"
    if score < t["unknown"]:
        return "UNKNOWN", score, "LOW EVIDENCE", f"best evidence score {score:.2f} is below the unknown threshold {t['unknown']:.2f}"
    close = abs(score - s2) < t["review_margin"] and (cfg["review_any_pair"] or {best, second} <= {"invoice", "purchase_order"})
    if close:
        return best, score, "REVIEW REQUIRED", f"close to '{second}' ({s2:.2f})"
    status = "HIGH EVIDENCE" if score >= t["high"] else "MEDIUM EVIDENCE" if score >= t["medium"] else "LOW EVIDENCE"
    return best, score, status, ""


def classify_page(image, cfg):
    """OCR -> blank rule -> keyword evidence -> optional image model -> fusion -> decision."""
    t0 = time.perf_counter()
    rgb = np.array(image.convert("RGB"))
    text, lines = run_ocr(rgb)
    chars = len(re.sub(r"[^A-Za-z0-9]", "", text)); ink = ink_ratio(image); b = cfg["blank"]
    if chars < b["min_chars"] and cfg["ocr"]["retry_on_failure"] and ink >= b["max_ink"]:
        text2, lines2 = run_ocr(normalise_illumination(rgb))          # shadows/tints can make OCR return nothing
        if len(re.sub(r"[^A-Za-z0-9]", "", text2)) > chars:
            text, lines = text2, lines2; chars = len(re.sub(r"[^A-Za-z0-9]", "", text))
    ocr_time = time.perf_counter() - t0
    base = dict(ocr_chars=chars, ink=round(ink, 4), ocr_text=text, ocr_lines=lines, ocr_time=round(ocr_time, 3))
    if chars < b["min_chars"] and (not b["require_low_ink"] or ink < b["max_ink"]):
        return dict(base, label="BLANK_PAGE", evidence_score=1.0, status="BLANK RULE", reason=f"OCR found {chars} characters and the page has almost no ink",
                    image_top=[], matched={}, final_scores={}, image_time=0.0, total_time=round(time.perf_counter() - t0, 3))
    ocr_scores, matched = text_evidence(text, cfg)
    image_scores, image_time = None, 0.0
    m = cfg["image_model"]; skip_at = m["skip_when_ocr_evidence"]
    if m["enabled"] and not (skip_at > 0 and max(ocr_scores.values()) >= skip_at) and IMAGE.state == "ready":
        ti = time.perf_counter(); image_scores = IMAGE.predict(image); image_time = time.perf_counter() - ti
    final = combine(image_scores, ocr_scores, cfg)
    label, score, status, reason = decide(final, matched, cfg)
    top = sorted((image_scores or {}).items(), key=lambda x: x[1], reverse=True)[:5]
    return dict(base, label=label, evidence_score=round(score, 4), status=status, reason=reason, image_top=top,
                matched={k: v for k, v in matched.items() if v}, ocr_scores={k: round(v, 3) for k, v in ocr_scores.items() if v},
                final_scores={k: round(v, 3) for k, v in list(final.items())[:5]}, image_time=round(image_time, 3),
                image_used=image_scores is not None, total_time=round(time.perf_counter() - t0, 3))
