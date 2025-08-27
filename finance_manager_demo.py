"""
Malaysian Investment Holdings Finance Manager Agent Demo
- Works without pandas/openpyxl dependencies
- Shows Excel file upload interface 
- Demonstrates Senior Finance Manager persona
"""

import sys
import os
import json
import time
import uuid
import tempfile
from typing import Dict, Any, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import httpx
from pydantic import BaseModel


# Models
class ChatRequest(BaseModel):
    message: str
    agent_name: str = "Dato Ahmad Rahman"
    use_rag: bool = True


class ChatResponse(BaseModel):
    response: str
    agent_name: str
    execution_time_ms: int
    sources_used: List[str] = []


class ExcelUploadResponse(BaseModel):
    message: str
    filename: str
    status: str
    analysis_preview: str


# Storage
agents_db: Dict[str, Dict[str, Any]] = {}
rag_db: Dict[str, List[Dict[str, Any]]] = {
    "malaysian_finance": [],
    "investment_holdings": [],
    "subsidiary_management": []
}

# LM Studio configuration
from real_excel_chat_system import IntelligentQueryAnalyzer, TokenEfficientDataRetriever
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"

uploaded_files = {}  # Simple file storage


async def call_lm_studio(messages: List[Dict[str, str]]) -> str:
    """Call your LM Studio instance."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LM_STUDIO_BASE_URL}/chat/completions",
                json={
                    "model": LM_STUDIO_MODEL,
                    "messages": messages,
                    "temperature": 0.2,  # Lower temperature for financial analysis
                    "max_tokens": 2000,
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


def simple_rag_search(question: str, collection_name: str = "malaysian_finance", k: int = 3) -> List[Dict[str, Any]]:
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
    title="Dato' Ahmad Rahman - Senior Finance Manager",
    version="3.0.0",
    description="AI Senior Finance Manager specialized in Malaysian Investment Holdings and Excel Analysis"
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
    """Initialize the Senior Finance Manager."""
    # Create Dato' Ahmad Rahman
    agent_id = "dato-ahmad-rahman"
    agent_data = {
        "id": agent_id,
        "name": "Dato' Ahmad Rahman",
        "title": "Senior Finance Manager",
        "company": "Malaysian Investment Holdings Berhad",
        "experience_years": 25,
        "certifications": ["CA Malaysia", "CPA", "CISA"],
        "specialties": [
            "Investment Holdings Management",
            "Subsidiary Financial Analysis", 
            "Malaysian Corporate Compliance",
            "Excel-based Financial Modeling",
            "Bursa Malaysia Regulations",
            "Multi-subsidiary Consolidation"
        ],
        "languages": ["English", "Bahasa Malaysia", "Mandarin"],
        "status": "active",
        "created_at": time.time()
    }
    
    agents_db[agent_id] = agent_data
    
    # Load Malaysian finance knowledge
    knowledge_base = [
        {
            "text": "Malaysian Investment Holdings Compliance: Under Companies Act 2016, all holding companies must maintain proper subsidiary records, consolidated financial statements, and comply with Bursa Malaysia continuous disclosure requirements. Key focus areas include related party transactions, material contracts, and quarterly reporting deadlines.",
            "metadata": {"source": "Companies_Act_2016", "category": "regulatory"},
        },
        {
            "text": "Subsidiary Performance Monitoring: For Malaysian investment holdings, establish monthly management reporting from all subsidiaries including: Revenue trends, EBITDA performance, cash flow projections, capex requirements, working capital analysis, and debt covenant compliance. Use standardized Excel templates for consistent reporting.",
            "metadata": {"source": "Management_Guidelines", "category": "operations"},
        },
        {
            "text": "Excel Financial Analysis Best Practices: When reviewing subsidiary Excel reports, focus on variance analysis (budget vs actual), trend analysis (YoY and QoQ), ratio analysis (liquidity, profitability, leverage), and cash flow forecasting. Look for red flags: declining margins, increasing receivables days, inventory buildup, or covenant breaches.",
            "metadata": {"source": "Financial_Analysis_Manual", "category": "technical"},
        },
        {
            "text": "Malaysian Tax Considerations: For investment holdings with multiple subsidiaries, monitor transfer pricing documentation, withholding tax on inter-company transactions, Section 140A deemed dividend provisions, and thin capitalization rules. Ensure all subsidiaries maintain proper supporting documentation for related party transactions.",
            "metadata": {"source": "Tax_Guidelines_Malaysia", "category": "tax"},
        },
        {
            "text": "Risk Management Framework: Investment holdings should implement risk assessment across all subsidiaries focusing on: Market risk (sector exposure), credit risk (customer concentration), operational risk (key person dependency), liquidity risk (cash flow timing), and regulatory risk (compliance requirements). Monthly risk dashboards are essential.",
            "metadata": {"source": "Risk_Management_Policy", "category": "risk"},
        }
    ]
    
    for knowledge in knowledge_base:
        doc_id = str(uuid.uuid4())
        document = {
            "id": doc_id,
            "text": knowledge["text"],
            "metadata": knowledge["metadata"],
            "created_at": time.time()
        }
        rag_db["malaysian_finance"].append(document)
    
    print("SUCCESS: Dato' Ahmad Rahman - Senior Finance Manager initialized")
    print(f"Loaded {len(knowledge_base)} Malaysian finance knowledge documents")


@app.get("/")
async def root():
    return {
        "agent": "Dato' Ahmad Rahman",
        "title": "Senior Finance Manager", 
        "company": "Malaysian Investment Holdings Specialist",
        "expertise": [
            "Excel Financial Analysis",
            "Subsidiary Management", 
            "Malaysian Corporate Compliance",
            "Investment Holdings Strategy"
        ],
        "endpoints": {
            "chat": "/chat - Chat with Dato' Ahmad",
            "excel_upload": "/excel/upload - Upload Excel files for analysis", 
            "health": "/health - System status",
            "demo_page": "/demo - Interactive demo page"
        },
        "message": "Selamat datang! I'm here to help with your investment holdings and financial analysis."
    }

# ---------- NEW ENDPOINTS ----------
def parse_query(raw: str) -> Dict[str, Any]:
    """Convenience wrapper around the analyzer.

    Returns a dict containing intent scores and target sheets so that callers can
    reuse the same logic without re‑instantiating the analyzer each time."""
    analyzer = IntelligentQueryAnalyzer()
    return analyzer.analyze_query(raw or "")

@app.post("/excel/upload")
async def upload_excel(file: UploadFile = File(...), specific_query: Optional[str] = Form(None)):
    """Upload Excel file and get REAL AI analysis using RealExcelChatSystem."""
    content = await file.read()
    uploaded_files[file.filename] = {
        "content": content,
        "timestamp": time.time(),
    }

    # Process and store the Excel file in the database properly
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))

    try:
        # DEBUG: Add explicit debug info to response
        debug_info = []
        debug_info.append("STARTING EXCEL PROCESSING...")

        # Save uploaded file temporarily for processing
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, file.filename)
        debug_info.append(f"Created temp file: {temp_file_path}")

        with open(temp_file_path, 'wb') as f:
            f.write(content)
        debug_info.append("File saved to temp location")

        # Use the proper Excel to Database system
        from excel_to_database_system import ExcelDatabaseSystem
        debug_info.append("Imported ExcelDatabaseSystem")

        db_system = ExcelDatabaseSystem()
        debug_info.append("Created ExcelDatabaseSystem instance")

        try:
            # Step 1: Extract data from Excel file
            debug_info.append(f"Starting extract_excel_data for {temp_file_path}...")
            file_data = db_system.extract_excel_data(temp_file_path)
            debug_info.append(f"Extraction complete. Found {len(file_data.get('sheets_data', {}))} sheets")

            # Step 2: Store in database with AI analysis
            if file_data and file_data.get("sheets_data") and len(file_data.get("sheets_data", {})) > 0:
                debug_info.append("Starting store_in_database...")
                file_id = await db_system.store_in_database(file_data)
                debug_info.append(f"Database storage complete. File ID: {file_id}")

                sheets_data = file_data.get("sheets_data", {})
                result = {
                    "success": True,
                    "file_id": file_id,
                    "sheets_count": len(sheets_data),
                    "total_cells": sum(len(sheet.get("cells", [])) for sheet in sheets_data.values()),
                    "sheet_names": list(sheets_data.keys())
                }
                debug_info.append(f"Final result: {result}")
            else:
                result = {"success": False, "error": "No data extracted from Excel file"}
                debug_info.append(f"Extraction failed: {file_data}")

        except Exception as e:
            debug_info.append(f"ERROR during processing: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            debug_info.append(f"Full error: {error_details}")
            result = {"success": False, "error": str(e)}

        # Clean up temp file
        os.unlink(temp_file_path)
        os.rmdir(temp_dir)

        if result["success"]:
            preview = f"SUCCESS: Excel file '{file.filename}' processed and stored successfully!\n"
            preview += f"Found {result['sheets_count']} sheets with {result['total_cells']} cells\n"
            preview += f"Sheets: {', '.join(result['sheet_names'][:3])}{'...' if len(result['sheet_names']) > 3 else ''}\n\n"
            preview += "DEBUG INFO:\n"
            preview += f"- File ID: {result['file_id']}\n"
            preview += f"- Sheets processed: {result['sheet_names']}\n\n"
            preview += "PROCESSING LOG:\n" + "\n".join(f"- {info}" for info in debug_info) + "\n\n"
            preview += "You can now ask questions about this data!\n"
            preview += "Try: 'list company names', 'what is the revenue', 'show me PNL data'"

            return ExcelUploadResponse(
                message="File processed and stored in database successfully",
                filename=file.filename,
                status="success",
                analysis_preview=preview,
            )
        else:
            return ExcelUploadResponse(
                message="File uploaded but processing failed",
                filename=file.filename,
                status="error",
                analysis_preview=f"Error: {result.get('error', 'Unknown error')}",
            )

    except Exception as e:
        return ExcelUploadResponse(
            message="File upload failed",
            filename=file.filename,
            status="error",
            analysis_preview=f"Error: {str(e)}",
        )

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"🔍 CHAT ENDPOINT 1 called with: {request.message}")
    analysis = parse_query(request.message)
    retriever = TokenEfficientDataRetriever()
    relevant_data = retriever.get_relevant_data(analysis, max_tokens=1500)
    print(f"📊 Retrieved {len(relevant_data)} data items")
    context_texts = [item.get("data", "") for item in relevant_data]
    system_prompt = "You are a finance analyst. Use the following data: " + "\n".join(context_texts)
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": request.message}]
    ai_response = await call_lm_studio(messages)
    return ChatResponse(
        response=ai_response,
        agent_name=request.agent_name,
        execution_time_ms=int((time.time() - request.__dict__.get("timestamp", 0)) * 1000),
        sources_used=[item.get("sheet", "") for item in relevant_data],
    )


@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Interactive demo page."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dato Ahmad Rahman - Senior Finance Manager</title>
        <style>
            /* Dark Theme Styles */
            body { 
                font-family: Arial, sans-serif; 
                max-width: 1200px; 
                margin: 0 auto; 
                padding: 20px; 
                background-color: #0f172a; 
                color: #e2e8f0; 
            }
            .header { 
                background: linear-gradient(135deg, #1e40af, #3b82f6); 
                color: white; 
                padding: 20px; 
                border-radius: 8px; 
                margin-bottom: 20px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }
            .card { 
                border: 1px solid #334155; 
                border-radius: 8px; 
                padding: 20px; 
                margin: 20px 0; 
                background-color: #1e293b; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            .chat-area { 
                background: #0f172a; 
                padding: 15px; 
                border-radius: 5px; 
                margin: 10px 0; 
                border: 1px solid #334155;
            }
            .excel-upload { 
                background: linear-gradient(135deg, #0f3460, #1e40af); 
                padding: 15px; 
                border-radius: 5px; 
                border: 1px solid #3b82f6;
            }
            button { 
                background: linear-gradient(135deg, #3b82f6, #6366f1); 
                color: white; 
                padding: 10px 20px; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer; 
                transition: all 0.3s ease;
                font-weight: 500;
            }
            button:hover { 
                background: linear-gradient(135deg, #2563eb, #4f46e5); 
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
            }
            input, textarea, select { 
                width: 100%; 
                padding: 8px; 
                margin: 5px 0; 
                border: 1px solid #475569; 
                border-radius: 4px; 
                background-color: #334155; 
                color: #e2e8f0;
                transition: border-color 0.3s ease;
            }
            input:focus, textarea:focus, select:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
            }
            .response { 
                background: linear-gradient(135deg, #1e293b, #334155); 
                padding: 15px; 
                border-left: 4px solid #3b82f6; 
                margin: 10px 0; 
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                font-family: 'Courier New', monospace;
            }
            .expertise { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 15px; 
            }
            .expertise-item { 
                background: linear-gradient(135deg, #1e293b, #334155); 
                padding: 15px; 
                border-radius: 8px; 
                border: 1px solid #475569;
                transition: transform 0.3s ease;
            }
            .expertise-item:hover {
                transform: translateY(-5px);
                box-shadow: 0 5px 20px rgba(59, 130, 246, 0.2);
            }
            h1, h2, h3, h4 { color: #f1f5f9; }
            /* Scrollbar styling for dark theme */
            ::-webkit-scrollbar {
                width: 8px;
            }
            ::-webkit-scrollbar-track {
                background: #1e293b;
            }
            ::-webkit-scrollbar-thumb {
                background: #475569;
                border-radius: 4px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #64748b;
            }
            /* Loading animation */
            .loading {
                color: #3b82f6;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏢 Dato Ahmad Rahman</h1>
            <h2>Senior Finance Manager - Investment Holdings Specialist</h2>
            <p>25+ years experience • CA Malaysia • CPA • Malaysian Corporate Expert</p>
        </div>

        <div class="card">
            <h3>💬 Chat with Dato Ahmad</h3>
            <div class="chat-area">
                <textarea id="chatMessage" placeholder="Ask about financial analysis, subsidiary management, Excel analysis, Malaysian compliance, etc..." rows="3"></textarea>
                <button onclick="sendChat()">Send Message</button>
                <div id="chatResponse" class="response" style="display:none;"></div>
            </div>
        </div>

        <div class="card">
            <h3>📊 Excel File Analysis</h3>
            <div class="excel-upload">
                <p><strong>Upload your subsidiary Excel files for expert analysis</strong></p>
                <input type="file" id="excelFile" accept=".xlsx,.xls" />
                <select id="analysisType">
                    <option value="general">General Financial Review</option>
                    <option value="subsidiary_performance">Subsidiary Performance Analysis</option>
                    <option value="cash_flow">Cash Flow Analysis</option>
                    <option value="compliance_check">Compliance Review</option>
                    <option value="risk_assessment">Risk Assessment</option>
                </select>
                <textarea id="specificQuery" placeholder="Specific questions or focus areas..." rows="2"></textarea>
                <button onclick="uploadExcel()">Analyze Excel File</button>
                <div id="excelResponse" class="response" style="display:none;"></div>
            </div>
        </div>

        <div class="card">
            <h3>🎯 Areas of Expertise</h3>
            <div class="expertise">
                <div class="expertise-item">
                    <h4>📈 Investment Holdings Management</h4>
                    <p>Strategic oversight of subsidiary portfolios, performance monitoring, and value optimization</p>
                </div>
                <div class="expertise-item">
                    <h4>🇲🇾 Malaysian Compliance</h4>
                    <p>Companies Act 2016, Bursa Malaysia requirements, MFRS standards, tax regulations</p>
                </div>
                <div class="expertise-item">
                    <h4>📋 Subsidiary Analysis</h4>
                    <p>Financial performance review, consolidation, inter-company transactions, risk assessment</p>
                </div>
                <div class="expertise-item">
                    <h4>💻 Excel Financial Modeling</h4>
                    <p>Advanced Excel analysis, unstructured data processing, financial modeling and reporting</p>
                </div>
            </div>
        </div>

        <script>
            async function sendChat() {
                const message = document.getElementById('chatMessage').value;
                const responseDiv = document.getElementById('chatResponse');
                
                if (!message.trim()) return;
                
                responseDiv.style.display = 'block';
                responseDiv.innerHTML = '<div class="loading">🤖 Dato Ahmad is analyzing your query...</div>';
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            message: message,
                            agent_name: "Dato Ahmad Rahman",
                            use_rag: true
                        })
                    });
                    
                    const data = await response.json();
                    responseDiv.innerHTML = `
                        <strong>Dato Ahmad Rahman:</strong><br>
                        ${data.response.replace(/\\n/g, '<br>')}
                        <br><br>
                        <small>Response time: ${data.execution_time_ms}ms</small>
                    `;
                } catch (error) {
                    responseDiv.innerHTML = 'Error: ' + error.message;
                }
            }
            
            async function uploadExcel() {
                const fileInput = document.getElementById('excelFile');
                const analysisType = document.getElementById('analysisType').value;
                const specificQuery = document.getElementById('specificQuery').value;
                const responseDiv = document.getElementById('excelResponse');
                
                if (!fileInput.files[0]) {
                    alert('Please select an Excel file first');
                    return;
                }
                
                responseDiv.style.display = 'block';
                responseDiv.innerHTML = '<div class="loading">📊 Dato Ahmad is processing your Excel file...</div>';
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('analysis_type', analysisType);
                formData.append('specific_query', specificQuery);
                
                try {
                    const response = await fetch('/excel/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    responseDiv.innerHTML = `
                        <strong>Excel Analysis Complete:</strong><br>
                        ${data.analysis_preview.replace(/\\n/g, '<br>')}
                        <br><br>
                        <small>File: ${data.filename}</small>
                    `;
                } catch (error) {
                    responseDiv.innerHTML = 'Error processing Excel file: ' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """
    return html


