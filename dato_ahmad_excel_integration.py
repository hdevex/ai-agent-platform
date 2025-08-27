#!/usr/bin/env python3
"""
Dato Ahmad Integration with Excel Database System
Complete integration between chat interface and processed Excel data
"""

import sqlite3
import asyncio
import httpx
from typing import List, Dict, Any

DATABASE_PATH = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/excel_data.db"
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"

class DatoAhmadExcelIntegration:
    """Integration between Dato Ahmad and Excel database."""
    
    def __init__(self):
        self.db_path = DATABASE_PATH
    
    def search_excel_data(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search processed Excel data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            results = []
            
            # Search in search index
            cursor.execute("""
                SELECT DISTINCT f.filename, s.sheet_name, si.searchable_text, si.content_type
                FROM search_index si
                JOIN excel_files f ON si.file_id = f.id
                JOIN excel_sheets s ON si.sheet_id = s.id
                WHERE si.searchable_text LIKE ?
                ORDER BY si.relevance_score DESC
                LIMIT ?
            """, (f"%{query}%", limit))
            
            for row in cursor.fetchall():
                results.append({
                    "filename": row[0],
                    "sheet": row[1],
                    "data": row[2],
                    "type": row[3]
                })
            
            # Also search specific financial data if needed
            cursor.execute("""
                SELECT DISTINCT f.filename, s.sheet_name, ed.cell_address, ed.raw_value, ed.data_type
                FROM excel_data ed
                JOIN excel_sheets s ON ed.sheet_id = s.id
                JOIN excel_files f ON s.file_id = f.id
                WHERE ed.text_value LIKE ? AND ed.numeric_value IS NOT NULL
                ORDER BY ed.numeric_value DESC
                LIMIT 5
            """, (f"%{query}%",))
            
            for row in cursor.fetchall():
                results.append({
                    "filename": row[0],
                    "sheet": row[1],
                    "cell": row[2],
                    "value": row[3],
                    "type": "numeric_data"
                })
            
            conn.close()
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def get_financial_summary(self) -> Dict[str, Any]:
        """Get financial summary from processed data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get file info
            cursor.execute("SELECT filename, sheets_count, processed_at FROM excel_files LIMIT 1")
            file_info = cursor.fetchone()
            
            # Get sheets
            cursor.execute("SELECT sheet_name FROM excel_sheets")
            sheets = [row[0] for row in cursor.fetchall()]
            
            # Get sample entities
            cursor.execute("""
                SELECT DISTINCT searchable_text 
                FROM search_index 
                WHERE content_type = 'data' 
                AND (searchable_text LIKE '%bhd%' OR searchable_text LIKE '%berhad%' OR searchable_text LIKE '%construction%')
                LIMIT 5
            """)
            entities = [row[0] for row in cursor.fetchall()]
            
            # Get sample financial terms
            cursor.execute("""
                SELECT DISTINCT searchable_text 
                FROM search_index 
                WHERE content_type = 'data' 
                AND (searchable_text LIKE '%revenue%' OR searchable_text LIKE '%profit%' OR searchable_text LIKE '%assets%')
                LIMIT 5
            """)
            financial_terms = [row[0] for row in cursor.fetchall()]
            
            # Get some numeric data
            cursor.execute("""
                SELECT ed.raw_value, ed.cell_address, s.sheet_name
                FROM excel_data ed
                JOIN excel_sheets s ON ed.sheet_id = s.id
                WHERE ed.data_type = 'number' AND ed.numeric_value > 1000000
                ORDER BY ed.numeric_value DESC
                LIMIT 5
            """)
            large_numbers = [{"value": row[0], "cell": row[1], "sheet": row[2]} for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                "file_info": {
                    "filename": file_info[0] if file_info else "No file",
                    "sheets_count": file_info[1] if file_info else 0,
                    "processed_at": file_info[2] if file_info else "Unknown"
                },
                "sheets": sheets,
                "entities": entities,
                "financial_terms": financial_terms,
                "large_numbers": large_numbers
            }
            
        except Exception as e:
            return {"error": f"Summary error: {e}"}
    
    async def chat_with_excel_context(self, user_message: str) -> str:
        """Chat with Dato Ahmad using Excel data context."""
        try:
            # Search for relevant data based on user message
            search_results = self.search_excel_data(user_message, limit=8)
            
            # Get financial summary
            summary = self.get_financial_summary()
            
            # Build context
            context = f"""DATO AHMAD RAHMAN - EXCEL DATA CONTEXT
            
File Processed: {summary['file_info']['filename']}
Sheets Available: {', '.join(summary['sheets'][:5])}
Entities Found: {', '.join(summary['entities'][:3])}
Financial Terms: {', '.join(summary['financial_terms'][:3])}

RELEVANT DATA FOR USER QUERY:"""
            
            if search_results:
                context += "\n\nSearch Results:"
                for i, result in enumerate(search_results[:5], 1):
                    if "cell" in result:
                        context += f"\n{i}. {result['sheet']} -> {result['cell']}: {result['value']}"
                    else:
                        context += f"\n{i}. {result['sheet']}: {result['data']}"
            
            if summary['large_numbers']:
                context += f"\n\nLarge Financial Values:"
                for item in summary['large_numbers'][:3]:
                    context += f"\n- {item['sheet']} [{item['cell']}]: {item['value']}"
            
            # Create chat request
            messages = [
                {
                    "role": "system",
                    "content": """You are Dato' Ahmad Rahman, Senior Finance Manager with 25+ years experience in Malaysian investment holdings. 

You have access to REAL Excel data from the user's investment holding company files. Use this data to provide specific, practical insights about their business. Reference actual numbers, entities, and sheets when possible.

Focus on:
- Malaysian corporate compliance and regulations
- Investment holding company management
- Subsidiary performance analysis
- Financial reporting and consolidation
- Excel data interpretation and insights"""
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nUser Question: {user_message}\n\nPlease provide specific insights based on the actual Excel data above."
                }
            ]
            
            # Call LM Studio
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{LM_STUDIO_BASE_URL}/chat/completions",
                    json={
                        "model": LM_STUDIO_MODEL,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 1000,
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"I apologize, but I'm having difficulty accessing the analysis system at the moment. Status: {response.status_code}"
        
        except Exception as e:
            return f"I apologize for the technical issue. Let me try to help based on general principles: {str(e)}"

async def test_integration():
    """Test the integration."""
    print("🏢 TESTING DATO AHMAD EXCEL INTEGRATION")
    print("=" * 50)
    
    integration = DatoAhmadExcelIntegration()
    
    # Test summary
    print("📊 Getting financial summary...")
    summary = integration.get_financial_summary()
    print(f"File: {summary['file_info']['filename']}")
    print(f"Sheets: {len(summary['sheets'])}")
    print(f"Entities: {summary['entities'][:3]}")
    
    # Test search
    print(f"\n🔍 Testing search for 'ABC Construction'...")
    results = integration.search_excel_data("ABC Construction")
    for result in results[:3]:
        print(f"  - {result}")
    
    # Test chat
    print(f"\n💬 Testing chat integration...")
    test_questions = [
        "What companies are in my Excel file?",
        "Show me the revenue figures",
        "What is the financial performance summary?"
    ]
    
    for question in test_questions:
        print(f"\nQ: {question}")
        response = await integration.chat_with_excel_context(question)
        print(f"A: {response[:200]}{'...' if len(response) > 200 else ''}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_integration())