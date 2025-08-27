"""
Demo server to test the AI Agent Platform without full dependencies.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel


# Simple models for demo
class ChatRequest(BaseModel):
    message: str
    agent_name: str = "DemoAgent"
    use_rag: bool = False


class ChatResponse(BaseModel):
    response: str
    agent_name: str
    execution_time_ms: int
    sources_used: List[str] = []


class AgentCreateRequest(BaseModel):
    name: str
    description: str
    agent_type: str = "demo_agent"
    capabilities: List[str] = []


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_type: str
    capabilities: List[str]
    status: str = "ready"
    created_at: str


class RAGAddRequest(BaseModel):
    text: str
    metadata: Dict[str, Any] = {}
    collection_name: str = "default"


class RAGQueryRequest(BaseModel):
    question: str
    collection_name: str = "default"
    k: int = 3


# Simple in-memory storage
agents_db: Dict[str, Dict[str, Any]] = {}
rag_db: Dict[str, List[Dict[str, Any]]] = {"default": []}

# LM Studio configuration from config
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"


async def call_lm_studio(messages: List[Dict[str, str]]) -> str:
    """Call your LM Studio instance."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{LM_STUDIO_BASE_URL}/chat/completions",
                json={
                    "model": LM_STUDIO_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Error calling LM Studio: HTTP {response.status_code}"
                
    except Exception as e:
        return f"Error connecting to LM Studio: {str(e)}"


async def check_lm_studio_health() -> Dict[str, Any]:
    """Check if your LM Studio is accessible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{LM_STUDIO_BASE_URL}/models")
            
            if response.status_code == 200:
                models = response.json()
                return {
                    "status": "healthy",
                    "url": LM_STUDIO_BASE_URL,
                    "models": [model["id"] for model in models.get("data", [])],
                    "preferred_model": LM_STUDIO_MODEL
                }
            else:
                return {
                    "status": "unhealthy", 
                    "error": f"HTTP {response.status_code}",
                    "url": LM_STUDIO_BASE_URL
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "url": LM_STUDIO_BASE_URL
        }


def simple_rag_search(question: str, collection_name: str = "default", k: int = 3) -> List[Dict[str, Any]]:
    """Simple RAG search using keyword matching."""
    documents = rag_db.get(collection_name, [])
    if not documents:
        return []
    
    # Simple keyword matching
    question_words = set(question.lower().split())
    scored_docs = []
    
    for doc in documents:
        text_words = set(doc["text"].lower().split())
        score = len(question_words.intersection(text_words))
        if score > 0:
            scored_docs.append((score, doc))
    
    # Sort by score and return top k
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored_docs[:k]]


# Create FastAPI app
app = FastAPI(
    title="AI Agent Platform Demo",
    version="2.0.0",
    description="Demo server to test AI Agent Platform with your LM Studio setup"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Agent Platform Demo API",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "agents": "/agents/",
            "chat": "/chat",
            "rag": "/rag/"
        }
    }


@app.get("/health")
async def health_check():
    """Health check including LM Studio status."""
    lm_studio_health = await check_lm_studio_health()
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "lm_studio": lm_studio_health,
            "agents": {"count": len(agents_db)},
            "rag": {"collections": list(rag_db.keys()), "total_docs": sum(len(docs) for docs in rag_db.values())}
        }
    }


@app.post("/agents/", response_model=AgentResponse)
async def create_agent(request: AgentCreateRequest):
    """Create a new demo agent."""
    agent_id = str(uuid.uuid4())
    agent_data = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "agent_type": request.agent_type,
        "capabilities": request.capabilities,
        "status": "ready",
        "created_at": time.time(),
    }
    
    agents_db[agent_id] = agent_data
    
    return AgentResponse(
        id=agent_id,
        name=request.name,
        description=request.description,
        agent_type=request.agent_type,
        capabilities=request.capabilities,
        created_at=str(agent_data["created_at"])
    )


@app.get("/agents/")
async def list_agents():
    """List all agents."""
    return {
        "agents": list(agents_db.values()),
        "total_count": len(agents_db)
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Chat with an agent using your LM Studio."""
    start_time = time.time()
    
    # Build system message
    system_message = {
        "role": "system",
        "content": f"""You are {request.agent_name}, a helpful AI agent.
Be helpful, concise, and professional in your responses."""
    }
    
    messages = [system_message]
    sources_used = []
    
    # Add RAG context if requested
    if request.use_rag:
        relevant_docs = simple_rag_search(request.message)
        if relevant_docs:
            context_text = "\n".join([f"Context: {doc['text']}" for doc in relevant_docs])
            messages.append({
                "role": "system",
                "content": f"Relevant context information:\n{context_text}"
            })
            sources_used = [doc.get("source", "unknown") for doc in relevant_docs]
    
    # Add user message
    messages.append({"role": "user", "content": request.message})
    
    # Get response from your LM Studio
    response = await call_lm_studio(messages)
    
    execution_time = int((time.time() - start_time) * 1000)
    
    return ChatResponse(
        response=response,
        agent_name=request.agent_name,
        execution_time_ms=execution_time,
        sources_used=sources_used
    )


@app.post("/rag/add")
async def add_to_rag(request: RAGAddRequest):
    """Add text to RAG system."""
    if request.collection_name not in rag_db:
        rag_db[request.collection_name] = []
    
    doc_id = str(uuid.uuid4())
    document = {
        "id": doc_id,
        "text": request.text,
        "metadata": request.metadata,
        "created_at": time.time()
    }
    
    rag_db[request.collection_name].append(document)
    
    return {
        "document_id": doc_id,
        "collection_name": request.collection_name,
        "status": "added"
    }


@app.post("/rag/query")
async def query_rag(request: RAGQueryRequest):
    """Query RAG system."""
    relevant_docs = simple_rag_search(request.question, request.collection_name, request.k)
    
    if not relevant_docs:
        return {
            "answer": "No relevant documents found.",
            "sources": [],
            "num_sources": 0
        }
    
    # Create a simple answer from the documents
    context = "\n".join([doc["text"] for doc in relevant_docs])
    
    # Use LM Studio to generate an answer based on the context
    messages = [
        {"role": "system", "content": "Answer the question based on the provided context. Be concise and accurate."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {request.question}"}
    ]
    
    answer = await call_lm_studio(messages)
    
    return {
        "answer": answer,
        "sources": [{"id": doc["id"], "text": doc["text"][:200] + "..."} for doc in relevant_docs],
        "num_sources": len(relevant_docs)
    }


if __name__ == "__main__":
    print("🚀 Starting AI Agent Platform Demo Server...")
    print(f"📡 LM Studio URL: {LM_STUDIO_BASE_URL}")
    print(f"🤖 Preferred Model: {LM_STUDIO_MODEL}")
    print("📊 Access the API at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)