"""Section-aware text chunking for RAG ingestion.

Reads Markdown files from textbook_txt/, splits them into chunks using
RecursiveCharacterTextSplitter, and exports as JSONL to textbook_chunks/.
Each chunk includes metadata: source_file, page_number, class, chapter.

Usage::

    python scripts/chunk_text.py
"""
import glob
import json
import os
import re

# Try to import the MarkdownNodeParser from llama-index
try:
    from llama_index.core.node_parser import MarkdownNodeParser
    from llama_index.core import Document
except Exception:
    MarkdownNodeParser = None


def extract_metadata_from_filename(filename: str) -> dict:
    """Extract class, chapter, page_range from filename like 'Amar_Choupashor_Paribesh_Class_III_Assamese_pages_1_5.md'."""
    # Match: (source_base)_pages_(start)_(end).md
    match = re.search(r'(.*)_pages_(\d+)_(\d+)\.md', filename)
    if match:
        source_base = match.group(1)
        start_page = int(match.group(2))
        end_page = int(match.group(3))
        page_number = f"{start_page}-{end_page}"
        # Extract class from source_base, e.g., Class_III -> III
        class_match = re.search(r'Class_([IVXLCDM]+)', source_base)
        class_num = class_match.group(1) if class_match else "unknown"
        source_file = source_base + '.pdf'
        return {
            "class": class_num,
            "page_number": page_number,
            "source_file": source_file
        }
    return {"class": "unknown", "page_number": "unknown", "source_file": filename}


def chunk_text(input_dir: str = "textbook_txt",
               output_dir: str = "textbook_chunks",
               chunk_size: int = 1000,
               overlap: int = 150):
    os.makedirs(output_dir, exist_ok=True)

    if MarkdownNodeParser is None:
        raise RuntimeError("llama-index-core is required for Markdown chunking")

    parser = MarkdownNodeParser()

    for path in glob.glob(os.path.join(input_dir, "*.md")):
        basename = os.path.basename(path)
        metadata = extract_metadata_from_filename(basename)
        out_path = os.path.join(output_dir, basename.replace('.md', '.jsonl'))

        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()

        doc = Document(text=text)
        nodes = parser.get_nodes_from_documents([doc])

        with open(out_path, 'w', encoding='utf-8') as outf:
            for i, node in enumerate(nodes):
                # LlamaIndex's MarkdownNodeParser automatically extracts header context!
                header_path = " > ".join([v for k, v in node.metadata.items() if k.startswith("Header")])
                chapter = header_path if header_path else "unknown"
                
                record = {
                    "text": node.text,
                    "meta": {
                        **metadata,
                        "chapter": chapter,
                        "chunk_index": i
                    }
                }
                outf.write(json.dumps(record, ensure_ascii=False) + '\n')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chunk cleaned markdown into JSONL chunks")
    parser.add_argument("--input-dir", default="textbook_txt", help="Directory containing markdown files to chunk")
    parser.add_argument("--output-dir", default="textbook_chunks", help="Directory to write JSONL chunk files")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Maximum characters per chunk")
    parser.add_argument("--overlap", type=int, default=150, help="Overlap between chunks in characters")
    args = parser.parse_args()

    chunk_text(input_dir=args.input_dir, output_dir=args.output_dir, chunk_size=args.chunk_size, overlap=args.overlap)