"""
Vector store management for RAG system.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader, PDFMinerLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from ..llm.providers import get_llm_manager
from ..config import config

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector stores."""
    
    @abstractmethod
    async def add_documents(
        self, 
        documents: List[Document], 
        collection_name: str = "default"
    ) -> List[str]:
        """Add documents to vector store."""
        pass
    
    @abstractmethod
    async def similarity_search(
        self, 
        query: str, 
        k: int = 4, 
        collection_name: str = "default",
        **kwargs
    ) -> List[Document]:
        """Search for similar documents."""
        pass
    
    @abstractmethod
    async def delete_documents(
        self, 
        ids: List[str], 
        collection_name: str = "default"
    ) -> bool:
        """Delete documents by IDs."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check vector store health."""
        pass


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store implementation."""
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        """Initialize ChromaDB vector store."""
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        # LangChain Chroma instances per collection
        self.langchain_stores: Dict[str, Chroma] = {}
        
        logger.info(f"🗂️ ChromaDB vector store initialized: {self.persist_directory}")
    
    async def _get_langchain_store(self, collection_name: str = "default") -> Chroma:
        """Get LangChain Chroma instance for collection."""
        if collection_name not in self.langchain_stores:
            # Get embeddings from LLM manager
            llm_manager = get_llm_manager()
            
            # Create embedding function wrapper
            class EmbeddingFunction:
                async def embed_documents(self, texts: List[str]) -> List[List[float]]:
                    return await llm_manager.get_embeddings(texts)
                
                async def embed_query(self, text: str) -> List[float]:
                    embeddings = await llm_manager.get_embeddings([text])
                    return embeddings[0]
            
            embedding_function = EmbeddingFunction()
            
            # Create LangChain Chroma store
            self.langchain_stores[collection_name] = Chroma(
                client=self.chroma_client,
                collection_name=collection_name,
                embedding_function=embedding_function,
            )
        
        return self.langchain_stores[collection_name]
    
    async def add_documents(
        self, 
        documents: List[Document], 
        collection_name: str = "default"
    ) -> List[str]:
        """Add documents to ChromaDB."""
        try:
            store = await self._get_langchain_store(collection_name)
            
            # Generate IDs for documents
            doc_ids = [str(uuid.uuid4()) for _ in documents]
            
            # Add documents with IDs
            await store.aadd_documents(documents, ids=doc_ids)
            
            logger.info(f"✅ Added {len(documents)} documents to collection '{collection_name}'")
            return doc_ids
            
        except Exception as e:
            logger.error(f"❌ Failed to add documents to ChromaDB: {e}")
            raise
    
    async def similarity_search(
        self, 
        query: str, 
        k: int = 4, 
        collection_name: str = "default",
        **kwargs
    ) -> List[Document]:
        """Search for similar documents in ChromaDB."""
        try:
            store = await self._get_langchain_store(collection_name)
            
            # Perform similarity search
            results = await store.asimilarity_search(
                query, 
                k=k, 
                **kwargs
            )
            
            logger.info(f"🔍 Found {len(results)} similar documents for query in '{collection_name}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Similarity search failed: {e}")
            raise
    
    async def delete_documents(
        self, 
        ids: List[str], 
        collection_name: str = "default"
    ) -> bool:
        """Delete documents by IDs."""
        try:
            store = await self._get_langchain_store(collection_name)
            
            # Delete documents
            await store.adelete(ids)
            
            logger.info(f"🗑️ Deleted {len(ids)} documents from collection '{collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete documents: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ChromaDB health."""
        try:
            # List collections
            collections = self.chroma_client.list_collections()
            collection_info = []
            
            for collection in collections:
                count = collection.count()
                collection_info.append({
                    "name": collection.name,
                    "count": count,
                })
            
            return {
                "status": "healthy",
                "type": "chromadb",
                "persist_directory": str(self.persist_directory),
                "collections": collection_info,
            }
            
        except Exception as e:
            logger.error(f"❌ ChromaDB health check failed: {e}")
            return {
                "status": "unhealthy",
                "type": "chromadb",
                "error": str(e),
            }


