"""Utility to split all PDFs in data/pdfs/ into smaller chunks (e.g. 5 pages each).

For each PDF in data/pdfs/, this script splits it into smaller files of a
specified number of pages and saves them to data/split_pdfs/ with names
like "Amar_Choupashor_Paribesh_Class_III_Assamese_pages_1_5.pdf".

This enables batch OCR processing without hitting file size limits.

Example usage::

    python scripts/split_pdf.py --pages-per-file 5
"""
import argparse
import os
import fitz


def split_all_pdfs(input_dir: str = "data/pdfs",
                   output_dir: str = "data/split_pdfs",
                   pages_per_file: int = 5):
    os.makedirs(output_dir, exist_ok=True)

    for pdf_file in os.listdir(input_dir):
        if not pdf_file.endswith('.pdf'):
            continue
        input_path = os.path.join(input_dir, pdf_file)
        basename = os.path.splitext(pdf_file)[0]

        doc = fitz.open(input_path)
        total_pages = doc.page_count

        for start in range(0, total_pages, pages_per_file):
            end = min(start + pages_per_file, total_pages)
            new_doc = fitz.open()
            for p in range(start, end):
                new_doc.insert_pdf(doc, from_page=p, to_page=p)
            out_name = f"{basename}_pages_{start+1}_{end}.pdf"
            out_path = os.path.join(output_dir, out_name)
            new_doc.save(out_path)
            print(f"Created split file: {out_path}")
            new_doc.close()
        doc.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split all PDFs in data/pdfs into smaller files.")
    parser.add_argument(
        "--input-dir",
        default="data/pdfs",
        help="Directory containing source PDFs",
    )
    parser.add_argument(
        "--output-dir",
        default="data/split_pdfs",
        help="Directory to write split PDFs",
    )
    parser.add_argument(
        "--pages-per-file",
        type=int,
        default=5,
        help="Number of pages to include in each split file",
    )
    args = parser.parse_args()
    split_all_pdfs(args.input_dir, args.output_dir, args.pages_per_file)
