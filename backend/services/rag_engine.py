import os
from typing import List
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
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
        """Initializes the LlamaIndex with Mistral AI."""
        if self._initialized:
            return

        if not MISTRAL_API_KEY:
            print("Warning: MISTRAL_API_KEY not found. RAG Engine will not be initialized.")
            return

        print("Initializing Advanced RAG Engine with Mistral Reranking...")
        
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

            # Load documents and create index
            documents = SimpleDirectoryReader(self.docs_dir).load_data()
            if not documents:
                print(f"Warning: No documents found in {self.docs_dir}")
                return

            self.index = VectorStoreIndex.from_documents(documents)
            self._initialized = True
            print(f"Advanced RAG Engine ready with {len(documents)} documents.")
        except Exception as e:
            print(f"Error initializing Advanced RAG Engine: {e}")

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
            # 1. Fetch initial candidates (more than requested top_k)
            retriever = self.index.as_retriever(similarity_top_k=10)
            nodes = retriever.retrieve(query)
            
            if not nodes:
                return []

            # 2. Rerank using Mistral's API
            # Convert nodes to text list for reranker
            documents = [node.get_content() for node in nodes]
            
            try:
                rerank_response = self.mistral_client.rerank.rerank(
                    model="mistral-rerank-latest",
                    query=query,
                    documents=documents,
                    top_n=top_k
                )
                
                # Sort and select based on reranker results
                results = []
                for hit in rerank_response.data:
                    results.append(documents[hit.index])
                
                return results
            except Exception as rerank_err:
                print(f"Reranking failed, falling back to vector results: {rerank_err}")
                return documents[:top_k]

        except Exception as e:
            print(f"Error during advanced retrieval: {e}")
            return []

# Singleton instance
rag_engine = RAGEngine()
