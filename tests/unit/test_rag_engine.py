"""
Unit Tests — backend/services/rag_engine.py
Tests: model usage verification for embeddings and reranking calls.
No real network calls — Mistral client is inspected via source analysis.
"""
import os
import sys
import inspect
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestRagEngineModelUsage:
    """
    Verify RAGEngine uses the correct Mistral models for each task:
    - Embeddings       → mistral-embed  (×3 call sites)
    - Reranking/CRAG   → ministral-14b-2512 (×3 call sites)
    Never large, small, or nemo — those are reserved for other services.
    """

    def _source(self):
        import backend.services.rag_engine as re_mod
        return inspect.getsource(re_mod)

    def test_embeddings_use_mistral_embed(self):
        src = self._source()
        assert "mistral-embed" in src, (
            "rag_engine must use 'mistral-embed' for embedding generation"
        )

    def test_reranking_uses_ministral_14b(self):
        src = self._source()
        assert "ministral-14b-2512" in src, (
            "rag_engine must use 'ministral-14b-2512' for reranking/CRAG"
        )

    def test_does_not_use_mistral_large(self):
        src = self._source()
        assert "mistral-large-latest" not in src, (
            "rag_engine must not use 'mistral-large-latest' (reserved for resume analysis)"
        )

    def test_does_not_use_mistral_small(self):
        src = self._source()
        assert "mistral-small-latest" not in src, (
            "rag_engine must not use 'mistral-small-latest' (reserved for interview engine)"
        )

    def test_does_not_use_nemo(self):
        src = self._source()
        assert "open-mistral-nemo" not in src, (
            "rag_engine must not use 'open-mistral-nemo' (reserved for AI writing assist)"
        )

    def test_embed_model_string_count(self):
        """mistral-embed should appear at least 3 times (init probe + chunk embed + query embed)."""
        src = self._source()
        count = src.count("mistral-embed")
        assert count >= 3, (
            f"Expected at least 3 uses of 'mistral-embed' in rag_engine, found {count}"
        )

    def test_rerank_model_string_count(self):
        """ministral-14b-2512 should appear at least 3 times (rerank + CRAG + validate)."""
        src = self._source()
        count = src.count("ministral-14b-2512")
        assert count >= 3, (
            f"Expected at least 3 uses of 'ministral-14b-2512' in rag_engine, found {count}"
        )
