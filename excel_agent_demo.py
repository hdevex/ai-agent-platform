"""
Enhanced demo server with Excel file processing capabilities for Senior Finance Manager Agent.
"""

import sys
import os
import io
import base64
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

# Excel processing imports
try:
    import pandas as pd
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    print("⚠️  Install pandas and openpyxl for Excel support: pip install pandas openpyxl")


# Enhanced models for Excel processing
class ExcelAnalysisRequest(BaseModel):
    file_data: str  # Base64 encoded Excel file
    filename: str
    analysis_type: str = "general"  # general, financial, subsidiary, cash_flow, etc.
    specific_query: str = ""


class ExcelAnalysisResponse(BaseModel):
    analysis: str
    summary: Dict[str, Any]
    recommendations: List[str]
    data_insights: Dict[str, Any]
    execution_time_ms: int


class ChatRequest(BaseModel):
    message: str
    agent_name: str = "SeniorFinanceManager"
    use_rag: bool = True
    excel_context: Optional[Dict[str, Any]] = None


# Existing models remain the same...
class ChatResponse(BaseModel):
    response: str
    agent_name: str
    execution_time_ms: int
    sources_used: List[str] = []


class AgentCreateRequest(BaseModel):
    name: str
    description: str
    agent_type: str = "finance_manager"
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


# Storage
agents_db: Dict[str, Dict[str, Any]] = {}
rag_db: Dict[str, List[Dict[str, Any]]] = {
    "default": [],
    "financial_data": [],
    "company_policies": []
}

# Excel analysis cache
excel_analysis_cache: Dict[str, Dict[str, Any]] = {}

# LM Studio configuration
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"


