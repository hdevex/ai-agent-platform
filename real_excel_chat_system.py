#!/usr/bin/env python3
"""
REAL Excel Chat System - No Fake Responses
Connect chat directly to Excel database with intelligent query processing
"""

import sqlite3
import re
import asyncio
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import httpx

# Configuration
DATABASE_PATH = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/excel_data.db"
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"

@dataclass
class QueryContext:
    """Structured query context for efficient token usage."""
    user_question: str
    query_type: str
    target_sheets: List[str]
    relevant_data: List[Dict[str, Any]]
    data_summary: str
    token_count_estimate: int

class IntelligentQueryAnalyzer:
    """Analyzes user queries without hardcoding - truly dynamic."""
    
    def __init__(self):
        # Dynamic patterns - not hardcoded responses
        self.entity_patterns = [
            r'\b\w+\s+(sdn\s+bhd|berhad|bhd|corporation|holdings|company|construction)\b',
            r'\b(abc|xyz|[A-Z]{2,})\s+(construction|corporation|holdings)\b'
        ]
        
        self.financial_patterns = [
            r'\b(revenue|profit|loss|income|expense|cost|total|gross|net)\b',
            r'\b(assets|liabilities|equity|cash|debt)\b',
            r'\b(balance|sheet|statement|report)\b'
        ]
        
        self.numeric_patterns = [
            r'\b(greater|less|more|above|below|than)\s+\d+',
            r'\b(sum|total|average|maximum|minimum|count)\b',
            r'\b\d+\s*(million|thousand|billion|k|m|b)\b'
        ]
    
    def analyze_query(self, user_question: str) -> Dict[str, Any]:
        """Dynamically analyze what user is asking for."""
        question_lower = user_question.lower()
        
        analysis = {
            "original_query": user_question,
            "intent_scores": {},
            "target_sheets": [],
            "data_types_needed": [],
            "filters_required": [],
            "output_format": "conversational"
        }
        
        # Detect intent dynamically
        if any(word in question_lower for word in ['company', 'companies', 'entity', 'entities', 'name']):
            analysis["intent_scores"]["entity_search"] = 1.0
            analysis["data_types_needed"].append("text")
        
        if any(word in question_lower for word in ['revenue', 'profit', 'financial', 'money', 'amount']):
            analysis["intent_scores"]["financial_analysis"] = 1.0  
            analysis["data_types_needed"].append("numeric")
        
        if any(word in question_lower for word in ['count', 'how many', 'number of', 'total']):
            analysis["intent_scores"]["aggregation"] = 1.0
            analysis["data_types_needed"].append("count")
        
        if any(word in question_lower for word in ['sheet', 'worksheet', 'tab']):
            analysis["intent_scores"]["sheet_analysis"] = 1.0
        
        # Extract mentioned sheets dynamically
        # This will work with ANY sheet names, not hardcoded ones
        potential_sheets = re.findall(r'\b[A-Z][A-Z0-9_-]+\b', user_question)
        analysis["target_sheets"] = potential_sheets
        
        # Extract numeric filters dynamically
        numeric_filters = re.findall(r'(greater|less|more|above|below)\s+than?\s*(\d+(?:\.\d+)?)\s*(million|thousand|k|m|b)?', question_lower)
        for operator, value, unit in numeric_filters:
            multiplier = {"million": 1000000, "thousand": 1000, "k": 1000, "m": 1000000, "b": 1000000000}.get(unit, 1)
            analysis["filters_required"].append({
                "type": "numeric",
                "operator": operator,
                "value": float(value) * multiplier
            })
        
        return analysis

