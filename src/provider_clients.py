import os
import zipfile
import tempfile
from sarvamai import SarvamAI
from typing import List


class EmbeddingClient:
    """Embedding client using sentence-transformers (BAAI/bge-m3).

    This class lazy-loads the SentenceTransformer model to avoid a heavy
    download at import time. Call `get_embeddings(texts)` to receive a list
    of vectors (list of list[float]).
    """

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self.model = None

    def _ensure_model(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as e:
                raise RuntimeError("sentence-transformers is required for EmbeddingClient") from e
            self.model = SentenceTransformer(self.model_name)

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        self._ensure_model()
        # encode returns numpy array; convert to list of lists
        emb = self.model.encode(texts, show_progress_bar=False)
        try:
            return emb.tolist()
        except Exception:
            # If already a list
            return list(emb)

class RerankerClient:
    """Reranker client using sentence-transformers CrossEncoder (BAAI/bge-reranker-m3)."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self.model = None

    def _ensure_model(self):
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
            except Exception as e:
                raise RuntimeError("sentence-transformers is required for RerankerClient") from e
            self.model = CrossEncoder(self.model_name)

    def rerank(self, query: str, documents: List[str], top_k: int = 3) -> List[str]:
        """Reranks a list of documents against a query and returns the top_k."""
        if not documents:
            return []
        self._ensure_model()
        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs)
        
        # Pair up documents with their scores and sort descending
        doc_scores = list(zip(documents, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return just the top_k documents
        return [doc for doc, score in doc_scores[:top_k]]


class SarvamClient:
    """Unified client for SarvamAI SDK endpoints (OCR, embeddings, LLM).

    This class centralizes authentication and API interactions using the
    official SarvamAI Python SDK. It handles OCR via document intelligence,
    embeddings via the embeddings API, and chat completions for the LLM.

    Usage:
        client = SarvamClient()
        text = client.get_ocr("path/to/file.pdf")
        emb = client.get_embeddings(["some text"])
        resp = client.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(self):
        self.client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

    def get_ocr(self, file_path: str) -> str:
        """Send a file to SarvamAI document intelligence for OCR.

        Creates a job, uploads the file, waits for completion, downloads
        the output ZIP, extracts the markdown content, and returns it.

        Args:
            file_path: Path to the PDF or image file.

        Returns:
            The OCR'd text in markdown format.
        """
        job = self.client.document_intelligence.create_job(
            language="as-IN", output_format="md"
        )
        job.upload_file(file_path)
        job.start()
        job.wait_until_complete()

        # Download to a temporary ZIP file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
            zip_path = tmp_zip.name
        job.download_output(zip_path)

        # Extract markdown from ZIP
        markdown_content = ""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Assume the markdown file is named something like 'output.md'
            for file_name in zip_ref.namelist():
                if file_name.endswith('.md'):
                    with zip_ref.open(file_name) as md_file:
                        markdown_content = md_file.read().decode('utf-8')
                    break

        # Clean up
        os.unlink(zip_path)

        return markdown_content

    def get_embeddings(self, texts: list) -> list:
        """Generate embeddings for a list of strings using Sarvam-2B."""
        response = self.client.embeddings.create(
            model="sarvam-2b",
            inputs=texts
        )
        # Assume response has 'embeddings' key
        return response.get("embeddings", [])

    def chat(self, messages: list) -> dict:
        """Generate chat completions using Sarvam-30B."""
        return self.client.chat.completions(
            model="sarvam-30b",
            messages=messages,
            temperature=0.5
        )

