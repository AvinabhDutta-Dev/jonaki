"""Cloud ingestion script for Google Colab.

- Reads all markdown files from `data/cleaned_text/`.
- Uses `BAAI/bge-m3` to compute embeddings.
- Stores embeddings, documents, and metadata into a ChromaDB persistent collection
  located at `./chroma_db`.
- Zips `chroma_db` into `chroma_db.zip` for download.

Notes for Colab:
- Run in a Colab notebook cell as a Python script, or upload this file and run it.
- Installing requirements in Colab:
    !pip install sentence-transformers chromadb

Usage (in Colab):
    python scripts/cloud_ingestion.py --batch-size 64
"""
import glob
import json
import os
import argparse
import shutil
from typing import List

from sentence_transformers import SentenceTransformer
import chromadb


def extract_metadata_from_filename(filename: str) -> dict:
    import re
    match = re.search(r'(.*)_pages_(\d+)_(\d+)\.md', filename)
    if match:
        source_base = match.group(1)
        start_page = int(match.group(2))
        end_page = int(match.group(3))
        page_number = f"{start_page}-{end_page}"
        return {
            "source_file": source_base + '.pdf',
            "page_number": page_number,
        }
    return {"source_file": filename, "page_number": "unknown"}


def load_documents(input_dir: str) -> List[dict]:
    docs = []
    for path in sorted(glob.glob(os.path.join(input_dir, "*.md"))):
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        if not text:
            continue
        basename = os.path.basename(path)
        meta = extract_metadata_from_filename(basename)
        docs.append({
            "text": text,
            "meta": meta,
            "basename": basename
        })
    return docs


def main(input_dir: str = "data/cleaned_text", persist_dir: str = "./chroma_db", batch_size: int = 64):
    os.makedirs(persist_dir, exist_ok=True)

    print("Loading documents...")
    docs = load_documents(input_dir)
    print(f"Found {len(docs)} documents to embed")

    print("Loading sentence-transformers model: paraphrase-multilingual-MiniLM-L12-v2")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    # Initialize Chroma persistent client
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name="jonaki_assamese", metadata={"hnsw:space": "cosine"})

    # Batch encode and insert
    def batch_iter(items, n):
        batch = []
        for item in items:
            batch.append(item)
            if len(batch) >= n:
                yield batch
                batch = []
        if batch:
            yield batch

    for batch in batch_iter(docs, batch_size):
        texts = [b['text'] for b in batch]
        metadatas = [b['meta'] for b in batch]
        ids = []
        for i, b in enumerate(batch):
            # create stable id from basename + index
            chunk_idx = b['meta'].get('chunk_index', i)
            ids.append(f"{b['basename']}::{chunk_idx}")

        print(f"Encoding batch of {len(texts)} documents")
        embeddings = model.encode(texts, show_progress_bar=False)

        print(f"Adding {len(embeddings)} vectors to ChromaDB")
        collection.add(
            ids=ids,
            embeddings=embeddings.tolist() if hasattr(embeddings, 'tolist') else list(embeddings),
            metadatas=metadatas,
            documents=texts,
        )

    # Zip the chroma_db directory
    zip_name = 'chroma_db'
    archive_path = shutil.make_archive(zip_name, 'zip', persist_dir)
    print(f"Created archive: {archive_path}")
    print("Cloud ingestion complete. Download chroma_db.zip from your Colab session.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', default='data/cleaned_text')
    parser.add_argument('--persist-dir', default='./chroma_db')
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--model-name', default='BAAI/bge-m3')
    args = parser.parse_args()

    model = SentenceTransformer(args.model_name)