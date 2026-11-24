"""FastAPI backend + static frontend.  Run:  python -m uvicorn app.main:app --host 127.0.0.1 --port 8033"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config as cfgmod
from . import convert, engine, jobs, logging_setup
from .categories import CATEGORY_GROUPS, DISPLAY, LABELS, SYSTEM_LABELS

log = logging_setup.setup()
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
LAST_FOLDER_FILE = ROOT / "data" / "last_folder.json"
app = FastAPI(title="Document Page Classifier")


@app.on_event("startup")
def _startup():
    log.info("=== application started ===")
    jobs.manager()
    threading.Thread(target=lambda: engine.IMAGE.ensure(cfgmod.load()), daemon=True, name="model-preload").start()


# ---------------------------------------------------------------- health / config
@app.get("/api/health")
def health():
    m = jobs.manager()
    return {"ok": True, "image_model": engine.IMAGE.status(), "queued": m.q.qsize(),
            "running": any(j["status"] == "running" for j in m.jobs.values())}


@app.get("/api/categories")
def categories():
    return {"groups": CATEGORY_GROUPS, "display": DISPLAY, "labels": LABELS, "system_labels": SYSTEM_LABELS,
            "accepted_formats": convert.ACCEPT_TEXT, "extensions": sorted(convert.SUPPORTED)}


@app.get("/api/config")
def get_config():
    return cfgmod.load_editable()


@app.put("/api/config")
def put_config(body: dict = Body(...)):
    try:
        vals = cfgmod.save(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    log.info("configuration saved: %s", vals)
    return vals


# ---------------------------------------------------------------- output folder: Browse only, last folder remembered
def check_folder(p: str):
    path = Path(p).expanduser()
    try:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"; probe.write_text("ok"); probe.unlink()
    except Exception as e:
        return {"ok": False, "path": str(path), "message": f"Cannot write to this folder: {e}"}
    return {"ok": True, "path": str(path.resolve()), "message": "Folder is ready." if existed else "Folder did not exist, so it was created."}


def remember_folder(p: str):
    try:
        LAST_FOLDER_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_FOLDER_FILE.write_text(json.dumps({"path": p}), encoding="utf-8")
    except Exception as e:
        log.warning("could not remember the output folder: %s", e)


@app.get("/api/last-folder")
def last_folder():
    try:
        return {"path": json.loads(LAST_FOLDER_FILE.read_text(encoding="utf-8")).get("path", "")}
    except Exception:
        return {"path": ""}


_PICKER = r'''
import sys
try:
    import tkinter as tk
    from tkinter import filedialog
except Exception as e:
    print("ERR:the folder picker needs tkinter, which is not available (" + str(e) + ")"); sys.exit(0)
try:
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    kw = {"title": "Choose the output folder", "parent": root}
    if sys.argv[1]:
        kw["initialdir"] = sys.argv[1]
    p = filedialog.askdirectory(**kw)
    root.destroy(); print("OK:" + (p or ""))
except Exception as e:
    print("ERR:" + str(e))
'''


@app.post("/api/browse-folder")
def browse_folder():
    """Opens the normal folder-picker window ON THIS COMPUTER (the app runs locally), then checks the folder."""
    initial = last_folder()["path"]
    initial = initial if initial and os.path.isdir(initial) else ""
    try:
        r = subprocess.run([sys.executable, "-c", _PICKER, initial], capture_output=True, text=True, timeout=900)
    except Exception as e:
        return {"ok": False, "path": None, "message": f"Could not open the folder picker: {e}"}
    out = (r.stdout or "").strip().splitlines()
    line = out[-1] if out else ""
    if not line.startswith("OK:"):
        return {"ok": False, "path": None, "message": line[4:] or (r.stderr or "").strip()[-200:] or "The folder picker could not be opened."}
    chosen = line[3:].strip()
    if not chosen:
        return {"ok": False, "path": None, "message": "No folder selected."}
    res = check_folder(os.path.normpath(chosen))
    if res["ok"]:
        remember_folder(res["path"])
    return {"ok": res["ok"], "path": res["path"] if res["ok"] else None, "message": res["message"]}


# ---------------------------------------------------------------- jobs (one file per upload)
@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...), output_dir: Optional[str] = Form(None)):
    out = (output_dir or "").strip()
    if not out:
        raise HTTPException(400, "Choose an output folder first.")
    res = check_folder(out)
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    name = Path(file.filename or "").name
    kind = convert.kind_of(name)
    if kind is None:
        raise HTTPException(400, f"'{name}' is not an accepted file. Accepted formats: {convert.ACCEPT_TEXT}.")
    dest = jobs.UPLOADS / f"{int(time.time() * 1000)}_{name}"
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    try:
        if not convert.signature_ok(dest, Path(name).suffix):
            raise convert.ConvertError(f"'{name}' does not look like a valid {Path(name).suffix.upper().lstrip('.')} file.")
        protected = convert.needs_password(dest, kind)
    except convert.ConvertError as e:
        dest.unlink(missing_ok=True); raise HTTPException(400, str(e))
    remember_folder(res["path"])
    job = jobs.manager().submit(name, dest, res["path"], kind, protected)
    return {"id": job["id"], "filename": job["filename"], "status": job["status"]}


@app.post("/api/jobs/{jid}/password")
def job_password(jid: str, body: dict = Body(...)):
    try:
        job = jobs.manager().unlock_job(jid, str(body.get("password", "")))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return jobs.manager()._summary(job)


@app.post("/api/jobs/{jid}/skip")
def job_skip(jid: str):
    try:
        job = jobs.manager().skip_job(jid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return jobs.manager()._summary(job)


@app.get("/api/jobs")
def list_jobs():
    return jobs.manager().list()


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    j = jobs.manager().get(jid)
    if j is None:
        raise HTTPException(404, "Job not found")
    return {k: v for k, v in j.items() if k != "unlocked_path"}


@app.get("/api/jobs/{jid}/report")
def job_report(jid: str):
    j = jobs.manager().get(jid)
    if not j or not j.get("json_report") or not Path(j["json_report"]).exists():
        raise HTTPException(404, "JSON report not available yet")
    return FileResponse(j["json_report"], filename=Path(j["json_report"]).name, media_type="application/json")


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
