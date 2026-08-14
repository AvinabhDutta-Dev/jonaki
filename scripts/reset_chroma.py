"""Script to reset/clear the ChromaDB collection.

Deletes the existing 'jonaki_assamese' collection to allow fresh ingestion
of new data (e.g., switching from Class 9 to Classes 3/4).

Usage::

    python scripts/reset_chroma.py
"""
import os
import chromadb


def reset_chroma(persist_dir: str = None):
    if persist_dir is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    client = chromadb.PersistentClient(path=persist_dir)

    try:
        client.delete_collection("jonaki_assamese")
        print("Collection 'jonaki_assamese' deleted successfully.")
    except Exception as e:
        print(f"Error deleting collection: {e}")


if __name__ == "__main__":
    reset_chroma()