"""
Unit Tests — backend/services/rag_engine.py
Tests: model usage verification for embeddings and CRAG calls.
Architecture: Mistral embed at startup, provider_router.chat_crag for CRAG/guardrails.
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
    Verify RAGEngine uses the correct providers:
    - Embeddings  → mistral-embed via Mistral (startup only)
    - CRAG        → provider_router.chat_crag (Gemini → OpenRouter)
    - Guardrails  → provider_router.chat_crag (Gemini → OpenRouter)
    Must not use ministral-14b-2512 (invalid model) or old direct Mistral chat calls.
    """

    def _source(self):
        import backend.services.rag_engine as re_mod
        return inspect.getsource(re_mod)

    def test_embeddings_use_mistral_embed(self):
        src = self._source()
        assert "mistral-embed" in src, (
            "rag_engine must use 'mistral-embed' for embedding generation"
        )

    def test_uses_chat_crag_for_crag(self):
        src = self._source()
        assert "chat_crag" in src, (
            "rag_engine must use 'chat_crag' from provider_router for CRAG evaluation"
        )

    def test_does_not_use_invalid_ministral_model(self):
        src = self._source()
        assert "ministral-14b-2512" not in src, (
            "ministral-14b-2512 is not a valid model and must not appear in rag_engine"
        )

    def test_does_not_use_mistral_large(self):
        src = self._source()
        assert "mistral-large-latest" not in src, (
            "rag_engine must not use 'mistral-large-latest'"
        )

    def test_does_not_use_nemo(self):
        src = self._source()
        assert "open-mistral-nemo" not in src, (
            "rag_engine must not use 'open-mistral-nemo'"
        )

    def test_embed_model_string_present(self):
        """mistral-embed should appear at least once."""
        src = self._source()
        count = src.count("mistral-embed")
        assert count >= 1, (
            f"Expected at least 1 use of 'mistral-embed' in rag_engine, found {count}"
        )

    def test_keyword_only_method_exists(self):
        """retrieve_keyword_only must exist as a fallback for rate-limited environments."""
        import backend.services.rag_engine as re_mod
        assert hasattr(re_mod.RAGEngine, "retrieve_keyword_only"), (
            "RAGEngine must have retrieve_keyword_only for rate-limit fallback"
        )
