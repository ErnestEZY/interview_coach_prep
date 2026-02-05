import os
from typing import List
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.llms.mistralai import MistralAI
from llama_index.embeddings.mistralai import MistralAIEmbedding
from ..config import MISTRAL_API_KEY

class RAGEngine:
    """
    RAG Engine using LlamaIndex with Mistral AI.
    Optimized for low-memory environments (Render Free Tier) by offloading 
    embeddings and LLM tasks to Mistral's API.
    """
    def __init__(self, docs_dir: str = "backend/data/rag_docs"):
        self.docs_dir = docs_dir
        self.index = None
        self._initialized = False

    def initialize(self):
        """Initializes the LlamaIndex with Mistral AI."""
        if self._initialized:
            return

        if not MISTRAL_API_KEY:
            print("Warning: MISTRAL_API_KEY not found. RAG Engine will not be initialized.")
            return

        print("Initializing LlamaIndex RAG Engine with Mistral AI...")
        
        try:
            # Configure LlamaIndex to use Mistral for both LLM and Embeddings
            # This is crucial for keeping local memory usage low
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
            print(f"LlamaIndex RAG Engine ready with {len(documents)} documents.")
        except Exception as e:
            print(f"Error initializing LlamaIndex: {e}")

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieves relevant chunks using LlamaIndex vector search.
        """
        self._ensure_initialized()
        if not self.index:
            print("RAG Engine not initialized. Returning empty results.")
            return []

        try:
            retriever = self.index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            return [node.get_content() for node in nodes]
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []

# Singleton instance
rag_engine = RAGEngine()
