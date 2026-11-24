"""Accepted upload formats -> PDF. PDF is used as is; PNG/JPG/TIFF/DOCX are converted, then the normal flow runs.
Password handling (PDF and Word): the password is used ONLY inside unlock() and is never stored or logged."""
import logging
import os
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

log = logging.getLogger("docapp.convert")

SUPPORTED = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image", ".tif": "image", ".tiff": "image", ".docx": "docx"}
ACCEPT_TEXT = "PDF, PNG, JPG, TIFF or DOCX"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"      # password-protected Word files are stored like this


class ConvertError(Exception):
    """A readable problem with the uploaded file (shown to the user)."""


def kind_of(filename):
    return SUPPORTED.get(Path(filename).suffix.lower())


def signature_ok(path, ext):
    with open(path, "rb") as f:
        head = f.read(16)
    ext = ext.lower()
    if ext == ".pdf":
        return head.startswith(b"%PDF-")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext in (".tif", ".tiff"):
        return head[:4] in (b"II*\x00", b"MM\x00*")
    if ext == ".docx":
        return head.startswith(b"PK") or head.startswith(OLE_MAGIC)
    return False


# ------------------------------------------------------------------ password handling
def needs_password(path, kind):
    if kind == "pdf":
        try:
            d = pymupdf.open(path)
        except Exception as e:
            raise ConvertError(f"This PDF cannot be opened: {e}")
        try:
            return bool(d.needs_pass)
        finally:
            d.close()
    if kind == "docx":
        try:
            import msoffcrypto
            with open(path, "rb") as f:
                return bool(msoffcrypto.OfficeFile(f).is_encrypted())
        except Exception:
            return False
    return False                                        # images cannot carry a password


def unlock(path, kind, password, out_path):
    """Write an UNPROTECTED copy to out_path. Returns True, or False when the password is wrong."""
    if kind == "pdf":
        d = pymupdf.open(path)
        try:
            if not d.authenticate(password):
                return False
            d.save(out_path, encryption=pymupdf.PDF_ENCRYPT_NONE)
            return True
        finally:
            d.close()
    if kind == "docx":
        import msoffcrypto
        from msoffcrypto.exceptions import InvalidKeyError
        try:
            with open(path, "rb") as f:
                office = msoffcrypto.OfficeFile(f)
                office.load_key(password=password)
                with open(out_path, "wb") as o:
                    office.decrypt(o)
            return True
        except InvalidKeyError:
            Path(out_path).unlink(missing_ok=True)
            return False
        except Exception as e:
            Path(out_path).unlink(missing_ok=True)
            raise ConvertError(f"This Word file cannot be unlocked: {e}")
    raise ConvertError("This file type has no password protection.")


# ------------------------------------------------------------------ conversion to PDF
def _save_converted(src_doc, out_pdf):
    pdf = pymupdf.open("pdf", src_doc.convert_to_pdf())
    try:
        if pdf.page_count == 0:
            raise ValueError("no pages were produced")
        pdf.save(out_pdf)
    finally:
        pdf.close()


def _word_to_pdf(docx_path, out_pdf):
    """Fallback: Microsoft Word installed on this PC (via the docx2pdf package)."""
    if sys.platform not in ("win32", "darwin"):
        raise RuntimeError("Microsoft Word is only available on Windows or Mac")
    try:
        from docx2pdf import convert
    except ImportError:
        raise RuntimeError("the docx2pdf package is not installed (run setup.bat again)")
    com = None
    if sys.platform == "win32":
        try:
            import pythoncom
            pythoncom.CoInitialize(); com = pythoncom
        except ImportError:
            pass
    try:
        convert(str(docx_path), str(out_pdf))
    finally:
        if com:
            com.CoUninitialize()
    if not Path(out_pdf).exists():
        raise RuntimeError("Microsoft Word did not produce a PDF")


def to_pdf(path, kind, out_pdf):
    """Returns (pdf_path, info). info = {"converted": bool, "converted_with": str|None}."""
    path, out_pdf = Path(path), Path(out_pdf)
    if kind == "pdf":
        try:
            d = pymupdf.open(path)
        except Exception as e:
            raise ConvertError(f"This PDF cannot be opened: {e}")
        try:
            if d.needs_pass:
                raise ConvertError("This PDF is password protected.")
            if d.page_count == 0:
                raise ConvertError("This PDF has no pages.")
        finally:
            d.close()
        return path, {"converted": False, "converted_with": None}
    if kind == "image":
        try:
            src = pymupdf.open(path)
            try:
                _save_converted(src, out_pdf)
            finally:
                src.close()
        except Exception as e:
            raise ConvertError(f"This image cannot be converted to PDF: {e}")
        return out_pdf, {"converted": True, "converted_with": "built-in"}
    if kind == "docx":
        built_in_err = None
        try:
            src = pymupdf.open(path)
            try:
                _save_converted(src, out_pdf)
            finally:
                src.close()
            return out_pdf, {"converted": True, "converted_with": "built-in"}
        except Exception as e:
            built_in_err = e
            log.warning("built-in Word conversion failed (%s); trying Microsoft Word", e)
            Path(out_pdf).unlink(missing_ok=True)
        try:
            _word_to_pdf(path, out_pdf)
            return out_pdf, {"converted": True, "converted_with": "Microsoft Word"}
        except Exception as e:
            raise ConvertError(f"This Word file could not be converted to PDF. Built-in converter: {built_in_err}. Microsoft Word: {e}.")
    raise ConvertError(f"Unsupported file type. Accepted: {ACCEPT_TEXT}.")
