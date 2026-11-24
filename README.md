# Document Page Classifier (free, local, no API key)

Upload ONE file -> every page is classified -> pages are split into folders by document type.

## Accepted files (one per upload)
PDF, PNG, JPG/JPEG, TIFF/TIF (multi-page works) and DOCX. Everything except PDF is converted to PDF first, then the normal flow runs.
- DOCX: built-in converter first; if that fails, Microsoft Word installed on the PC is used (via `docx2pdf`). LibreOffice is not used.
- Password-protected PDF or Word file: the page asks for the password (**Enter password** / **Skip this file**). 3 tries; after 3 wrong
  passwords the file is marked `failed: wrong password` and you can upload it again. Saved PDFs are unprotected. The password is used only
  to unlock the file in memory and is never saved or logged. (Image files cannot have a password.)
- Output folder: choose it with the **Browse** button (typing is not possible). The last folder is remembered and shown next time.

## Run (Windows, Python 3.9+)
1. Double-click **setup.bat** (once; creates `venv`, installs packages, downloads the Nutrient v1 model, ~2.2 GB).
   `setup.bat nomodel` skips the model download (OCR keyword rules only).
2. Double-click **start.bat** (default port 8033, one port for page and backend; to use another: `start.bat 9000`). The browser opens at http://127.0.0.1:8033.

Logs are created automatically in `logs/`: `setup.log`, `start.log`, `app.log`.

## Output
```
<output folder>/
    <pdf name>.json                     ONE document-wise JSON report (no .txt files are created)
    <pdf name>/
        aadhaar/aadhaar_document.pdf    all Aadhaar pages, in original order
        pan/pan_document.pdf
        invoice/invoice_document.pdf  ...
        blank_pages/  unknown/  errors/
```
`split_mode = by_group` makes one PDF per run of consecutive pages (`aadhaar_document_1.pdf`, `_2.pdf`, ...).

JSON layout: `file`, `total_pages`, `total_documents`, `pages_per_type`, `output_folder`, then `documents[]`. Each document
(a run of consecutive pages of one type) has `document_type`, `pages`, `page_range`, `evidence_score_avg/min`, `needs_review`,
`output_file` and `page_details[]` (evidence score, status, matched keywords, OCR text). Turn the OCR text off in Configuration
(`json_include_ocr_text`) for smaller files.

## Document types
Financial: Invoice, Credit Note, Debit Note, Receipt | Procurement: Purchase Order, Quotation, Vendor Agreement |
Identity: Aadhaar, PAN, Passport, Driving Licence | Banking: Bank Statement, Cancelled Cheque |
Logistics: Delivery Challan, E-Way Bill, Lorry Receipt | Supporting: Address Proof, Payment Proof, Declaration, Others
+ system labels BLANK_PAGE, UNKNOWN, ERROR.

## How a page is decided
1. RapidOCR reads the page (retries with lighting correction if it reads nothing on an inky page).
2. **Blank rule**: fewer than `min_chars` characters (and almost no ink) -> BLANK_PAGE.
3. Weighted whole-word keywords (after removing "Not a tax invoice"-type phrases).
4. Optional Nutrient v1 image model (zero-shot, Apache-2.0, local). Fusion: 0.40 image + 0.60 OCR evidence.
5. **No keyword matched -> UNKNOWN** (the image model alone never decides). Evidence score below UNKNOWN_THRESHOLD (0.35) -> UNKNOWN.
6. Two types within the review margin -> REVIEW REQUIRED.
If the image model is off or cannot load, the OCR evidence gets the full weight automatically.

## Configuration page
Only four values can be changed (saved to `config.json`, applied to the next job):
```
IMAGE_WEIGHT      = 0.40   how much the image model counts
OCR_WEIGHT        = 0.60   how much the OCR keywords count
UNKNOWN_THRESHOLD = 0.35   best score below this -> UNKNOWN
REVIEW_MARGIN     = 0.08   top two types closer than this -> REVIEW REQUIRED
```
All other settings (keywords, folder names, blank rule, split mode, ...) are fixed defaults in the code (`app/config.py`, `app/categories.py`).

## Logs
Stored automatically in the `logs` folder: `setup.log` (setup.bat), `start.log` (start.bat), `app.log` (the application: jobs, pages, errors).

## Notes
- Server listens on 127.0.0.1 only (local use). Output paths are folders on the machine running the app.
- A scanned page with unreadable text is not called blank when it has ink: it ends up UNKNOWN.
- Always test on your own real scans before relying on the results.
