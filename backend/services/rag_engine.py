import os
import time
from typing import List, Dict, Any
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.mistralai import MistralAI
from llama_index.embeddings.mistralai import MistralAIEmbedding
try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral
from ..core.config import MISTRAL_API_KEY
from .cache_manager import cache

class RAGEngine:
    """
    RAG Engine using LlamaIndex with Mistral AI.
    Upgraded to Hybrid-style Retrieval with Mistral Reranking.
    Optimized for low-memory environments by offloading tasks to Mistral's API.
    """
    def __init__(self, docs_dir: str = "backend/data/rag_docs"):
        self.docs_dir = docs_dir
        self.index = None
        self._initialized = False
        self.mistral_client = None

    def initialize(self):
        """Initializes the LlamaIndex with Mistral AI with retry logic."""
        if self._initialized:
            return

        if not MISTRAL_API_KEY:
            print("Warning: MISTRAL_API_KEY not found. RAG Engine will not be initialized.")
            return

        print("Initializing Advanced RAG Engine with Mistral Reranking...")
        
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                # Initialize Mistral SDK client for Reranking
                self.mistral_client = Mistral(api_key=MISTRAL_API_KEY)

                # Configure LlamaIndex to use Mistral for both LLM and Embeddings
                Settings.llm = MistralAI(api_key=MISTRAL_API_KEY, model="mistral-large-latest")
                Settings.embed_model = MistralAIEmbedding(api_key=MISTRAL_API_KEY)
                Settings.chunk_size = 512
                Settings.chunk_overlap = 50

                if not os.path.exists(self.docs_dir):
                    print(f"Warning: RAG docs directory not found at {self.docs_dir}")
                    return

                # Load documents
                documents = SimpleDirectoryReader(self.docs_dir).load_data()
                if not documents:
                    print(f"Warning: No documents found in {self.docs_dir}")
                    return

                # Create index with a single attempt (LlamaIndex handles some internal batching)
                # If this fails with 429, it will be caught by our retry loop
                self.index = VectorStoreIndex.from_documents(documents)
                self._initialized = True
                print(f"Advanced RAG Engine ready with {len(documents)} documents.")
                break

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate_limit" in error_msg.lower() or "capacity_exceeded" in error_msg.lower():
                    print(f"Mistral API Rate Limit (429) hit during initialization (Attempt {attempt + 1}/{max_retries}).")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print("Failed to initialize RAG Engine after multiple attempts due to API limits.")
                        print("Tip: Check your Mistral AI dashboard for service tier capacity.")
                else:
                    print(f"Unexpected error during RAG initialization: {e}")
                    break

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieves relevant document chunks using the index.
        Uses manual caching to avoid pickling errors with class instance (RLock issue).
        """
        self._ensure_initialized()
        if not self.index or not self.mistral_client:
            print("RAG Engine not fully initialized. Returning empty results.")
            return []
            
        # Manual cache key based on query and top_k
        cache_key = f"rag_retrieve_{query}_{top_k}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            # 1. Fetch initial candidates using vector search
            # We fetch more than top_k to allow the reranker to work
            retriever = self.index.as_retriever(similarity_top_k=10)
            nodes = retriever.retrieve(query)
            
            if not nodes:
                return []

            # 2. Rerank using Mistral's API (if available)
            documents = [node.get_content() for node in nodes]
            
            try:
                # Check if rerank is supported by the current client version
                if hasattr(self.mistral_client, 'rerank'):
                    rerank_response = self.mistral_client.rerank.rerank(
                        model="mistral-rerank-latest",
                        query=query,
                        documents=documents,
                        top_n=top_k
                    )
                    
                    results = []
                    for hit in rerank_response.data:
                        results.append(documents[hit.index])
                    
                    # Cache results for 1 hour
                    cache.set(cache_key, results, expire=3600)
                    return results
                else:
                    # Silent fallback to vector results
                    results = documents[:top_k]
                    cache.set(cache_key, results, expire=3600)
                    return results
            except Exception as rerank_err:
                # Silent fallback to vector results if reranker fails
                results = documents[:top_k]
                cache.set(cache_key, results, expire=3600)
                return results

        except Exception as e:
            print(f"Error during RAG retrieval: {e}")
            return []

    def retrieve_with_correction(self, query: str, top_k: int = 3) -> List[str]:
        """
        Implements Corrective RAG (CRAG) logic:
        1. Retrieve documents (Hybrid Search + Reranking).
        2. Evaluate relevance using a lightweight LLM check.
        3. Filter out irrelevant documents to prevent hallucinations.
        """
        # Step 1: Standard Retrieval
        retrieved_docs = self.retrieve(query, top_k=top_k)
        if not retrieved_docs:
            return []
            
        # Step 2: Corrective Evaluation (Lightweight Check)
        verified_docs = []
        try:
            # Prepare a batch prompt to check all docs at once
            docs_text = "\n\n".join([f"Document {i+1}: {doc[:300]}..." for i, doc in enumerate(retrieved_docs)])
            
            prompt = (
                f"Query: {query}\n\n"
                f"Documents:\n{docs_text}\n\n"
                "Task: Evaluate if each document is relevant to the query. "
                "Return strictly a JSON list of booleans (true/false) corresponding to the document order. "
                "Example: [true, false, true]"
            )
            
            client = Mistral(api_key=MISTRAL_API_KEY)
            resp = client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            import json
            relevance_list = json.loads(resp.choices[0].message.content)
            
            if isinstance(relevance_list, list):
                for i, is_relevant in enumerate(relevance_list):
                    if is_relevant and i < len(retrieved_docs):
                        verified_docs.append(retrieved_docs[i])
            else:
                # Fallback if AI response format is wrong
                verified_docs = retrieved_docs
        except Exception as e:
            print(f"CRAG Evaluation Error: {e}")
            verified_docs = retrieved_docs
            
        return verified_docs

# Global singleton instance
rag_engine = RAGEngine()
