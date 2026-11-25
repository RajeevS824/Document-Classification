
import os
import re
import time
import fitz
import cv2
import numpy as np

from pathlib import Path
from paddleocr import TextDetection, TextRecognition


# ============================================================
# PP-OCRv6 LARGE HYBRID OCR
# Detection: PP-OCRv6_large_det
# Recognition: PP-OCRv6_large_rec
# Engine: ONNX Runtime
# ============================================================

PADDLE_LARGE_DET = "PP-OCRv6_medium_det"
PADDLE_LARGE_REC = "PP-OCRv6_medium_rec"

INPUT_DIR = Path("result")
OUTPUT_DIR = Path("results")
DPI = 300

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# INITIALIZE DETECTION AND RECOGNITION MODELS
# ============================================================

detector = TextDetection(
    model_name=PADDLE_LARGE_DET,
    engine="onnxruntime"
)

recognizer = TextRecognition(
    model_name=PADDLE_LARGE_REC,
    engine="onnxruntime"
)


# ============================================================
# PDF TO IMAGE
# ============================================================

def pdf_to_images(pdf_path):
    images = []

    document = fitz.open(pdf_path)
    zoom = DPI / 72

    matrix = fitz.Matrix(zoom, zoom)

    for page in document:
        pix = page.get_pixmap(
            matrix=matrix,
            alpha=False
        )

        image = np.frombuffer(
            pix.samples,
            dtype=np.uint8
        ).reshape(
            pix.height,
            pix.width,
            3
        )

        image = cv2.cvtColor(
            image,
            cv2.COLOR_RGB2BGR
        )

        images.append(image)

    document.close()

    return images


# ============================================================
# EXTRACT DETECTION POLYGONS
# ============================================================

def get_detection_polygons(result):

    if hasattr(result, "json"):
        result = result.json

    if callable(result):
        result = result()

    if isinstance(result, dict):
        result = result.get("res", result)
        return result.get("dt_polys", [])

    return []


# ============================================================
# SORT DETECTED TEXT REGIONS
# ============================================================

def sort_boxes(boxes):

    boxes = list(boxes)

    boxes.sort(
        key=lambda box: (
            int(np.min(np.asarray(box)[:, 1]) // 15),
            int(np.min(np.asarray(box)[:, 0]))
        )
    )

    return boxes


# ============================================================
# CROP DETECTED TEXT REGION
# ============================================================

def crop_text_region(image, polygon):

    polygon = np.asarray(
        polygon,
        dtype=np.float32
    )

    x_min = max(0, int(np.min(polygon[:, 0])))
    y_min = max(0, int(np.min(polygon[:, 1])))

    x_max = min(
        image.shape[1],
        int(np.max(polygon[:, 0])) + 1
    )

    y_max = min(
        image.shape[0],
        int(np.max(polygon[:, 1])) + 1
    )

    crop = image[y_min:y_max, x_min:x_max]

    return crop


# ============================================================
# RECOGNIZE ONE TEXT REGION
# ============================================================

def recognize_crop(crop):

    if crop is None or crop.size == 0:
        return ""

    result = recognizer.predict(input=crop)

    if not result:
        return ""

    item = result[0]

    if hasattr(item, "json"):
        item = item.json

    if callable(item):
        item = item()

    if isinstance(item, dict):
        item = item.get("res", item)
        return str(item.get("rec_text", "")).strip()

    return ""


# ============================================================
# PROCESS ONE PAGE
# ============================================================

def process_page(image):

    detection_result = detector.predict(input=image)

    all_text = []

    for result in detection_result:

        boxes = get_detection_polygons(result)
        boxes = sort_boxes(boxes)

        for polygon in boxes:

            crop = crop_text_region(
                image,
                polygon
            )

            text = recognize_crop(crop)

            if text:
                all_text.append(text)

    return "\n".join(all_text)


# ============================================================
# PROCESS ONE PDF
# ============================================================

def process_pdf(pdf_path):

    print(f"\nProcessing: {pdf_path.name}")

    start_time = time.time()

    page_images = pdf_to_images(pdf_path)

    pdf_output_dir = OUTPUT_DIR / pdf_path.stem
    pdf_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    complete_text = []

    for page_number, image in enumerate(
        page_images,
        start=1
    ):

        print(f"Processing page {page_number}...")

        page_text = process_page(image)

        page_file = (
            pdf_output_dir /
            f"page_{page_number:03d}_paddleocr_v6_large_hybrid.txt"
        )

        page_file.write_text(
            page_text,
            encoding="utf-8"
        )

        complete_text.append(
            f"\n--- PAGE {page_number} ---\n{page_text}"
        )

    combined_file = (
        pdf_output_dir /
        "complete_extraction.txt"
    )

    combined_file.write_text(
        "\n".join(complete_text),
        encoding="utf-8"
    )

    elapsed = time.time() - start_time

    print(f"Completed: {pdf_path.name}")
    print(f"Time: {elapsed:.2f} seconds")
    print(f"Output: {pdf_output_dir}")


# ============================================================
# MAIN
# ============================================================

def main():

    pdf_files = sorted(
        INPUT_DIR.glob("*.pdf")
    )

    if not pdf_files:
        print("No PDF files found in the pdfs folder.")
        return

    for pdf_path in pdf_files:

        try:
            process_pdf(pdf_path)

        except Exception as error:
            print(
                f"Error processing {pdf_path.name}: {error}"
            )

    print("\nAll PDF processing completed.")


if __name__ == "__main__":
    main()
