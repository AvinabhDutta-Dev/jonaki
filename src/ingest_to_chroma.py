"""Ingest JSONL chunks into ChromaDB using Sarvam embeddings.

This script reads `textbook_chunks/*.jsonl`, batches texts for embeddings,
and inserts them into the `jonaki_assamese` Chroma collection with full
metadata. Each document id preserves source and chunk index to avoid mixing
content across textbooks.

Usage:
    python src/ingest_to_chroma.py --dry-run  # prints actions but does not call APIs
    python src/ingest_to_chroma.py             # performs ingestion
"""
import argparse
import glob
import json
import os
from typing import List

from src.chroma_client import get_chroma_client, get_or_create_collection
from src.provider_clients import SarvamClient, EmbeddingClient


def load_chunks(chunk_dir: str) -> List[dict]:
    records = []
    for path in glob.glob(os.path.join(chunk_dir, "*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                # Ensure metadata contains source_file and page_number
                meta = obj.get("meta", {})
                if "source_file" not in meta:
                    meta["source_file"] = os.path.basename(path).replace('.jsonl', '.pdf')
                if "page_number" not in meta:
                    meta["page_number"] = meta.get("page_number", "unknown")

                records.append({
                    "text": obj.get("text", ""),
                    "meta": meta,
                })
    return records


def batch_iter(iterable, batch_size=32):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def ingest(chunks_dir: str = "textbook_chunks",
           persist_dir: str = None,
           batch_size: int = 32,
           dry_run: bool = False):
    sarvam = SarvamClient()
    embedder = EmbeddingClient()

    client = get_chroma_client(persist_dir)
    # Ensure Chroma knows how to embed queries using the same embedding function
    collection = get_or_create_collection(client, embedding_function=embedder.get_embeddings)

    records = load_chunks(chunks_dir)
    print(f"Loaded {len(records)} chunk records from {chunks_dir}")

    for batch in batch_iter(records, batch_size=batch_size):
        texts = [r["text"] for r in batch]
        metas = [r["meta"] for r in batch]
        ids = []
        for m in metas:
            src = m.get("source_file", "unknown")
            idx = m.get("chunk_index")
            if idx is None:
                # fallback unique id
                import uuid

                uid = uuid.uuid4().hex
                ids.append(f"{src}::{uid}")
            else:
                ids.append(f"{src}::chunk_{idx}")

        if dry_run:
            print("Dry run - would embed and add to Chroma:")
            for i, _id in enumerate(ids):
                print(f" - id={_id}, source={metas[i].get('source_file')}, page={metas[i].get('page_number')}")
            continue

        # Request embeddings from local sentence-transformers (BAAI/bge-m3)
        embeddings = embedder.get_embeddings(texts)
        if not embeddings or len(embeddings) != len(texts):
            raise RuntimeError("Embedding service returned unexpected result length")

        # Add to chroma collection
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metas,
            documents=texts,
        )
        print(f"Inserted batch of {len(texts)} vectors into Chroma")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest JSONL chunks into ChromaDB")
    parser.add_argument("--chunks-dir", default="textbook_chunks")
    parser.add_argument("--persist-dir", default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ingest(chunks_dir=args.chunks_dir, persist_dir=args.persist_dir, batch_size=args.batch_size, dry_run=args.dry_run)
