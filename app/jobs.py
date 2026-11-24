"""Background job runner: one file at a time (OCR/model are CPU heavy). Errors are caught PER PAGE.
Flow: upload -> (password step for protected PDF/Word) -> convert to PDF -> classify pages -> split PDFs + JSON."""
import logging
import queue
import threading
import time
import uuid
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from . import config as cfgmod
from . import convert, engine, pdf_output

log = logging.getLogger("docapp.jobs")
ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "data" / "uploads"
WORK = ROOT / "data" / "work"          # temporary unlocked / converted copies (deleted after each job)
MAX_PASSWORD_TRIES = 3


class JobManager:
    def __init__(self):
        self.jobs, self.q, self.lock = {}, queue.Queue(), threading.Lock()
        UPLOADS.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._worker, daemon=True, name="job-worker").start()

    @staticmethod
    def _summary(j):
        return {k: v for k, v in j.items() if k not in ("pages", "unlocked_path")}

    def submit(self, filename, saved_path, output_dir, kind, needs_password):
        jid = uuid.uuid4().hex[:10]
        job = dict(id=jid, filename=filename, upload=str(saved_path), kind=kind, source_format=Path(filename).suffix.lower().lstrip("."),
                   output_dir=output_dir, status="waiting_password" if needs_password else "queued", needs_password=needs_password,
                   tries_left=MAX_PASSWORD_TRIES, attempts=0, unlocked_path=None, converted_with=None,
                   total_pages=0, done_pages=0, pages=[], counts={}, job_dir=None, files=[], error=None,
                   created=time.time(), started=None, finished=None, seconds=None)
        with self.lock:
            self.jobs[jid] = job
        if needs_password:
            log.info("job %s waiting for password: %s", jid, filename)
        else:
            self.q.put(jid); log.info("job %s queued: %s -> %s", jid, filename, output_dir)
        return job

    # ---------------------------------------------------------------- password step (the password is never stored or logged)
    def unlock_job(self, jid, password):
        job = self.jobs.get(jid)
        if job is None or job["status"] != "waiting_password":
            raise ValueError("This file is not waiting for a password.")
        ext = ".pdf" if job["kind"] == "pdf" else ".docx"
        out = WORK / f"{jid}_unlocked{ext}"
        try:
            ok = convert.unlock(job["upload"], job["kind"], password, out)
        except convert.ConvertError as e:
            self._cleanup(job, keep_upload=False)
            job.update(status="failed", error=str(e), finished=time.time()); log.error("job %s unlock failed: %s", jid, e)
            return job
        finally:
            password = None
        if ok:
            job.update(status="queued", unlocked_path=str(out), error=None)
            log.info("job %s password accepted", jid); self.q.put(jid)
        else:
            job["attempts"] += 1; job["tries_left"] = MAX_PASSWORD_TRIES - job["attempts"]
            log.warning("job %s wrong password (attempt %d of %d)", jid, job["attempts"], MAX_PASSWORD_TRIES)
            if job["tries_left"] <= 0:
                self._cleanup(job, keep_upload=False)
                job.update(status="failed", error="failed: wrong password", finished=time.time())
            else:
                job["error"] = f"Wrong password. {job['tries_left']} {'try' if job['tries_left'] == 1 else 'tries'} left."
        return job

    def skip_job(self, jid):
        job = self.jobs.get(jid)
        if job is None or job["status"] != "waiting_password":
            raise ValueError("This file is not waiting for a password.")
        self._cleanup(job, keep_upload=False)
        job.update(status="skipped", error="Skipped. Remove the password from the file and upload it again.", finished=time.time())
        log.info("job %s skipped by user", jid)
        return job

    def get(self, jid, with_pages=True):
        j = self.jobs.get(jid)
        return None if j is None else (j if with_pages else self._summary(j))

    def list(self):
        return sorted((self._summary(j) for j in self.jobs.values()), key=lambda j: j["created"], reverse=True)

    @staticmethod
    def _cleanup(job, keep_upload):
        """Delete temporary copies (always) and the uploaded file (unless it should be kept)."""
        for key in ("unlocked_path",):
            if job.get(key):
                Path(job[key]).unlink(missing_ok=True); job[key] = None
        (WORK / f"{job['id']}.pdf").unlink(missing_ok=True)
        if not keep_upload:
            Path(job["upload"]).unlink(missing_ok=True)

    def _worker(self):
        while True:
            jid = self.q.get()
            try:
                if self.jobs[jid]["status"] == "queued":
                    self._run(self.jobs[jid])
            except convert.ConvertError as e:
                log.error("job %s could not be converted: %s", jid, e)
                self.jobs[jid].update(status="error", error=str(e), finished=time.time())
            except Exception as e:
                log.exception("job %s failed", jid)
                self.jobs[jid].update(status="error", error=f"{type(e).__name__}: {e}", finished=time.time())
            finally:
                job = self.jobs[jid]
                self._cleanup(job, keep_upload=cfgmod.load()["keep_uploads"] and job["status"] == "done")
                self.q.task_done()

    def _run(self, job):
        cfg = cfgmod.load()
        job.update(status="running", started=time.time())
        src = Path(job.get("unlocked_path") or job["upload"])
        pdf_path, info = convert.to_pdf(src, job["kind"], WORK / f"{job['id']}.pdf")      # PDF as is; others converted
        job["converted_with"] = info["converted_with"]
        if info["converted"]:
            log.info("job %s converted %s to PDF with the %s converter", job["id"], job["source_format"].upper(), info["converted_with"])
        engine.IMAGE.ensure(cfg)                      # never raises: falls back to OCR-only
        out_root = Path(job["output_dir"]); out_root.mkdir(parents=True, exist_ok=True)
        doc = pymupdf.open(pdf_path); job["total_pages"] = len(doc); results = []
        log.info("job %s started: %s (%d pages, image model: %s)", job["id"], job["filename"], len(doc), engine.IMAGE.state)
        for i, page in enumerate(doc):
            try:
                r = engine.classify_page(engine.render_page(page, cfg["ocr"]["render_zoom"]), cfg)
            except Exception as e:                    # one bad page must not stop the whole file
                log.exception("job %s page %d failed", job["id"], i + 1)
                r = dict(label="ERROR", evidence_score=0.0, status="ERROR", reason=f"{type(e).__name__}: {e}", ocr_text="", ocr_lines=[],
                         image_top=[], matched={}, final_scores={}, total_time=0.0)
            results.append(r)
            job["pages"].append({k: v for k, v in r.items() if k not in ("ocr_lines",)} | {"page": i + 1})
            job["counts"][r["label"]] = job["counts"].get(r["label"], 0) + 1
            job["done_pages"] = i + 1
            log.info("job %s page %d/%d -> %s (%.2f, %s) %.1fs", job["id"], i + 1, len(doc), r["label"], r["evidence_score"], r["status"], r.get("total_time", 0))
        doc.close()
        job_dir, files = pdf_output.write_outputs(pdf_path, results, out_root, cfg, name=Path(job["filename"]).stem)
        job["finished"] = time.time(); job["seconds"] = round(job["finished"] - job["started"], 1)
        summary = dict(file=job["filename"], total_pages=len(results), counts=job["counts"], seconds=job["seconds"],
                       source_format=job["source_format"], converted_with=job["converted_with"], password_protected=job["needs_password"],
                       image_model=engine.IMAGE.status(), config_used=dict(weights=cfg["weights"], thresholds=cfg["thresholds"], split_mode=cfg["split_mode"]))
        json_path = pdf_output.write_json_report(out_root, job_dir, job["filename"], results, files, summary, cfg)
        job.update(job_dir=str(job_dir), json_report=str(json_path), files=files, status="done")
        log.info("job %s done in %.1fs -> %s (JSON: %s)", job["id"], job["seconds"], job_dir, json_path)


MANAGER = None


def manager():
    global MANAGER
    if MANAGER is None:
        MANAGER = JobManager()
    return MANAGER
