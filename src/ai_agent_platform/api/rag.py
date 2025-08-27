"""
RAG system API endpoints.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File

from ..rag.vector_store import get_rag_system
from .schemas import (
    RAGAddTextRequest,
    RAGAddFileRequest,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGAddResponse,
    SuccessResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/add-text", response_model=RAGAddResponse)
async def add_text_to_rag(request: RAGAddTextRequest):
    """Add text to RAG system."""
    try:
        rag_system = get_rag_system()
        
        doc_ids = await rag_system.add_text(
            text=request.text,
            metadata=request.metadata,
            collection_name=request.collection_name,
        )
        
        return RAGAddResponse(
            document_ids=doc_ids,
            chunks_created=len(doc_ids),
            collection_name=request.collection_name,
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to add text to RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add text: {str(e)}")


@router.post("/add-file", response_model=RAGAddResponse)
async def add_file_to_rag(request: RAGAddFileRequest):
    """Add file to RAG system."""
    try:
        rag_system = get_rag_system()
        
        doc_ids = await rag_system.add_file(
            file_path=request.file_path,
            metadata=request.metadata,
            collection_name=request.collection_name,
        )
        
        return RAGAddResponse(
            document_ids=doc_ids,
            chunks_created=len(doc_ids),
            collection_name=request.collection_name,
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
        
    except Exception as e:
        logger.error(f"❌ Failed to add file to RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add file: {str(e)}")


@router.post("/upload-file", response_model=RAGAddResponse)
async def upload_file_to_rag(
    file: UploadFile = File(...),
    collection_name: str = "default",
    metadata: str = "{}",
):
    """Upload and add file to RAG system."""
    try:
        import json
        import tempfile
        import os
        
        # Parse metadata
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            metadata_dict = {}
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Add file metadata
            metadata_dict.update({
                "original_filename": file.filename,
                "content_type": file.content_type,
                "file_size": len(content),
            })
            
            # Add to RAG system
            rag_system = get_rag_system()
            doc_ids = await rag_system.add_file(
                file_path=temp_file_path,
                metadata=metadata_dict,
                collection_name=collection_name,
            )
            
            return RAGAddResponse(
                document_ids=doc_ids,
                chunks_created=len(doc_ids),
                collection_name=collection_name,
            )
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
        
    except Exception as e:
        logger.error(f"❌ Failed to upload file to RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(request: RAGQueryRequest):
    """Query RAG system."""
    try:
        rag_system = get_rag_system()
        
        result = await rag_system.query(
            question=request.question,
            k=request.k,
            collection_name=request.collection_name,
            include_sources=request.include_sources,
        )
        
        return RAGQueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            context_used=result["context_used"],
            num_sources=result["num_sources"],
        )
        
    except Exception as e:
        logger.error(f"❌ RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/health", response_model=dict)
async def get_rag_health():
    """Get RAG system health."""
    try:
        rag_system = get_rag_system()
        health = await rag_system.health_check()
        return health
        
    except Exception as e:
        logger.error(f"❌ RAG health check failed: {e}")
        raise HTTPException(status_code=500, detail="RAG health check failed")