class RAGSystem:
    """RAG (Retrieval-Augmented Generation) system."""
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        """Initialize RAG system."""
        self.vector_store = vector_store or ChromaVectorStore()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        logger.info("🧠 RAG system initialized")
    
    async def add_text(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None, 
        collection_name: str = "default"
    ) -> List[str]:
        """Add text to RAG system."""
        try:
            # Split text into chunks
            documents = self.text_splitter.create_documents(
                texts=[text],
                metadatas=[metadata or {}]
            )
            
            # Add to vector store
            doc_ids = await self.vector_store.add_documents(documents, collection_name)
            
            logger.info(f"📄 Added text as {len(documents)} chunks to RAG system")
            return doc_ids
            
        except Exception as e:
            logger.error(f"❌ Failed to add text to RAG: {e}")
            raise
    
    async def add_file(
        self, 
        file_path: str, 
        metadata: Optional[Dict[str, Any]] = None,
        collection_name: str = "default"
    ) -> List[str]:
        """Add file to RAG system."""
        try:
            file_path = Path(file_path)
            
            # Choose appropriate loader based on file type
            if file_path.suffix.lower() == ".pdf":
                loader = PDFMinerLoader(str(file_path))
            else:
                loader = TextLoader(str(file_path), encoding="utf-8")
            
            # Load documents
            documents = loader.load()
            
            # Add file metadata
            file_metadata = metadata or {}
            file_metadata.update({
                "source_file": str(file_path),
                "file_type": file_path.suffix.lower(),
            })
            
            for doc in documents:
                doc.metadata.update(file_metadata)
            
            # Split documents
            split_docs = self.text_splitter.split_documents(documents)
            
            # Add to vector store
            doc_ids = await self.vector_store.add_documents(split_docs, collection_name)
            
            logger.info(f"📁 Added file '{file_path}' as {len(split_docs)} chunks to RAG system")
            return doc_ids
            
        except Exception as e:
            logger.error(f"❌ Failed to add file to RAG: {e}")
            raise
    
    async def query(
        self, 
        question: str, 
        k: int = 4, 
        collection_name: str = "default",
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """Query RAG system for relevant information."""
        try:
            # Retrieve relevant documents
            relevant_docs = await self.vector_store.similarity_search(
                question, k=k, collection_name=collection_name
            )
            
            if not relevant_docs:
                return {
                    "answer": "I don't have relevant information to answer this question.",
                    "sources": [],
                    "context_used": False
                }
            
            # Build context from retrieved documents
            context_parts = []
            sources = []
            
            for i, doc in enumerate(relevant_docs, 1):
                context_parts.append(f"Context {i}:\n{doc.page_content}")
                if include_sources and doc.metadata:
                    sources.append({
                        "chunk_id": i,
                        "metadata": doc.metadata,
                        "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                    })
            
            context = "\n\n".join(context_parts)
            
            # Generate answer using LLM
            llm_manager = get_llm_manager()
            
            prompt = f"""Based on the following context, please answer the question. If the context doesn't contain enough information to answer the question, please say so.

Context:
{context}

Question: {question}

Answer:"""

            answer = await llm_manager.completion(prompt)
            
            return {
                "answer": answer.strip(),
                "sources": sources if include_sources else [],
                "context_used": True,
                "num_sources": len(relevant_docs)
            }
            
        except Exception as e:
            logger.error(f"❌ RAG query failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check RAG system health."""
        vector_health = await self.vector_store.health_check()
        
        return {
            "status": "healthy" if vector_health.get("status") == "healthy" else "degraded",
            "components": {
                "vector_store": vector_health,
                "text_splitter": {
                    "chunk_size": self.text_splitter._chunk_size,
                    "chunk_overlap": self.text_splitter._chunk_overlap,
                }
            }
        }


# Global RAG system instance
rag_system: Optional[RAGSystem] = None


def get_rag_system() -> RAGSystem:
    """Get global RAG system instance."""
    global rag_system
    if rag_system is None:
        rag_system = RAGSystem()
    return rag_system