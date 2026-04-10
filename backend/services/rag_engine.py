import os
import time
import json
import numpy as np
from typing import List, Dict, Any
try:
    from mistralai import Mistral
except (ImportError, AttributeError):
    try:
        from mistralai.client import Mistral
    except ImportError:
        from mistralai.client import MistralClient as Mistral

from ..core.config import MISTRAL_API_KEY
from .cache_manager import cache

class RAGEngine:
    """
    Lightweight RAG Engine using Mistral SDK directly.
    Eliminates LlamaIndex dependency for maximum speed and deployment stability.
    """
    def __init__(self, docs_dir: str = "backend/data/rag_docs"):
        self.docs_dir = docs_dir
        self.chunks = []
        self.embeddings = []
        self._initialized = False
        self.mistral_client = None

    def initialize(self):
        """Initializes the RAG Engine with Mistral SDK directly."""
        if self._initialized:
            return

        if not MISTRAL_API_KEY:
            print("Warning: MISTRAL_API_KEY not found. RAG Engine will not be initialized.")
            return

        print("Initializing Lightweight RAG Engine...")
        
        try:
            # Initialize Mistral SDK client
            self.mistral_client = Mistral(api_key=MISTRAL_API_KEY)

            if not os.path.exists(self.docs_dir):
                print(f"Warning: RAG docs directory not found at {self.docs_dir}")
                return

            # Load and chunk documents
            all_text = ""
            for filename in os.listdir(self.docs_dir):
                if filename.endswith(".txt"):
                    with open(os.path.join(self.docs_dir, filename), "r", encoding="utf-8") as f:
                        all_text += f.read() + "\n\n"

            if not all_text.strip():
                print(f"Warning: No text found in {self.docs_dir}")
                return

            # Simple chunking by paragraph/section
            self.chunks = [p.strip() for p in all_text.split("\n\n") if len(p.strip()) > 50]
            
            if not self.chunks:
                print("Warning: No valid chunks found for RAG.")
                return

            # Batch embed chunks
            print(f"Embedding {len(self.chunks)} chunks...")
            # Mistral allows batch embeddings
            resp = self.mistral_client.embeddings.create(
                model="mistral-embed",
                inputs=self.chunks
            )
            self.embeddings = [e.embedding for e in resp.data]
            
            self._initialized = True
            print(f"Lightweight RAG Engine ready with {len(self.chunks)} chunks.")

        except Exception as e:
            print(f"Error during Lightweight RAG initialization: {e}")

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieves relevant document chunks using cosine similarity on Mistral embeddings."""
        self._ensure_initialized()
        if not self.chunks or not self.embeddings or not self.mistral_client:
            return []
            
        cache_key = f"rag_retrieve_{query}_{top_k}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            # Get query embedding
            resp = self.mistral_client.embeddings.create(
                model="mistral-embed",
                inputs=[query]
            )
            query_emb = np.array(resp.data[0].embedding)
            
            # Calculate cosine similarities
            similarities = []
            for emb in self.embeddings:
                emb_arr = np.array(emb)
                # Cosine similarity = (A dot B) / (||A|| * ||B||)
                # Mistral embeddings are usually normalized, so simple dot product works
                sim = np.dot(query_emb, emb_arr)
                similarities.append(sim)
            
            # Sort by similarity
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            results = [self.chunks[i] for i in top_indices]
            
            # Cache results for 1 hour
            cache.set(cache_key, results, expire=3600)
            return results

        except Exception as e:
            print(f"Error during RAG retrieval: {e}")
            return []

    def retrieve_with_correction(self, query: str, top_k: int = 3) -> List[str]:
        """Simple version of retrieve_with_correction for backward compatibility."""
        return self.retrieve(query, top_k=top_k)

# Global singleton instance
rag_engine = RAGEngine()
