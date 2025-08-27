"""
Direct Excel Analysis Script for Dato' Ahmad Rahman
Analyzes your specific Excel file: C:\\Users\\nvntr\\Documents\\ai_agent_platform\\data\\input\\multi_sheet.xlsx
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path

# Add current directory for imports
sys.path.append(os.path.dirname(__file__))

import httpx

# Your LM Studio configuration
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"

# Path to your Excel file
EXCEL_FILE_PATH = r"C:\Users\nvntr\Documents\ai_agent_platform\data\input\multi_sheet.xlsx"
LOCAL_EXCEL_PATH = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/data/input/multi_sheet.xlsx"


async def call_lm_studio(messages):
    """Call your LM Studio for analysis."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{LM_STUDIO_BASE_URL}/chat/completions",
                json={
                    "model": LM_STUDIO_MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 3000,
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


def analyze_excel_structure():
    """Analyze the structure of your Excel file without pandas."""
    try:
        # Try to import pandas for detailed analysis
        import pandas as pd
        import openpyxl
        
        print("📊 Analyzing your Excel file with full capabilities...")
        
        # Read the Excel file
        excel_file = pd.ExcelFile(LOCAL_EXCEL_PATH)
        
        analysis = {
            "filename": "multi_sheet.xlsx",
            "file_path": EXCEL_FILE_PATH,
            "sheets": {},
            "summary": {
                "total_sheets": len(excel_file.sheet_names),
                "sheet_names": excel_file.sheet_names
            }
        }
        
        print(f"📋 Found {len(excel_file.sheet_names)} sheets: {', '.join(excel_file.sheet_names)}")
        
        # Analyze each sheet
        for i, sheet_name in enumerate(excel_file.sheet_names):
            print(f"   🔍 Analyzing sheet {i+1}: '{sheet_name}'")
            
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                
                # Get basic info
                rows, cols = df.shape
                
                # Sample the first 10 rows and convert to readable format
                sample_data = []
                for idx in range(min(10, rows)):
                    row_data = []
                    for col_idx in range(min(10, cols)):
                        cell_value = df.iloc[idx, col_idx]
                        if pd.isna(cell_value):
                            row_data.append("")
                        else:
                            row_data.append(str(cell_value))
                    sample_data.append(row_data)
                
                # Look for financial keywords
                financial_indicators = []
                malaysian_entities = []
                
                # Scan all cells for keywords
                df_str = df.astype(str).values.flatten()
                for cell_value in df_str:
                    cell_lower = str(cell_value).lower()
                    
                    # Financial terms
                    if any(term in cell_lower for term in ['revenue', 'profit', 'loss', 'assets', 'liabilities', 'cash', 'expenses', 'rm', 'ringgit']):
                        if cell_value not in financial_indicators and len(financial_indicators) < 20:
                            financial_indicators.append(str(cell_value)[:50])
                    
                    # Malaysian business entities
                    if any(term in cell_lower for term in ['sdn bhd', 'berhad', 'bhd', 'malaysia']):
                        if cell_value not in malaysian_entities and len(malaysian_entities) < 10:
                            malaysian_entities.append(str(cell_value)[:50])
                
                analysis["sheets"][sheet_name] = {
                    "dimensions": {"rows": rows, "columns": cols},
                    "sample_data": sample_data[:5],  # First 5 rows for preview
                    "financial_indicators": list(set(financial_indicators)),
                    "malaysian_entities": list(set(malaysian_entities)),
                    "non_empty_cells": int((~pd.isna(df)).sum().sum()),
                    "has_merged_cells": "Cannot detect merged cells in pandas"
                }
                
            except Exception as e:
                analysis["sheets"][sheet_name] = {"error": f"Error reading sheet: {str(e)}"}
        
        return analysis
        
    except ImportError:
        print("⚠️  Pandas/openpyxl not available. Providing basic file info...")
        return {
            "filename": "multi_sheet.xlsx",
            "file_path": EXCEL_FILE_PATH,
            "message": "File detected but detailed analysis requires pandas/openpyxl installation",
            "recommendation": "Upload file via web interface at http://localhost:8003/demo"
        }


async def get_dato_ahmad_analysis(excel_analysis):
    """Get Dato' Ahmad Rahman's expert analysis of your Excel file."""
    
    # Prepare the context
    context = f"""EXCEL FILE ANALYSIS REQUEST

File: {excel_analysis['filename']}
Location: {excel_analysis['file_path']}

"""
    
    if 'sheets' in excel_analysis:
        context += f"Total Sheets: {excel_analysis['summary']['total_sheets']}\n"
        context += f"Sheet Names: {', '.join(excel_analysis['summary']['sheet_names'])}\n\n"
        
        for sheet_name, sheet_data in excel_analysis['sheets'].items():
            if 'error' not in sheet_data:
                context += f"SHEET: {sheet_name}\n"
                context += f"- Dimensions: {sheet_data['dimensions']['rows']} rows × {sheet_data['dimensions']['columns']} columns\n"
                context += f"- Non-empty cells: {sheet_data['non_empty_cells']}\n"
                
                if sheet_data['financial_indicators']:
                    context += f"- Financial terms found: {', '.join(sheet_data['financial_indicators'][:10])}\n"
                
                if sheet_data['malaysian_entities']:
                    context += f"- Malaysian entities: {', '.join(sheet_data['malaysian_entities'])}\n"
                
                if sheet_data['sample_data']:
                    context += "- Sample data (first few rows):\n"
                    for i, row in enumerate(sheet_data['sample_data'][:3]):
                        context += f"  Row {i+1}: {' | '.join(row[:5])}\n"
                
                context += "\n"
    
    # Dato' Ahmad's analysis prompt
    prompt = f"""As Dato' Ahmad Rahman, Senior Finance Manager with 25+ years experience in Malaysian investment holdings, please analyze this Excel file structure and provide your expert recommendations.

{context}

Based on this Excel file structure, please provide:

1. **INITIAL ASSESSMENT**: What type of financial document is this likely to be?

2. **SHEET ANALYSIS**: Analysis of each sheet and its probable purpose

3. **DATA QUALITY REVIEW**: Assessment of data organization and potential issues

4. **MALAYSIAN COMPLIANCE PERSPECTIVE**: Any regulatory or compliance considerations

5. **RECOMMENDED APPROACH**: Step-by-step plan for extracting meaningful financial insights

6. **RED FLAGS & CONCERNS**: Potential issues or areas needing attention

7. **NEXT STEPS**: Specific actions for thorough financial analysis

Please provide practical, actionable advice as you would for a fellow finance professional managing subsidiaries in Malaysia."""

    # Get Dato' Ahmad's analysis
    messages = [
        {
            "role": "system", 
            "content": """You are Dato' Ahmad Rahman, Senior Finance Manager with 25+ years in Malaysian investment holdings. 

Provide detailed, professional analysis with:
- Practical insights from Malaysian business experience
- Specific Excel handling techniques
- Regulatory compliance considerations
- Risk assessment from a senior finance perspective
- Actionable recommendations

Use your expertise in Companies Act 2016, Bursa Malaysia requirements, and subsidiary management."""
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    print("\n💭 Dato' Ahmad is analyzing your Excel file...")
    analysis = await call_lm_studio(messages)
    return analysis


async def main():
    print("🏢 DATO' AHMAD RAHMAN - EXCEL FILE ANALYSIS")
    print("=" * 60)
    print(f"📁 Analyzing: {EXCEL_FILE_PATH}")
    print(f"🤖 Using LM Studio: {LM_STUDIO_BASE_URL}")
    print()
    
    # Check if file exists
    if not os.path.exists(LOCAL_EXCEL_PATH):
        print("❌ Excel file not found!")
        print(f"Expected location: {LOCAL_EXCEL_PATH}")
        return
    
    print("✅ Excel file found!")
    
    # Analyze Excel structure
    print("\n📊 ANALYZING EXCEL STRUCTURE...")
    excel_analysis = analyze_excel_structure()
    
    # Get Dato' Ahmad's expert analysis
    print("\n👔 DATO' AHMAD'S EXPERT ANALYSIS:")
    print("-" * 40)
    
    dato_analysis = await get_dato_ahmad_analysis(excel_analysis)
    print(dato_analysis)
    
    print("\n" + "=" * 60)
    print("📋 ANALYSIS COMPLETE")
    print(f"💬 For interactive analysis, visit: http://localhost:8003/demo")
    print(f"📤 Upload your Excel file there for detailed processing")


if __name__ == "__main__":
    asyncio.run(main())