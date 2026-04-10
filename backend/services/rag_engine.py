import os
import time
import json
import numpy as np
import re
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
    Advanced Lightweight RAG Engine using Mistral SDK directly.
    Implements:
    1. Hybrid Search (Vector Cosine Similarity + Keyword Frequency)
    2. Reranking (using mistral-rerank-latest)
    3. Corrective RAG (CRAG) (Evaluation + Filtering)
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

        print("Initializing Advanced Lightweight RAG Engine...")
        
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
            print(f"Advanced Lightweight RAG Engine ready with {len(self.chunks)} chunks.")

        except Exception as e:
            print(f"Error during Advanced Lightweight RAG initialization: {e}")

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def _get_keyword_score(self, query: str, chunk: str) -> float:
        """Simple keyword matching score (frequency-based)."""
        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return 0.0
        
        chunk_words = re.findall(r'\w+', chunk.lower())
        count = sum(1 for w in chunk_words if w in query_words)
        return count / len(chunk_words) if chunk_words else 0.0

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieves relevant chunks using Hybrid Search (Vector + Keyword) 
        followed by Reranking with Mistral.
        """
        self._ensure_initialized()
        if not self.chunks or not self.embeddings or not self.mistral_client:
            return []
            
        cache_key = f"rag_retrieve_v2_{query}_{top_k}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            # 1. Hybrid Search: Get Vector Similarity + Keyword Score
            # Get query embedding
            resp = self.mistral_client.embeddings.create(
                model="mistral-embed",
                inputs=[query]
            )
            query_emb = np.array(resp.data[0].embedding)
            
            hybrid_scores = []
            for i, emb in enumerate(self.embeddings):
                # Vector Score (Cosine Similarity)
                v_score = np.dot(query_emb, np.array(emb))
                
                # Keyword Score
                k_score = self._get_keyword_score(query, self.chunks[i])
                
                # Combined Score (Weighting: 0.7 Vector, 0.3 Keyword)
                combined = (0.7 * v_score) + (0.3 * k_score)
                hybrid_scores.append(combined)
            
            # Get top 10 candidates for reranking
            top_candidates_idx = np.argsort(hybrid_scores)[-10:][::-1]
            candidates = [self.chunks[i] for i in top_candidates_idx]
            
            if not candidates:
                return []

            # 2. Reranking: Use Mistral Rerank API
            try:
                rerank_resp = self.mistral_client.rerank.rerank(
                    model="mistral-rerank-latest",
                    query=query,
                    documents=candidates,
                    top_n=top_k
                )
                
                # Extract reranked results in order
                results = []
                for hit in rerank_resp.data:
                    results.append(candidates[hit.index])
                
                # Cache results for 1 hour
                cache.set(cache_key, results, expire=3600)
                return results
            except Exception as e:
                print(f"Reranking error (falling back to hybrid search results): {e}")
                results = candidates[:top_k]
                cache.set(cache_key, results, expire=3600)
                return results

        except Exception as e:
            print(f"Error during RAG retrieval: {e}")
            return []

    def retrieve_with_correction(self, query: str, top_k: int = 3) -> List[str]:
        """
        Corrective RAG (CRAG) Pattern:
        1. Retrieve top candidates (Hybrid + Reranking).
        2. Evaluate each document for relevance using a quick LLM check.
        3. Filter out irrelevant chunks to improve generation accuracy.
        """
        # Step 1: Retrieval
        retrieved_docs = self.retrieve(query, top_k=top_k)
        if not retrieved_docs:
            return []

        # Step 2: Evaluation (Corrective Step)
        verified_docs = []
        try:
            # Prepare evaluation prompt for a batch of documents
            docs_summary = "\n\n".join([f"DOC {i+1}: {doc[:400]}..." for i, doc in enumerate(retrieved_docs)])
            
            prompt = (
                f"Evaluate if the following documents are relevant to the query: '{query}'.\n\n"
                f"Documents:\n{docs_summary}\n\n"
                "Return only a JSON object with a 'relevance' key containing a list of booleans (true if relevant, false otherwise). "
                "Example: {'relevance': [true, false, true]}"
            )
            
            # Use mistral-small-latest for fast, cheap evaluation
            eval_resp = self.mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            relevance_data = json.loads(eval_resp.choices[0].message.content)
            relevance_list = relevance_data.get("relevance", [])
            
            for i, is_relevant in enumerate(relevance_list):
                if is_relevant and i < len(retrieved_docs):
                    verified_docs.append(retrieved_docs[i])
            
            # Fallback if evaluation fails or filters everything
            if not verified_docs:
                verified_docs = retrieved_docs[:1] # Keep at least the best one
                
        except Exception as e:
            print(f"CRAG Evaluation Error: {e}")
            verified_docs = retrieved_docs
            
        return verified_docs

# Global singleton instance
rag_engine = RAGEngine()