def process_excel_file(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Process Excel file and extract structured information."""
    if not EXCEL_SUPPORT:
        return {"error": "Excel support not available. Install pandas and openpyxl."}
    
    try:
        # Read Excel file
        excel_file = pd.ExcelFile(io.BytesIO(file_data))
        
        analysis = {
            "filename": filename,
            "sheets": {},
            "summary": {},
            "financial_metrics": {},
            "subsidiaries_data": {}
        }
        
        # Process each sheet
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                
                sheet_info = {
                    "shape": df.shape,
                    "columns": list(df.columns),
                    "data_types": df.dtypes.astype(str).to_dict(),
                    "sample_data": {},
                    "financial_indicators": {},
                    "subsidiaries": []
                }
                
                # Get sample data (first few rows, handling NaN values)
                sample_data = df.head(10).fillna("").to_dict('records')
                sheet_info["sample_data"] = sample_data
                
                # Detect financial patterns
                financial_keywords = ['revenue', 'profit', 'loss', 'assets', 'liabilities', 
                                    'equity', 'cash', 'expenses', 'income', 'balance',
                                    'rm', 'ringgit', 'million', 'thousand']
                
                # Look for subsidiary names (Malaysian context)
                malaysian_indicators = ['sdn bhd', 'sdn. bhd.', 'berhad', 'bhd', 'malaysia',
                                      'kuala lumpur', 'johor', 'penang', 'selangor']
                
                # Analyze columns for financial data
                for col in df.columns:
                    col_str = str(col).lower()
                    if any(keyword in col_str for keyword in financial_keywords):
                        try:
                            numeric_data = pd.to_numeric(df[col], errors='coerce').dropna()
                            if len(numeric_data) > 0:
                                sheet_info["financial_indicators"][col] = {
                                    "sum": float(numeric_data.sum()),
                                    "mean": float(numeric_data.mean()),
                                    "max": float(numeric_data.max()),
                                    "min": float(numeric_data.min()),
                                    "count": int(len(numeric_data))
                                }
                        except:
                            pass
                
                # Look for subsidiary information
                for col in df.columns:
                    col_data = df[col].astype(str).str.lower()
                    subsidiaries = col_data[col_data.str.contains('|'.join(malaysian_indicators), na=False)]
                    if len(subsidiaries) > 0:
                        sheet_info["subsidiaries"] = subsidiaries.unique().tolist()
                
                analysis["sheets"][sheet_name] = sheet_info
                
            except Exception as e:
                analysis["sheets"][sheet_name] = {"error": f"Error processing sheet: {str(e)}"}
        
        # Generate overall summary
        total_rows = sum(sheet.get("shape", [0, 0])[0] for sheet in analysis["sheets"].values() if isinstance(sheet, dict) and "shape" in sheet)
        total_financial_indicators = sum(len(sheet.get("financial_indicators", {})) for sheet in analysis["sheets"].values() if isinstance(sheet, dict))
        
        analysis["summary"] = {
            "total_sheets": len(excel_file.sheet_names),
            "total_rows": total_rows,
            "financial_indicators_found": total_financial_indicators,
            "processing_timestamp": time.time()
        }
        
        return analysis
        
    except Exception as e:
        return {"error": f"Failed to process Excel file: {str(e)}"}


async def call_lm_studio(messages: List[Dict[str, str]]) -> str:
    """Call your LM Studio instance."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increased timeout for complex analysis
            response = await client.post(
                f"{LM_STUDIO_BASE_URL}/chat/completions",
                json={
                    "model": LM_STUDIO_MODEL,
                    "messages": messages,
                    "temperature": 0.3,  # Lower temperature for financial analysis
                    "max_tokens": 2000,  # Increased for detailed analysis
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


def simple_rag_search(question: str, collection_name: str = "default", k: int = 3) -> List[Dict[str, Any]]:
    """Simple RAG search using keyword matching."""
    documents = rag_db.get(collection_name, [])
    if not documents:
        return []
    
    question_words = set(question.lower().split())
    scored_docs = []
    
    for doc in documents:
        text_words = set(doc["text"].lower().split())
        score = len(question_words.intersection(text_words))
        if score > 0:
            scored_docs.append((score, doc))
    
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored_docs[:k]]


# Create FastAPI app
app = FastAPI(
    title="AI Agent Platform - Excel Finance Manager",
    version="2.1.0",
    description="Specialized AI Agent Platform with Excel processing for Malaysian Investment Holdings"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize the Senior Finance Manager agent on startup."""
    # Create the Senior Finance Manager agent automatically
    agent_id = "senior-finance-manager-001"
    agent_data = {
        "id": agent_id,
        "name": "Dato' Ahmad Rahman",
        "description": "Senior Finance Manager with 25+ years experience in Malaysian investment holdings, expert in subsidiary management, financial analysis, and regulatory compliance",
        "agent_type": "senior_finance_manager",
        "capabilities": [
            "excel_file_analysis",
            "subsidiary_financial_review", 
            "malaysian_corporate_compliance",
            "investment_portfolio_analysis",
            "cash_flow_management",
            "financial_reporting",
            "risk_assessment",
            "budgeting_and_forecasting"
        ],
        "status": "ready",
        "created_at": time.time(),
        "persona": "experienced_malaysian_finance_executive",
        "specialization": "investment_holdings_management"
    }
    
    agents_db[agent_id] = agent_data
    
    # Add some Malaysian finance knowledge to RAG
    malaysian_finance_knowledge = [
        {
            "text": "Malaysian Corporate Compliance: All Malaysian investment holding companies must comply with Companies Act 2016, Bursa Malaysia listing requirements, and Bank Negara Malaysia guidelines. Subsidiary financial reporting must be consolidated according to Malaysian Financial Reporting Standards (MFRS).",
            "metadata": {"source": "malaysian_compliance.txt", "category": "regulatory"},
        },
        {
            "text": "Investment Holdings Best Practices: For Malaysian investment holdings, monitor subsidiary performance through quarterly management accounts, cash flow projections, and KPI dashboards. Pay attention to related party transactions, transfer pricing, and inter-company loans compliance with tax regulations.",
            "metadata": {"source": "holdings_best_practices.txt", "category": "management"},
        },
        {
            "text": "Excel Financial Analysis: When analyzing unstructured Excel files from subsidiaries, look for key metrics: Revenue trends, EBITDA margins, working capital changes, capex requirements, and debt servicing ability. Cross-reference with budget vs actual performance and identify variance explanations.",
            "metadata": {"source": "excel_analysis_guide.txt", "category": "technical"},
        }
    ]
    
    for knowledge in malaysian_finance_knowledge:
        doc_id = str(uuid.uuid4())
        document = {
            "id": doc_id,
            "text": knowledge["text"],
            "metadata": knowledge["metadata"],
            "created_at": time.time()
        }
        rag_db["company_policies"].append(document)
    
    print("🏢 Senior Finance Manager 'Dato' Ahmad Rahman' initialized")
    print("📊 Malaysian investment holdings knowledge base loaded")


@app.get("/")
async def root():
    return {
        "message": "AI Agent Platform - Excel Finance Manager",
        "version": "2.1.0",
        "specialized_agent": "Senior Finance Manager for Malaysian Investment Holdings",
        "capabilities": ["Excel Analysis", "Subsidiary Management", "Financial Reporting"],
        "endpoints": {
            "health": "/health",
            "agents": "/agents/",
            "chat": "/chat",
            "excel_analysis": "/excel/analyze",
            "excel_upload": "/excel/upload"
        }
    }


@app.get("/health")
async def health_check():
    lm_studio_health = await check_lm_studio_health()
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "lm_studio": lm_studio_health,
            "agents": {"count": len(agents_db)},
            "rag": {
                "collections": list(rag_db.keys()), 
                "total_docs": sum(len(docs) for docs in rag_db.values())
            },
            "excel_support": EXCEL_SUPPORT
        },
        "specialized_features": {
            "malaysian_finance_expertise": True,
            "excel_file_processing": EXCEL_SUPPORT,
            "subsidiary_analysis": True
        }
    }


async def check_lm_studio_health() -> Dict[str, Any]:
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
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/excel/upload")
async def upload_excel_file(file: UploadFile = File(...)):
    """Upload and analyze Excel file."""
    if not EXCEL_SUPPORT:
        raise HTTPException(status_code=400, detail="Excel support not available. Install pandas and openpyxl.")
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
    
    try:
        # Read file data
        file_data = await file.read()
        
        # Process Excel file
        analysis = process_excel_file(file_data, file.filename)
        
        # Store in cache for future reference
        file_id = str(uuid.uuid4())
        excel_analysis_cache[file_id] = {
            "filename": file.filename,
            "analysis": analysis,
            "uploaded_at": time.time()
        }
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "status": "processed",
            "summary": analysis.get("summary", {}),
            "sheets_found": list(analysis.get("sheets", {}).keys()) if "sheets" in analysis else [],
            "message": "Excel file uploaded and analyzed successfully. Use /excel/analyze for detailed insights."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Excel file: {str(e)}")


@app.post("/excel/analyze", response_model=ExcelAnalysisResponse)
async def analyze_excel_with_agent(
    file_id: str = Form(...),
    analysis_type: str = Form("general"),
    specific_query: str = Form("")
):
    """Analyze Excel file using the Senior Finance Manager agent."""
    start_time = time.time()
    
    if file_id not in excel_analysis_cache:
        raise HTTPException(status_code=404, detail="Excel file not found. Please upload first.")
    
    excel_data = excel_analysis_cache[file_id]
    analysis = excel_data["analysis"]
    
    # Build context for the Senior Finance Manager
    context_parts = [
        f"I am analyzing the Excel file '{excel_data['filename']}' for our Malaysian investment holding company.",
        f"File contains {len(analysis.get('sheets', {}))} sheets with the following structure:"
    ]
    
    # Add sheet information
    for sheet_name, sheet_data in analysis.get("sheets", {}).items():
        if isinstance(sheet_data, dict) and "shape" in sheet_data:
            context_parts.append(f"- Sheet '{sheet_name}': {sheet_data['shape'][0]} rows, {sheet_data['shape'][1]} columns")
            if sheet_data.get("financial_indicators"):
                context_parts.append(f"  Financial indicators found: {list(sheet_data['financial_indicators'].keys())}")
            if sheet_data.get("subsidiaries"):
                context_parts.append(f"  Subsidiaries mentioned: {sheet_data['subsidiaries']}")
    
    # Add RAG context
    rag_context = simple_rag_search(f"{analysis_type} {specific_query} excel analysis", "company_policies", 3)
    if rag_context:
        context_parts.append("Relevant company policies and guidelines:")
        for doc in rag_context:
            context_parts.append(f"- {doc['text'][:200]}...")
    
    # Build messages for Senior Finance Manager persona
    system_message = {
        "role": "system",
        "content": f"""You are Dato' Ahmad Rahman, a Senior Finance Manager with 25+ years of experience managing Malaysian investment holding companies with multiple subsidiaries.

Your expertise includes:
- Malaysian corporate compliance (Companies Act 2016, Bursa Malaysia requirements)
- Subsidiary financial analysis and consolidation
- Investment portfolio management
- Risk assessment and financial reporting
- Excel-based financial analysis of unstructured data

You speak with authority and experience, providing practical insights that reflect deep understanding of Malaysian business environment and investment holdings management.

Analysis Context:
{chr(10).join(context_parts)}

Please provide detailed financial analysis with specific recommendations for our investment holding company."""
    }
    
    analysis_prompt = f"""Please analyze this Excel file with the following focus:

Analysis Type: {analysis_type}
Specific Query: {specific_query if specific_query else 'General financial overview and subsidiary performance assessment'}

Based on the Excel data structure and content, please provide:

1. **Executive Summary**: Key findings and overall financial health
2. **Subsidiary Performance Analysis**: Individual subsidiary assessments if data available
3. **Financial Metrics Review**: Analysis of key financial indicators found
4. **Risk Assessment**: Potential concerns or red flags identified
5. **Recommendations**: Specific action items for management
6. **Compliance Considerations**: Malaysian regulatory aspects to consider

Focus on practical insights that a senior finance manager would provide to the board of directors."""
    
    messages = [
        system_message,
        {"role": "user", "content": analysis_prompt}
    ]
    
    # Get comprehensive analysis from LM Studio
    response = await call_lm_studio(messages)
    
    # Generate summary and recommendations
    summary = {
        "file_processed": excel_data['filename'],
        "sheets_analyzed": len(analysis.get('sheets', {})),
        "analysis_type": analysis_type,
        "total_financial_indicators": sum(
            len(sheet.get('financial_indicators', {})) 
            for sheet in analysis.get('sheets', {}).values() 
            if isinstance(sheet, dict)
        )
    }
    
    # Extract recommendations (simple keyword-based extraction)
    recommendations = []
    if "recommend" in response.lower():
        lines = response.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['recommend', 'suggest', 'should', 'must', 'action']):
                if len(line.strip()) > 20:
                    recommendations.append(line.strip())
    
    if not recommendations:
        recommendations = ["Review detailed analysis above for specific insights and action items"]
    
    # Data insights
    data_insights = {
        "sheets_with_financial_data": [
            name for name, sheet in analysis.get('sheets', {}).items() 
            if isinstance(sheet, dict) and sheet.get('financial_indicators')
        ],
        "subsidiaries_identified": [
            sub for sheet in analysis.get('sheets', {}).values() 
            if isinstance(sheet, dict) and sheet.get('subsidiaries')
            for sub in sheet['subsidiaries']
        ],
        "processing_timestamp": time.time()
    }
    
    execution_time = int((time.time() - start_time) * 1000)
    
    return ExcelAnalysisResponse(
        analysis=response,
        summary=summary,
        recommendations=recommendations[:5],  # Limit to top 5
        data_insights=data_insights,
        execution_time_ms=execution_time
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_with_finance_manager(request: ChatRequest):
    """Chat with the Senior Finance Manager agent."""
    start_time = time.time()
    
    # Build system message with Malaysian finance manager persona
    system_message = {
        "role": "system",
        "content": """You are Dato' Ahmad Rahman, a Senior Finance Manager with 25+ years of experience in Malaysian investment holding companies. 

Your background:
- Chartered Accountant (CA Malaysia) and CPA
- Extensive experience with Bursa Malaysia listed companies
- Expert in managing subsidiaries across various sectors
- Deep knowledge of Malaysian tax, corporate law, and regulatory requirements
- Skilled in Excel-based financial analysis and reporting

Your communication style:
- Professional but approachable
- Use Malaysian business terminology when appropriate
- Reference relevant Malaysian regulations and practices
- Provide practical, actionable advice
- Draw from extensive experience with investment holdings

You excel at analyzing complex financial data, especially from Excel files, and providing strategic insights for subsidiary management and investment decisions."""
    }
    
    messages = [system_message]
    sources_used = []
    
    # Add RAG context if requested
    if request.use_rag:
        relevant_docs = simple_rag_search(request.message, "company_policies", 3)
        if relevant_docs:
            context_text = "\n".join([f"Reference: {doc['text']}" for doc in relevant_docs])
            messages.append({
                "role": "system", 
                "content": f"Relevant company policies and guidelines:\n{context_text}"
            })
            sources_used = [doc.get("metadata", {}).get("source", "unknown") for doc in relevant_docs]
    
    # Add Excel context if provided
    if request.excel_context:
        excel_context = f"Excel file context: {json.dumps(request.excel_context, indent=2)}"
        messages.append({
            "role": "system",
            "content": f"Current Excel analysis context:\n{excel_context}"
        })
    
    # Add user message
    messages.append({"role": "user", "content": request.message})
    
    # Get response from LM Studio
    response = await call_lm_studio(messages)
    
    execution_time = int((time.time() - start_time) * 1000)
    
    return ChatResponse(
        response=response,
        agent_name="Dato' Ahmad Rahman (Senior Finance Manager)",
        execution_time_ms=execution_time,
        sources_used=sources_used
    )


@app.get("/agents/")
async def list_agents():
    return {
        "agents": list(agents_db.values()),
        "total_count": len(agents_db),
        "specialized_agent": "Senior Finance Manager - Malaysian Investment Holdings Expert"
    }


@app.get("/excel/cache")
async def list_excel_files():
    """List all uploaded Excel files."""
    return {
        "files": [
            {
                "file_id": file_id,
                "filename": data["filename"],
                "uploaded_at": data["uploaded_at"],
                "sheets": list(data["analysis"].get("sheets", {}).keys()) if "analysis" in data else []
            }
            for file_id, data in excel_analysis_cache.items()
        ],
        "total_files": len(excel_analysis_cache)
    }


# Existing RAG endpoints...
@app.post("/rag/add")
async def add_to_rag(request: RAGAddRequest):
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


if __name__ == "__main__":
    print("🏢 Starting AI Agent Platform - Excel Finance Manager")
    print(f"📡 LM Studio URL: {LM_STUDIO_BASE_URL}")
    print(f"🤖 Model: {LM_STUDIO_MODEL}")
    print("👔 Specialized Agent: Dato' Ahmad Rahman - Senior Finance Manager")
    print("🇲🇾 Expertise: Malaysian Investment Holdings & Subsidiaries")
    print(f"📊 Excel Support: {'✅ Available' if EXCEL_SUPPORT else '❌ Install pandas & openpyxl'}")
    print("📈 Access the API at: http://localhost:8001")
    print("📚 API docs at: http://localhost:8001/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)