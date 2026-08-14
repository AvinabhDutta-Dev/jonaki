"""Simple sanity check for SarvamClient methods.

This module can be invoked with a dummy API key to ensure that the client
initializes correctly and raises logical errors when the endpoints cannot be
reached.  It is not a comprehensive unit test suite but provides quick
feedback during early development.

Usage::

    set SARVAM_API_KEY=whatever   # PowerShell / cmd
    python -m scripts.test_provider
"""
import os
import sys
import tempfile

from src.provider_clients import SarvamClient


def main():
    try:
        client = SarvamClient()
    except Exception as e:
        print(f"failed to create SarvamClient: {e}")
        sys.exit(1)

    print("client initialized successfully")

    # try calls with dummy data; they will probably fail but we catch errors
    try:
        _ = client.get_embeddings(["hello world"])
        print("embeddings call succeeded (unexpected with test key)")
    except Exception as exc:
        print(f"embeddings call raised as expected: {exc}")

    try:
        # Create a dummy file for OCR test
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"dummy pdf content")
            dummy_path = tmp.name
        _ = client.get_ocr(dummy_path)
        os.unlink(dummy_path)
        print("ocr call succeeded (unexpected with test key)")
    except Exception as exc:
        print(f"ocr call raised as expected: {exc}")

    try:
        _ = client.chat([{"role": "user", "content": "test"}])
        print("chat call succeeded (unexpected with test key)")
    except Exception as exc:
        print(f"chat call raised as expected: {exc}")


if __name__ == "__main__":
    main()
