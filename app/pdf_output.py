"""Create <output>/<pdf name>/<type>/<type>_document.pdf and the report files."""
import datetime
import json
import re
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from .categories import DISPLAY


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip(" .") or "document"


def unique_dir(parent: Path, name: str, overwrite: bool) -> Path:
    d = parent / name
    if overwrite or not d.exists():
        return d
    n = 2
    while (parent / f"{name}_{n}").exists():
        n += 1
    return parent / f"{name}_{n}"


def folder_for(label, cfg):
    if label == "UNKNOWN" and cfg["merge_unknown_into_others"]:
        label = "others"
    return cfg["folder_names"].get(label, label.lower())


def groups_of(results):
    """Consecutive pages with the same label -> [(label, [page indexes])]."""
    out = []
    for i, r in enumerate(results):
        if out and out[-1][0] == r["label"]:
            out[-1][1].append(i)
        else:
            out.append((r["label"], [i]))
    return out


def write_outputs(pdf_path: Path, results, out_root: Path, cfg, name=None):
    """Returns (job folder, list of files created). Page order inside every output PDF follows the source PDF."""
    job_dir = unique_dir(out_root, safe_name(name or pdf_path.stem), cfg["overwrite_existing"])
    job_dir.mkdir(parents=True, exist_ok=True)
    src = pymupdf.open(pdf_path); files = []
    try:
        if cfg["split_mode"] == "by_label":
            buckets = {}
            for i, r in enumerate(results):
                if r["label"] == "BLANK_PAGE" and not cfg["save_blank_pages"]:
                    continue
                buckets.setdefault(folder_for(r["label"], cfg), []).append(i)
            jobs = [(f, f"{f}_document.pdf", idx) for f, idx in buckets.items()]
        else:
            counts, jobs = {}, []
            for label, idx in groups_of(results):
                if label == "BLANK_PAGE" and not cfg["save_blank_pages"]:
                    continue
                f = folder_for(label, cfg); counts[f] = counts.get(f, 0) + 1
                jobs.append((f, f"{f}_document_{counts[f]}.pdf", idx))
        for folder, fname, idx in jobs:
            d = job_dir / folder; d.mkdir(parents=True, exist_ok=True)
            out = pymupdf.open()
            for i in idx:
                out.insert_pdf(src, from_page=i, to_page=i)
            out.save(d / fname); out.close()
            files.append({"folder": folder, "file": str(d / fname), "pages": [i + 1 for i in idx]})
    finally:
        src.close()
    return job_dir, files


def _page_range(pages):
    return f"{pages[0]}-{pages[-1]}" if len(pages) > 1 else str(pages[0])


def build_documents(results, files, include_text=True):
    """Document-wise view: one entry per run of consecutive pages with the same type (a 'document')."""
    docs = []
    for n, (label, idx) in enumerate(groups_of(results), 1):
        rs = [results[i] for i in idx]
        scores = [r["evidence_score"] for r in rs]
        pages = [i + 1 for i in idx]
        detail = []
        for i in idx:
            r = results[i]
            d = {"page": i + 1, "evidence_score": round(r["evidence_score"], 4), "status": r["status"], "reason": r.get("reason", ""),
                 "matched_keywords": r.get("matched", {}), "image_top_labels": [[k, round(v, 4)] for k, v in (r.get("image_top") or [])]}
            if include_text:
                d["ocr_text"] = r.get("ocr_text", "")
            detail.append(d)
        docs.append({
            "document_no": n, "document_type": label, "document_name": DISPLAY.get(label, label),
            "pages": pages, "page_range": _page_range(pages), "page_count": len(pages),
            "evidence_score_avg": round(sum(scores) / len(scores), 4), "evidence_score_min": round(min(scores), 4),
            "needs_review": label in ("UNKNOWN", "ERROR") or any(r["status"].startswith("REVIEW") or r["status"] == "ERROR" for r in rs),
            "output_file": next((f["file"] for f in files if pages[0] in f["pages"]), None),
            "page_details": detail})
    return docs


def write_json_report(out_root: Path, job_dir: Path, pdf_name, results, files, summary, cfg):
    """ONE document-wise JSON file in the main output folder: <output folder>/<pdf name>.json (no .txt files are created)."""
    docs = build_documents(results, files, cfg.get("json_include_ocr_text", True))
    data = {"file": pdf_name, "source_format": summary.get("source_format"), "converted_to_pdf": summary.get("converted_with") is not None,
            "converted_with": summary.get("converted_with"), "password_protected": summary.get("password_protected"), "processed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "total_pages": len(results), "total_documents": len(docs), "output_folder": str(job_dir),
            "pages_per_type": summary.get("counts", {}), "processing_seconds": summary.get("seconds"),
            "image_model": summary.get("image_model"), "settings_used": summary.get("config_used"), "documents": docs}
    path = out_root / f"{job_dir.name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path
