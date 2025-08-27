"""
Real Excel File Analyzer for Dato' Ahmad Rahman
This script reads your actual multi_sheet.xlsx file and provides real data to the AI agent.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Import required libraries
import pandas as pd
import openpyxl
EXCEL_SUPPORT = True
print("✅ Excel processing libraries loaded successfully")

import httpx

# Your file path
EXCEL_FILE_PATH = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/data/input/multi_sheet.xlsx"
LM_STUDIO_BASE_URL = "http://192.168.101.70:1234/v1"
LM_STUDIO_MODEL = "openai/gpt-oss-20b"


async def call_lm_studio(messages):
    """Call your LM Studio."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{LM_STUDIO_BASE_URL}/chat/completions",
                json={
                    "model": LM_STUDIO_MODEL,
                    "messages": messages,
                    "temperature": 0.1,  # Very low for precise analysis
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
        return f"Error: {str(e)}"


def read_real_excel_data():
    """Read your actual Excel file and extract real data."""
    if not EXCEL_SUPPORT:
        return {"error": "Cannot read Excel files without pandas and openpyxl"}
    
    if not os.path.exists(EXCEL_FILE_PATH):
        return {"error": f"File not found: {EXCEL_FILE_PATH}"}
    
    try:
        print(f"📖 Reading your actual Excel file: {EXCEL_FILE_PATH}")
        
        # Read the Excel file
        excel_file = pd.ExcelFile(EXCEL_FILE_PATH)
        
        real_data = {
            "filename": "multi_sheet.xlsx",
            "total_sheets": len(excel_file.sheet_names),
            "sheet_names": excel_file.sheet_names,
            "sheets_data": {}
        }
        
        print(f"📋 Found {len(excel_file.sheet_names)} sheets: {excel_file.sheet_names}")
        
        # Read each sheet and extract REAL data
        for sheet_name in excel_file.sheet_names:
            print(f"   🔍 Reading sheet: '{sheet_name}'")
            
            try:
                # Read the sheet
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                rows, cols = df.shape
                
                # Extract actual data (first 15 rows for analysis)
                actual_data = []
                for row_idx in range(min(15, rows)):
                    row_data = {}
                    for col_idx in range(min(15, cols)):
                        col_name = f"Col_{col_idx}" if col_idx >= len(df.columns) else str(df.columns[col_idx])
                        cell_value = df.iloc[row_idx, col_idx]
                        
                        if pd.isna(cell_value):
                            row_data[col_name] = ""
                        elif isinstance(cell_value, (int, float)):
                            row_data[col_name] = cell_value
                        else:
                            row_data[col_name] = str(cell_value)[:100]  # Limit text length
                    
                    actual_data.append(row_data)
                
                # Find numerical columns
                numeric_columns = []
                for col in df.columns:
                    if df[col].dtype in ['int64', 'float64']:
                        numeric_data = df[col].dropna()
                        if len(numeric_data) > 0:
                            numeric_columns.append({
                                "column": str(col),
                                "sum": float(numeric_data.sum()),
                                "mean": float(numeric_data.mean()),
                                "max": float(numeric_data.max()),
                                "min": float(numeric_data.min()),
                                "count": int(len(numeric_data))
                            })
                
                # Find text patterns (Malaysian business terms, financial terms)
                text_patterns = {
                    "malaysian_entities": [],
                    "financial_terms": [],
                    "dates": [],
                    "currencies": []
                }
                
                # Scan all text data
                for col in df.columns:
                    col_data = df[col].astype(str).str.lower()
                    
                    # Malaysian business entities
                    malaysian_matches = col_data[col_data.str.contains('sdn bhd|berhad|bhd|malaysia', na=False)]
                    for match in malaysian_matches.head(5):  # Top 5 matches
                        if len(match) < 200:  # Reasonable length
                            text_patterns["malaysian_entities"].append(match)
                    
                    # Financial terms
                    financial_matches = col_data[col_data.str.contains('revenue|profit|loss|assets|cash|rm |ringgit', na=False)]
                    for match in financial_matches.head(5):
                        if len(match) < 100:
                            text_patterns["financial_terms"].append(match)
                    
                    # Currency mentions
                    currency_matches = col_data[col_data.str.contains('rm|ringgit|usd|sgd', na=False)]
                    for match in currency_matches.head(3):
                        if len(match) < 50:
                            text_patterns["currencies"].append(match)
                
                real_data["sheets_data"][sheet_name] = {
                    "dimensions": {"rows": rows, "columns": cols},
                    "column_names": [str(col) for col in df.columns[:10]],  # First 10 column names
                    "actual_data": actual_data[:10],  # First 10 rows of actual data
                    "numeric_columns": numeric_columns,
                    "text_patterns": text_patterns,
                    "non_empty_cells": int((~pd.isna(df)).sum().sum()),
                    "data_types": {str(col): str(dtype) for col, dtype in df.dtypes.head(10).items()}
                }
                
            except Exception as e:
                real_data["sheets_data"][sheet_name] = {"error": f"Error reading sheet: {str(e)}"}
        
        return real_data
        
    except Exception as e:
        return {"error": f"Failed to read Excel file: {str(e)}"}


async def get_real_analysis_from_dato_ahmad(real_excel_data):
    """Get Dato' Ahmad's analysis based on your actual Excel data."""
    
    # Build detailed context with REAL data
    context = f"""REAL EXCEL FILE ANALYSIS - ACTUAL DATA FROM USER'S FILE

File: multi_sheet.xlsx
Total Sheets: {real_excel_data['total_sheets']}
Sheet Names: {', '.join(real_excel_data['sheet_names'])}

"""
    
    # Add real data from each sheet
    for sheet_name, sheet_data in real_excel_data['sheets_data'].items():
        if 'error' not in sheet_data:
            context += f"\n=== SHEET: {sheet_name} ===\n"
            context += f"Dimensions: {sheet_data['dimensions']['rows']} rows × {sheet_data['dimensions']['columns']} columns\n"
            context += f"Column Names: {', '.join(sheet_data['column_names'])}\n"
            
            # Add actual data samples
            if sheet_data['actual_data']:
                context += "ACTUAL DATA SAMPLE (Real data from user's file):\n"
                for i, row in enumerate(sheet_data['actual_data'][:5]):
                    context += f"Row {i+1}: "
                    row_items = []
                    for key, value in list(row.items())[:5]:  # First 5 columns per row
                        row_items.append(f"{key}={value}")
                    context += " | ".join(row_items) + "\n"
            
            # Add numeric analysis
            if sheet_data['numeric_columns']:
                context += "NUMERIC COLUMNS ANALYSIS:\n"
                for num_col in sheet_data['numeric_columns'][:5]:
                    context += f"- {num_col['column']}: Sum={num_col['sum']}, Mean={num_col['mean']:.2f}, Range=[{num_col['min']}-{num_col['max']}]\n"
            
            # Add text patterns found
            if any(sheet_data['text_patterns'].values()):
                context += "TEXT PATTERNS FOUND:\n"
                if sheet_data['text_patterns']['malaysian_entities']:
                    context += f"Malaysian entities: {', '.join(sheet_data['text_patterns']['malaysian_entities'][:3])}\n"
                if sheet_data['text_patterns']['financial_terms']:
                    context += f"Financial terms: {', '.join(sheet_data['text_patterns']['financial_terms'][:3])}\n"
                if sheet_data['text_patterns']['currencies']:
                    context += f"Currencies mentioned: {', '.join(sheet_data['text_patterns']['currencies'])}\n"
            
            context += f"Non-empty cells: {sheet_data['non_empty_cells']}\n"
            context += "\n"
    
    # Dato' Ahmad's real analysis prompt
    prompt = f"""As Dato' Ahmad Rahman, I am analyzing the USER'S ACTUAL Excel file data shown above. This is REAL data from their multi_sheet.xlsx file, not simulated data.

Based on this REAL data analysis, I need to provide:

1. **REAL DATA ASSESSMENT**: What do I see in the actual data?
2. **SHEET-BY-SHEET ANALYSIS**: Analysis of each sheet based on real column names and data
3. **FINANCIAL INSIGHTS**: What financial information can be extracted from the real data?
4. **MALAYSIAN COMPLIANCE**: Any compliance issues based on actual data patterns
5. **ACTIONABLE RECOMMENDATIONS**: Specific next steps for this particular Excel file
6. **DATA EXTRACTION PLAN**: How to get the specific information the user needs for their board report

Please analyze the ACTUAL data shown above and provide practical guidance specific to what's really in their file.

Remember: This is real data from their investment holding company Excel file, not examples or simulations.

{context}

SPECIFIC FOCUS: Help the user extract meaningful financial metrics and prepare their quarterly board report using this actual data."""

    messages = [
        {
            "role": "system",
            "content": """You are Dato' Ahmad Rahman, analyzing REAL Excel data from a user's actual investment holding company file. 

Provide specific, actionable analysis based on the actual data shown, not generic advice. Reference specific sheet names, column names, and data values you can see in the real data provided."""
        },
        {
            "role": "user", 
            "content": prompt
        }
    ]
    
    print("\n💭 Dato' Ahmad is analyzing your REAL Excel data...")
    analysis = await call_lm_studio(messages)
    return analysis


async def main():
    print("🏢 DATO' AHMAD RAHMAN - REAL EXCEL FILE ANALYSIS")
    print("=" * 60)
    print(f"📁 Reading your actual file: {EXCEL_FILE_PATH}")
    print()
    
    # Read real Excel data
    print("📊 EXTRACTING REAL DATA FROM YOUR EXCEL FILE...")
    real_data = read_real_excel_data()
    
    if 'error' in real_data:
        print(f"❌ Error: {real_data['error']}")
        if not EXCEL_SUPPORT:
            print("\n💡 To analyze your actual Excel file, install pandas and openpyxl:")
            print("   pip install pandas openpyxl")
        return
    
    print(f"✅ Successfully read {real_data['total_sheets']} sheets with real data!")
    
    # Get Dato' Ahmad's analysis of real data
    print("\n👔 DATO' AHMAD'S ANALYSIS OF YOUR REAL DATA:")
    print("-" * 50)
    
    analysis = await get_real_analysis_from_dato_ahmad(real_data)
    print(analysis)
    
    print("\n" + "=" * 60)
    print("📋 REAL DATA ANALYSIS COMPLETE")
    print("💬 This analysis is based on your actual Excel file content")


if __name__ == "__main__":
    asyncio.run(main())