import os
import time
from typing import List
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.mistralai import MistralAI
from llama_index.embeddings.mistralai import MistralAIEmbedding
from mistralai import Mistral
from ..core.config import MISTRAL_API_KEY

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
        Retrieves relevant chunks using Hybrid-style search:
        1. Vector search to get initial candidates (Top 10)
        2. Mistral Reranker to select the most relevant chunks (Top K)
        """
        self._ensure_initialized()
        if not self.index or not self.mistral_client:
            print("RAG Engine not fully initialized. Returning empty results.")
            return []

        try:
            # 1. Fetch initial candidates
            # Using a slightly lower similarity_top_k if reranking is likely to fail
            retriever = self.index.as_retriever(similarity_top_k=10)
            nodes = retriever.retrieve(query)
            
            if not nodes:
                return []

            # 2. Rerank using Mistral's API
            documents = [node.get_content() for node in nodes]
            
            try:
                rerank_response = self.mistral_client.rerank.rerank(
                    model="mistral-rerank-latest",
                    query=query,
                    documents=documents,
                    top_n=top_k
                )
                
                results = []
                for hit in rerank_response.data:
                    results.append(documents[hit.index])
                
                return results
            except Exception as rerank_err:
                # Robust fallback to vector results if reranker fails (e.g., 429)
                print(f"Reranking failed (likely API limit), falling back to vector results: {rerank_err}")
                return documents[:top_k]

        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []

# Singleton instance
rag_engine = RAGEngine()
