"""Batch OCR script for split PDF files.

Reads every ``*.pdf`` in ``data/split_pdfs`` and sends the file bytes to the
Sarvam-Vision OCR endpoint via :class:`src.provider_clients.SarvamClient`.
The returned text is written to ``textbook_txt/`` using the same base name
with ``.md`` extension.

A small delay is included after each request to avoid rate‑limit issues.  The
script is intentionally simple; more advanced error handling or page-level
logic can be added once the core pipeline is working.

Usage::

    python scripts/batch_ocr.py
"""
import glob
import os
import time

from src.provider_clients import SarvamClient


def process_all_splits(split_dir: str = "data/split_pdfs",
                       output_dir: str = "textbook_txt",
                       pause_sec: float = 10.0):
    os.makedirs(output_dir, exist_ok=True)
    client = SarvamClient()

    for pdf_path in glob.glob(os.path.join(split_dir, "*.pdf")):
        basename = os.path.splitext(os.path.basename(pdf_path))[0]
        out_path = os.path.join(output_dir, f"{basename}.md")

        print(f"OCR-ing {pdf_path} -> {out_path}")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        try:
            text = client.get_ocr(pdf_path)
        except Exception as e:
            print(f"Error OCR-ing {pdf_path}: {e}")
            continue

        with open(out_path, "w", encoding="utf-8") as outf:
            outf.write(text)

        time.sleep(pause_sec)


if __name__ == "__main__":
    process_all_splits()
