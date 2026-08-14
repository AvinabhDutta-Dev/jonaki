"""ChromaDB client initialization and utilities.

Provides a simple interface to create or retrieve the persistent collection
for storing embeddings and metadata.
"""
import os
import chromadb


def get_chroma_client(persist_dir: str = None) -> chromadb.PersistentClient:
    """Initialize and return the Chroma PersistentClient."""
    if persist_dir is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(client: chromadb.PersistentClient,
                             name: str = "jonaki_assamese",
                             embedding_function=None) -> chromadb.Collection:
    """Get or create the collection with cosine distance.

    If `embedding_function` is provided, pass it to Chroma so it can be
    used for query-time vectorization to ensure consistency with the
    ingestion embeddings.
    """
    params = {
        "name": name,
        "metadata": {"hnsw:space": "cosine"}
    }
    if embedding_function is not None:
        params["embedding_function"] = embedding_function

    return client.get_or_create_collection(**params)