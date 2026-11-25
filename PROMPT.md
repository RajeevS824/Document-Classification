# Prompt: build the Document Page Classifier

Build a complete, runnable, FREE, local (no paid API, no LLM) web application that classifies every page of ONE uploaded file (PDF, PNG, JPG, TIFF or DOCX)
and splits the pages into folders by document type. Stack: Python 3.9+, FastAPI backend, single-file vanilla HTML/JS frontend
(no Node build), Windows .bat launchers.

## Input files
One file per upload: PDF, PNG, JPG/JPEG, TIFF/TIF (multi-page) or DOCX. Convert everything except PDF to PDF first (PyMuPDF; DOCX: built-in
converter first, then Microsoft Word via docx2pdf if the built-in one fails; no LibreOffice), then run the normal flow. For a password-protected
PDF or Word file (msoffcrypto-tool) the page asks for the password with "Enter password" and "Skip this file"; allow 3 tries, then mark the file
"failed: wrong password"; saved split PDFs are unprotected; never store or log the password. Output folder: Browse button only (native folder
dialog opened by the local backend), validated after choosing, last folder remembered. Default port 8033 (page and backend on one port).

## Document types (labels)
Financial: invoice, credit_note, debit_note, receipt. Procurement: purchase_order, quotation, vendor_agreement.
Identity: aadhaar, pan, passport, driving_licence. Banking: bank_statement, cancelled_cheque.
Logistics: delivery_challan, eway_bill, lorry_receipt. Supporting: address_proof, payment_proof, declaration, others.
System labels: BLANK_PAGE, UNKNOWN, ERROR.

## Classification pipeline (per page, page-by-page)
1. Render PDF page with PyMuPDF at 300 DPI. OCR with PP-OCRv6 medium detection and recognition models through ONNX Runtime. If OCR returns almost nothing but the page
   has ink, retry once after illumination normalisation.
2. Blank rule: if OCR finds fewer than N characters (default 10) AND the page has almost no ink -> BLANK_PAGE.
3. Normalise text (lower case, remove apostrophes, strip punctuation). Remove "ignore phrases" (regex, default
   "not a(n) (tax) invoice") BEFORE matching.
4. Weighted keyword evidence per type: whole-word matching (so "pay" does not match "payment"), evidence = min(sum(weights)/scale, 1).
   Include sensible default keywords for all types (India-specific wording: GSTIN, IFSC, UIDAI, Income Tax Department, "mini statement",
   "delivery note", ...). Classification only: do NOT validate document numbers (no PAN/Aadhaar/IFSC/passport/licence format or checksum checks).
5. Optional image model: Nutrient Document Classification v1 (Hugging Face `nutrientdocs/document-classification-v1`, Apache-2.0,
   onnxruntime, zero-shot with one text prompt per label incl. "a blank empty white page"). Run on GPU only if onnxruntime has the CUDA
   provider. If it cannot load, continue with OCR only (OCR weight becomes 1.0) and show this in the UI.
6. Fusion: final = 0.40*image + 0.60*ocr_evidence. If NO keyword matched for any known type -> UNKNOWN (the image model alone must never
   decide). If best score < UNKNOWN_THRESHOLD (0.35) -> UNKNOWN. If top-2 scores differ by < review margin (0.08) -> REVIEW REQUIRED.
   Use the name "evidence score" (not "confidence/probability").
7. Wrap each page in try/except: a failing page becomes ERROR, the rest of the file continues.

## Output
Frontend asks for an output folder. For each uploaded PDF create `<output>/<pdf name>/` (suffix _2, _3 if it exists unless overwrite is on),
and inside it one folder per detected type containing `<type>_document.pdf` with that type's pages in original order
(aadhaar/aadhaar_document.pdf, pan/pan_document.pdf, ...). Also blank_pages/, unknown/, errors/ folders. Do NOT create any .txt report files.
Write ONE document-wise JSON file directly in the main output folder, named `<pdf name>.json`: file info, total pages/documents, pages per type,
then `documents[]` (one per run of consecutive pages of the same type: type, pages, page range, average/min evidence score, needs_review,
output file, and per-page details incl. matched keywords and optional OCR text, controlled by a config option).
Option: split_mode "by_group" (one PDF per run of consecutive pages).

## Backend API (FastAPI, bound to 127.0.0.1)
GET/PUT /api/config (the 4 values), GET /api/categories, GET /api/health (image-model status), POST /api/validate-path,
POST /api/jobs (multipart files + output_dir), GET /api/jobs, GET /api/jobs/{id}, GET /api/jobs/{id}/report. One background worker processes jobs sequentially with page-level progress.
Validate the config values server-side (0-1) and return readable 400 errors.

## Frontend (3 tabs)
- Process: drag-and-drop PDF upload (multiple), output-folder field with a "Check folder" button, Start button, live progress bars,
  per-page results table (result, evidence score, status, matched keywords), output files list, report download.
- Configuration: ONLY four values, saved to config.json: IMAGE_WEIGHT=0.40, OCR_WEIGHT=0.60, UNKNOWN_THRESHOLD=0.35, REVIEW_MARGIN=0.08.
  Everything else (keywords, folder names, blank rule, split mode, prompts) is a fixed default in code, not shown in the UI.
- There is no jobs-history page and no log viewer in the frontend; logs are only written to the logs folder.

## Windows scripts and logs
- setup.bat: find Python 3.9+, create venv, upgrade pip, install requirements.txt, optionally pre-download the model
  (`setup.bat nomodel` skips it). Write everything with timestamps to logs\setup.log; create the logs folder automatically.
- start.bat [port]: check venv, check the port is free, open the browser after a delay, run uvicorn, log to logs\start.log.
- The app itself logs to logs\app.log (rotating). Create the logs folder automatically if missing.

## Quality bar
Runnable as delivered, no placeholders. Test with a multi-page PDF containing a different document type on each page, a blank page and
an unsupported document. Report honestly which parts were tested and which were not.
