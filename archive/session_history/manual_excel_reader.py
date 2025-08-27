"""
Manual Excel Reader for Dato' Ahmad Rahman
Reads Excel file using basic Python libraries and provides real data to analyze.
"""

import sys
import os
import asyncio
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import httpx

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
                    "temperature": 0.1,
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


def read_excel_with_zipfile():
    """Read Excel file structure using zipfile (works without pandas)."""
    if not os.path.exists(EXCEL_FILE_PATH):
        return {"error": f"File not found: {EXCEL_FILE_PATH}"}
    
    try:
        print(f"📖 Reading Excel file structure: {EXCEL_FILE_PATH}")
        
        # Excel files are zip archives
        with zipfile.ZipFile(EXCEL_FILE_PATH, 'r') as excel_zip:
            file_list = excel_zip.namelist()
            
            # Find sheet names from workbook.xml
            workbook_data = None
            if 'xl/workbook.xml' in file_list:
                with excel_zip.open('xl/workbook.xml') as f:
                    workbook_data = f.read().decode('utf-8')
            
            # Get sheet information
            sheet_info = {}
            worksheet_files = [f for f in file_list if f.startswith('xl/worksheets/')]
            
            print(f"📋 Found Excel structure with {len(worksheet_files)} worksheet files")
            
            # Extract some worksheet data
            for i, ws_file in enumerate(worksheet_files[:5]):  # Limit to first 5 sheets
                sheet_name = f"Sheet_{i+1}"  # Default name
                
                try:
                    with excel_zip.open(ws_file) as f:
                        sheet_xml = f.read().decode('utf-8')
                        
                    # Parse basic sheet structure
                    root = ET.fromstring(sheet_xml)
                    
                    # Count rows and cells
                    rows = root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
                    cells = root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c')
                    
                    # Extract some cell values
                    cell_values = []
                    for cell in cells[:20]:  # First 20 cells
                        value_elem = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                        if value_elem is not None:
                            cell_values.append(value_elem.text)
                    
                    sheet_info[sheet_name] = {
                        "worksheet_file": ws_file,
                        "estimated_rows": len(rows),
                        "estimated_cells": len(cells),
                        "sample_cell_values": cell_values[:10],  # First 10 values
                    }
                    
                except Exception as e:
                    sheet_info[sheet_name] = {"error": f"Error reading sheet: {str(e)}"}
            
            # Look for shared strings (text values)
            shared_strings = []
            if 'xl/sharedStrings.xml' in file_list:
                try:
                    with excel_zip.open('xl/sharedStrings.xml') as f:
                        strings_xml = f.read().decode('utf-8')
                    
                    strings_root = ET.fromstring(strings_xml)
                    string_items = strings_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                    
                    for item in string_items[:50]:  # First 50 strings
                        if item.text:
                            shared_strings.append(item.text[:100])  # Limit length
                            
                except Exception as e:
                    shared_strings = [f"Error reading strings: {str(e)}"]
            
            return {
                "filename": "multi_sheet.xlsx",
                "file_structure": {
                    "total_files": len(file_list),
                    "worksheet_files": len(worksheet_files),
                    "has_shared_strings": 'xl/sharedStrings.xml' in file_list,
                    "has_workbook": 'xl/workbook.xml' in file_list
                },
                "sheets": sheet_info,
                "shared_strings_sample": shared_strings[:20],  # First 20 strings
                "raw_workbook_snippet": workbook_data[:1000] if workbook_data else None
            }
            
    except Exception as e:
        return {"error": f"Failed to read Excel file: {str(e)}"}


async def analyze_excel_structure_with_dato_ahmad(excel_data):
    """Get Dato' Ahmad's analysis based on Excel file structure."""
    
    if 'error' in excel_data:
        context = f"ERROR: {excel_data['error']}"
    else:
        context = f"""REAL EXCEL FILE STRUCTURE ANALYSIS

File: {excel_data['filename']}
File Structure:
- Total files in Excel archive: {excel_data['file_structure']['total_files']}
- Worksheet files found: {excel_data['file_structure']['worksheet_files']}
- Has shared strings: {excel_data['file_structure']['has_shared_strings']}
- Has workbook structure: {excel_data['file_structure']['has_workbook']}

WORKSHEET ANALYSIS:
"""
        
        for sheet_name, sheet_data in excel_data['sheets'].items():
            if 'error' not in sheet_data:
                context += f"""
{sheet_name}:
- Estimated rows: {sheet_data['estimated_rows']}
- Estimated cells: {sheet_data['estimated_cells']}
- Sample values: {', '.join(sheet_data['sample_cell_values'])}
"""
        
        if excel_data['shared_strings_sample']:
            context += f"\nTEXT CONTENT SAMPLE (from shared strings):\n"
            context += '\n'.join([f"- {s}" for s in excel_data['shared_strings_sample'][:10]])
    
    prompt = f"""As Dato' Ahmad Rahman, I'm analyzing the structure of the user's ACTUAL Excel file. While I cannot see the detailed cell contents without pandas/openpyxl libraries, I can analyze the file structure and provide guidance.

{context}

Based on this structural analysis of the user's REAL Excel file, please provide:

1. **FILE STRUCTURE ASSESSMENT**: What can we determine from the Excel file structure?
2. **DATA ORGANIZATION INSIGHTS**: What do the worksheet structure and text samples suggest?
3. **RECOMMENDED APPROACH**: How should we proceed to get the data we need?
4. **ALTERNATIVE SOLUTIONS**: Ways to analyze this file without full pandas support
5. **PRACTICAL NEXT STEPS**: Specific actions for the user

Please provide practical advice for analyzing this actual Excel file."""

    messages = [
        {
            "role": "system",
            "content": "You are Dato' Ahmad Rahman, providing analysis based on actual Excel file structure. Be practical and specific about working with real files."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    print("\n💭 Dato' Ahmad is analyzing your Excel file structure...")
    analysis = await call_lm_studio(messages)
    return analysis


async def main():
    print("🏢 DATO' AHMAD RAHMAN - EXCEL FILE STRUCTURE ANALYSIS")
    print("=" * 60)
    print(f"📁 Analyzing: {EXCEL_FILE_PATH}")
    print()
    
    # Read Excel structure
    print("📊 READING EXCEL FILE STRUCTURE...")
    excel_data = read_excel_with_zipfile()
    
    if 'error' in excel_data:
        print(f"❌ Error: {excel_data['error']}")
        return
    
    print("✅ Successfully read Excel file structure!")
    print(f"   📋 Found {excel_data['file_structure']['worksheet_files']} worksheet(s)")
    print(f"   📝 Found {len(excel_data['shared_strings_sample'])} text strings")
    
    # Get Dato' Ahmad's analysis
    print("\n👔 DATO' AHMAD'S STRUCTURAL ANALYSIS:")
    print("-" * 45)
    
    analysis = await analyze_excel_structure_with_dato_ahmad(excel_data)
    print(analysis)
    
    print("\n" + "=" * 60)
    print("📋 STRUCTURAL ANALYSIS COMPLETE")
    print("💡 For detailed cell-level analysis, consider installing: pip install pandas openpyxl")


if __name__ == "__main__":
    asyncio.run(main())