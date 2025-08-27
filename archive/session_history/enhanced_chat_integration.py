#!/usr/bin/env python3
"""
Enhanced Chat Integration with Excel Data
Adds Excel data awareness to the finance manager demo
"""

import sqlite3
from typing import Dict, List, Any

DATABASE_PATH = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/excel_data.db"

def get_excel_context_for_chat(user_message: str) -> str:
    """Get relevant Excel data context for chat responses."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Check if we have data
        cursor.execute("SELECT COUNT(*) FROM excel_files")
        files_count = cursor.fetchone()[0]
        
        if files_count == 0:
            return "\n[Note: No processed Excel data available]"
        
        # Get file info
        cursor.execute("SELECT filename, sheets_count FROM excel_files LIMIT 1") 
        file_info = cursor.fetchone()
        
        # Get sheet names
        cursor.execute("SELECT sheet_name FROM excel_sheets")
        sheets = [row[0] for row in cursor.fetchall()]
        
        context = f"\n\n=== EXCEL DATA AVAILABLE ===\nFile: {file_info[0]}\nSheets: {', '.join(sheets)}\n"
        
        # Search for relevant data based on user query
        search_terms = user_message.lower().split()
        relevant_data = []
        
        for term in search_terms:
            if len(term) > 3:  # Skip short words
                cursor.execute("""
                    SELECT DISTINCT searchable_text, content_type 
                    FROM search_index 
                    WHERE searchable_text LIKE ? 
                    LIMIT 5
                """, (f"%{term}%",))
                
                for row in cursor.fetchall():
                    if row[0] not in [item[0] for item in relevant_data]:
                        relevant_data.append(row)
        
        if relevant_data:
            context += "Relevant data found:\n"
            for data, data_type in relevant_data[:5]:
                context += f"- {data} ({data_type})\n"
        
        # Add specific company info if asking about companies
        if any(word in user_message.lower() for word in ['company', 'companies', 'entity', 'entities', 'subsidiary']):
            cursor.execute("""
                SELECT DISTINCT searchable_text 
                FROM search_index 
                WHERE (searchable_text LIKE '%bhd%' OR searchable_text LIKE '%berhad%' 
                       OR searchable_text LIKE '%construction%' OR searchable_text LIKE '%corporation%')
                LIMIT 5
            """)
            
            entities = [row[0] for row in cursor.fetchall()]
            if entities:
                context += f"Companies/Entities: {', '.join(entities[:3])}\n"
        
        # Add financial data if asking about financials
        if any(word in user_message.lower() for word in ['revenue', 'profit', 'financial', 'performance']):
            cursor.execute("""
                SELECT DISTINCT searchable_text 
                FROM search_index 
                WHERE (searchable_text LIKE '%revenue%' OR searchable_text LIKE '%profit%' 
                       OR searchable_text LIKE '%total%' OR searchable_text LIKE '%gross%')
                LIMIT 3
            """)
            
            financial_terms = [row[0] for row in cursor.fetchall()]
            if financial_terms:
                context += f"Financial metrics: {', '.join(financial_terms)}\n"
        
        context += "=== END EXCEL DATA ===\n"
        conn.close()
        return context
        
    except Exception as e:
        return f"\n[Excel data access error: {str(e)}]"

def create_enhanced_system_prompt(user_message: str) -> str:
    """Create system prompt with Excel data context."""
    excel_context = get_excel_context_for_chat(user_message)
    
    base_prompt = """You are Dato' Ahmad Rahman, a highly experienced Senior Finance Manager with over 25 years in Malaysian investment holding companies.

BACKGROUND & CREDENTIALS:
- Chartered Accountant (CA Malaysia) and CPA
- Former Big 4 audit partner, now senior finance executive
- Expert in Bursa Malaysia listed companies and regulatory requirements
- Specialist in managing investment holdings with 10-50 subsidiaries

EXPERTISE AREAS:
- Malaysian Companies Act 2016 and corporate compliance
- Investment holdings structure and subsidiary management
- Financial consolidation under MFRS standards
- Excel-based financial analysis and modeling
- Cash flow management across subsidiary portfolios

IMPORTANT: You have access to the user's actual Excel data shown below. Use this real data to provide specific, practical insights about their investment holding company."""
    
    return base_prompt + excel_context

# Test the integration
if __name__ == "__main__":
    print("🧪 TESTING ENHANCED CHAT INTEGRATION")
    print("=" * 40)
    
    test_messages = [
        "What companies are in my Excel file?",
        "Show me the revenue data", 
        "What subsidiaries do I manage?"
    ]
    
    for message in test_messages:
        print(f"\n📋 Message: {message}")
        context = get_excel_context_for_chat(message)
        print(f"Context generated: {len(context)} characters")
        if "ABC" in context:
            print("✅ Found company data in context")
        if "revenue" in context.lower():
            print("✅ Found revenue data in context")
        print(f"Preview: {context[:200]}...")