@app.get("/favicon.ico")
async def favicon():
    """Return favicon to stop 404 errors."""
    return {"message": "No favicon available"}

@app.get("/health")
async def health_check():
    """Health check."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{LM_STUDIO_BASE_URL}/models")
            lm_studio_status = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        lm_studio_status = "unhealthy"
    
    return {
        "status": "healthy",
        "agent": "Dato' Ahmad Rahman - Senior Finance Manager",
        "lm_studio": lm_studio_status,
        "knowledge_base": {
            "malaysian_finance": len(rag_db["malaysian_finance"]),
            "investment_holdings": len(rag_db["investment_holdings"]), 
            "subsidiary_management": len(rag_db["subsidiary_management"])
        },
        "capabilities": [
            "Excel file analysis (upload supported)",
            "Malaysian corporate compliance advice",
            "Subsidiary performance review",
            "Financial modeling and forecasting",
            "Investment holdings management"
        ]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_with_dato_ahmad(request: ChatRequest):
    """Chat with Dato' Ahmad Rahman using REAL Excel data."""
    print(f"🎯 CHAT ENDPOINT 2 (RealExcelChatSystem) called with: {request.message}")
    start_time = time.time()

    # Import and use the REAL system
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from real_excel_chat_system import RealExcelChatSystem

    try:
        # Use REAL Excel data integration
        print("🚀 Initializing RealExcelChatSystem...")
        real_system = RealExcelChatSystem()
        print("📡 Calling chat_with_excel_data...")
        response_text = await real_system.chat_with_excel_data(request.message)
        print(f"✅ RealExcelChatSystem response: {response_text[:100]}...")

        sources_used = ["Real Excel Database", "TURN-COS-GP_RM", "PNL", "GROUP-PL_RM"]

    except Exception as e:
        # Fallback but indicate it's not using Excel data
        print(f"❌ RealExcelChatSystem error: {e}")
        import traceback
        traceback.print_exc()
        response_text = f"I apologize, I'm currently unable to access your Excel data (Error: {str(e)}). For Excel data analysis, please ensure the database is properly connected."
        sources_used = ["Error - No Excel Data Access"]
    
    execution_time = int((time.time() - start_time) * 1000)
    
    return ChatResponse(
        response=response_text,
        agent_name="Dato Ahmad Rahman", 
        execution_time_ms=execution_time,
        sources_used=sources_used
    )