class TokenEfficientDataRetriever:
    """Retrieves only relevant data to stay within token limits."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def get_relevant_data(self, query_analysis: Dict[str, Any], max_tokens: int = 1500) -> List[Dict[str, Any]]:
        """Get only the data needed for the specific query."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            relevant_data = []
            estimated_tokens = 0
            
            # Get file and sheet info first (minimal tokens)
            cursor.execute("""
                SELECT f.filename, s.sheet_name, s.rows_count, s.columns_count
                FROM excel_files f 
                JOIN excel_sheets s ON f.id = s.file_id
            """)
            
            sheets_info = {}
            for filename, sheet_name, rows, cols in cursor.fetchall():
                sheets_info[sheet_name] = {
                    "filename": filename,
                    "rows": rows, 
                    "columns": cols
                }
            
            # Filter sheets based on query
            target_sheets = query_analysis.get("target_sheets", [])
            if target_sheets:
                # User mentioned specific sheets
                sheets_to_search = [s for s in sheets_info.keys() if any(target in s for target in target_sheets)]
                # If no sheets matched, search all sheets (fallback)
                if not sheets_to_search:
                    sheets_to_search = list(sheets_info.keys())
            else:
                # Search all sheets but prioritize by size (smaller first for efficiency)
                sheets_to_search = sorted(sheets_info.keys(), key=lambda s: sheets_info[s]["rows"])
            
            # Get data based on intent
            intent_scores = query_analysis.get("intent_scores", {})

            # If no intent has high confidence (>0.5), default to entity_search for company queries
            if not any(score >= 0.5 for score in intent_scores.values()) and any(word in user_question.lower() for word in ['company', 'companies', 'name', 'names', 'entity', 'entities']):
                intent_scores['entity_search'] = 1.0

            for intent, score in intent_scores.items():
                if score < 0.5:
                    continue

                if intent == "entity_search":
                    # Find entities (companies, names, etc.)
                    for sheet in sheets_to_search[:3]:  # Limit to 3 sheets for efficiency
                        cursor.execute("""
                            SELECT si.searchable_text, s.sheet_name
                            FROM search_index si
                            JOIN excel_sheets s ON si.sheet_id = s.id
                            WHERE s.sheet_name = ? 
                            AND (si.searchable_text LIKE '%bhd%' OR si.searchable_text LIKE '%berhad%' 
                                OR si.searchable_text LIKE '%corporation%' OR si.searchable_text LIKE '%company%'
                                OR si.searchable_text LIKE '%construction%' OR si.searchable_text LIKE '%holdings%')
                            LIMIT 10
                        """, (sheet,))
                        
                        for text, sheet_name in cursor.fetchall():
                            if estimated_tokens < max_tokens:
                                relevant_data.append({
                                    "type": "entity",
                                    "sheet": sheet_name,
                                    "data": text,
                                    "context": f"Entity found in {sheet_name}"
                                })
                                estimated_tokens += len(text.split()) * 1.3  # Rough token estimate
                
                elif intent == "financial_analysis":
                    # Find financial data
                    for sheet in sheets_to_search[:3]:
                        cursor.execute("""
                            SELECT ed.raw_value, ed.cell_address, s.sheet_name, ed.numeric_value
                            FROM excel_data ed
                            JOIN excel_sheets s ON ed.sheet_id = s.id  
                            WHERE s.sheet_name = ?
                            AND ed.data_type = 'number'
                            AND ed.numeric_value IS NOT NULL
                            ORDER BY ed.numeric_value DESC
                            LIMIT 15
                        """, (sheet,))
                        
                        for raw_value, cell_address, sheet_name, numeric_value in cursor.fetchall():
                            if estimated_tokens < max_tokens:
                                # Apply numeric filters if specified
                                include_data = True
                                for filter_req in query_analysis.get("filters_required", []):
                                    if filter_req["type"] == "numeric":
                                        op = filter_req["operator"]
                                        threshold = filter_req["value"]
                                        if op in ["greater", "above", "more"] and numeric_value <= threshold:
                                            include_data = False
                                        elif op in ["less", "below"] and numeric_value >= threshold:
                                            include_data = False
                                
                                if include_data:
                                    relevant_data.append({
                                        "type": "financial",
                                        "sheet": sheet_name,
                                        "cell": cell_address,
                                        "value": raw_value,
                                        "numeric_value": numeric_value,
                                        "context": f"Financial figure in {sheet_name}[{cell_address}]"
                                    })
                                    estimated_tokens += 20  # Rough estimate for numeric data
                
                elif intent == "sheet_analysis":
                    # Return sheet structure info
                    for sheet_name, info in sheets_info.items():
                        relevant_data.append({
                            "type": "sheet_info",
                            "sheet": sheet_name,
                            "data": f"{info['filename']} - {sheet_name}: {info['rows']} rows × {info['columns']} columns",
                            "context": "Sheet structure information"
                        })
                        estimated_tokens += 15
            
            conn.close()
            return relevant_data[:50]  # Hard limit to prevent token overflow
            
        except Exception as e:
            return [{"type": "error", "data": f"Database error: {str(e)}", "context": "System error"}]