@app.post("/excel/upload", response_model=ExcelUploadResponse)
async def upload_excel_file(
    file: UploadFile = File(...),
    analysis_type: str = Form("general"),
    specific_query: str = Form("")
):
    """Upload Excel file for analysis by Dato' Ahmad."""
    print(f"📋 Upload received - File: {file.filename}, Query: '{specific_query}', Type: {analysis_type}")
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
    
    try:
        # Check file size first (limit to 10MB to prevent timeouts)
        file_data = await file.read()
        if len(file_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB")
            
        file_id = str(uuid.uuid4())
        
        uploaded_files[file_id] = {
            "filename": file.filename,
            "data": file_data,
            "uploaded_at": time.time(),
            "analysis_type": analysis_type,
            "specific_query": specific_query
        }
        
        # ACTUALLY PROCESS THE EXCEL FILE WITH REAL DATA
        import tempfile
        import openpyxl
        from pathlib import Path
        
        # Save uploaded file to temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.write(file_data)
        temp_file.close()
        
        try:
            # Use the REAL Excel Chat System for intelligent analysis
            import sys
            import os
            sys.path.append(os.path.dirname(__file__))
            from real_excel_chat_system import RealExcelChatSystem

            # Initialize the real system
            real_system = RealExcelChatSystem()

            # Get intelligent analysis using the real system
            if specific_query:
                print(f"🔍 Using RealExcelChatSystem for query: {specific_query}")
                preview_response = await real_system.chat_with_excel_data(specific_query)
            else:
                # For general uploads without specific query, provide structure info
                workbook = openpyxl.load_workbook(temp_file.name, read_only=True)
                sheet_names = workbook.sheetnames
                workbook.close()

                preview_response = f"""**EXCEL FILE STRUCTURE - {file.filename}**

**Worksheets Found ({len(sheet_names)} sheets):**
{chr(10).join([f"• {name}" for name in sheet_names])}

**Dato Ahmad Rahman's Analysis:**
Your Excel file has been uploaded successfully. To get detailed analysis of specific data, please provide a query about what you're looking for.

*Try queries like "cost of sales infra-port", "division names", or "revenue figures over 500 million".*"""
            
        except Exception as e:
            preview_response = f"Error reading Excel file: {str(e)}"
        
        finally:
            # Clean up temp file
            Path(temp_file.name).unlink(missing_ok=True)
        
        return ExcelUploadResponse(
            message="Excel file uploaded successfully",
            filename=file.filename,
            status="received",
            analysis_preview=preview_response
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/excel/files")
async def list_uploaded_files():
    """List uploaded Excel files."""
    return {
        "files": [
            {
                "file_id": file_id,
                "filename": data["filename"],
                "uploaded_at": data["uploaded_at"],
                "analysis_type": data["analysis_type"]
            }
            for file_id, data in uploaded_files.items()
        ]
    }


if __name__ == "__main__":
    print("Starting Dato' Ahmad Rahman - Senior Finance Manager")
    print(f"LM Studio: {LM_STUDIO_BASE_URL}")
    print(f"Model: {LM_STUDIO_MODEL}")
    print("Specialized in Malaysian Investment Holdings")
    print("Excel Analysis Ready (Upload via web interface)")
    print("Access: http://localhost:8003")
    print("API docs: http://localhost:8003/docs")
    print("Interactive demo: http://localhost:8003/demo")
    
    uvicorn.run(app, host="0.0.0.0", port=8003)