class RealExcelChatSystem:
    """The complete REAL system - no fake responses."""
    
    def __init__(self):
        self.query_analyzer = IntelligentQueryAnalyzer()
        self.data_retriever = TokenEfficientDataRetriever()
    
    def build_context(self, relevant_data: List[Dict[str, Any]], user_question: str) -> str:
        """Build minimal, focused context for LM Studio."""
        context_parts = [f"USER QUESTION: {user_question}", "", "RELEVANT DATA FROM EXCEL FILES:"]
        
        # Group data by type for efficient presentation
        entities = [d for d in relevant_data if d["type"] == "entity"]
        financial = [d for d in relevant_data if d["type"] == "financial"]
        sheets = [d for d in relevant_data if d["type"] == "sheet_info"]
        
        if entities:
            context_parts.append("COMPANIES/ENTITIES:")
            for entity in entities[:8]:
                context_parts.append(f"- {entity['data']} (from {entity['sheet']})")
        
        if financial:
            context_parts.append("\nFINANCIAL DATA:")
            for fin in financial[:10]:
                context_parts.append(f"- {fin['sheet']}[{fin['cell']}]: {fin['value']}")
        
        if sheets:
            context_parts.append("\nSHEET STRUCTURE:")
            for sheet in sheets:
                context_parts.append(f"- {sheet['data']}")
        
        context = "\n".join(context_parts)
        
        # Ensure we stay within reasonable token limits
        if len(context) > 6000:  # Rough character limit
            context = context[:6000] + "\n[Data truncated for efficiency]"
        
        return context
    
    async def chat_with_excel_data(self, user_question: str) -> str:
        """Process user question with REAL Excel data - no fakes."""
        try:
            # Step 1: Analyze what user is actually asking
            query_analysis = self.query_analyzer.analyze_query(user_question)
            
            # Step 2: Get only relevant data 
            relevant_data = self.data_retriever.get_relevant_data(query_analysis)
            
            if not relevant_data:
                return "I don't have Excel data loaded yet. Please ensure your Excel files have been processed into the database."
            
            # Step 3: Build efficient context
            context = self.build_context(relevant_data, user_question)
            
            # Step 4: Call LM Studio with focused context
            response = await self.call_lm_studio_with_context(context, user_question)
            
            return response
            
        except Exception as e:
            return f"Error processing your question: {str(e)}"
    
    async def call_lm_studio_with_context(self, context: str, user_question: str) -> str:
        """Call LM Studio with efficient context."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are Dato' Ahmad Rahman, a senior Malaysian finance manager analyzing REAL Excel data from investment holding companies.

IMPORTANT: The data provided is REAL extracted from actual Excel files. Answer based on the specific data shown.

Guidelines:
- Reference specific sheet names, cell addresses, and values from the data
- Apply Malaysian financial regulations and accounting standards
- Provide practical insights based on the actual numbers
- If data is incomplete, say so and suggest what additional data would help
- Be concise but thorough - you're speaking to business professionals"""
                },
                {
                    "role": "user",
                    "content": context
                }
            ]
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{LM_STUDIO_BASE_URL}/chat/completions",
                    json={
                        "model": LM_STUDIO_MODEL,
                        "messages": messages,
                        "temperature": 0.2,  # Low temperature for factual analysis
                        "max_tokens": 800,   # Controlled response length
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"LM Studio error: HTTP {response.status_code}"
                    
        except Exception as e:
            return f"Error calling LM Studio: {str(e)}"

# Test the REAL system
async def test_real_system():
    """Test with various query types."""
    system = RealExcelChatSystem()
    
    test_queries = [
        "What companies are mentioned in TURN-COS-GP_RM?",
        "Find revenue figures greater than 1 million",
        "List all the worksheets in the Excel files",
        "Show me financial data from PNL sheet",
        "Which sheets contain construction companies?"
    ]
    
    print("🧪 TESTING REAL EXCEL CHAT SYSTEM")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        response = await system.chat_with_excel_data(query)
        print(f"📊 Response: {response[:200]}{'...' if len(response) > 200 else ''}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_real_system())