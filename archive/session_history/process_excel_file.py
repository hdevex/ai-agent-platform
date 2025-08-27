#!/usr/bin/env python3
"""
Process your specific Excel file into the database system
"""

import asyncio
import sys
from pathlib import Path
from excel_to_database_system import ExcelDatabaseSystem

EXCEL_FILE_PATH = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/data/input/multi_sheet.xlsx"

async def main():
    """Process the specific Excel file."""
    print("📊 PROCESSING YOUR EXCEL FILE INTO DATABASE")
    print("=" * 50)
    print(f"📁 File: {Path(EXCEL_FILE_PATH).name}")
    print()
    
    # Check if file exists
    if not Path(EXCEL_FILE_PATH).exists():
        print(f"❌ Excel file not found: {EXCEL_FILE_PATH}")
        return
    
    # Initialize system
    system = ExcelDatabaseSystem()
    
    try:
        print("🔄 Extracting data from Excel file...")
        
        # Extract data
        file_data = system.extract_excel_data(EXCEL_FILE_PATH)
        
        if "error" in file_data:
            print(f"❌ Error extracting data: {file_data['error']}")
            return
        
        print(f"✅ Successfully extracted data from {file_data['sheets_count']} sheets:")
        for sheet_name, sheet_data in file_data["sheets_data"].items():
            print(f"   📋 {sheet_name}: {sheet_data['rows_count']} rows × {sheet_data['columns_count']} columns")
            print(f"      💾 {len(sheet_data['cells'])} cells extracted")
            print(f"      💰 {len(sheet_data['patterns']['financial_terms'])} financial terms found")
            print(f"      🏢 {len(sheet_data['patterns']['entities'])} entities found")
        
        print(f"\n💾 Storing data in database...")
        
        # Store in database with AI analysis
        file_id = await system.store_in_database(file_data)
        
        print(f"✅ Successfully stored in database (File ID: {file_id})")
        
        # Show statistics
        print(f"\n📊 DATABASE STATISTICS:")
        stats = system.get_database_stats()
        if "error" not in stats:
            print(f"   📁 Files: {stats['files']['count']}")
            print(f"   📋 Sheets: {stats['files']['total_sheets']}")
            print(f"   💾 Cells: {stats['total_cells']:,}")
            print(f"   🔢 Numbers: {stats['numeric_cells']:,}")
            print(f"   🔍 Searchable: {stats['searchable_items']:,}")
        
        # Quick search demo
        print(f"\n🔍 QUICK SEARCH TEST:")
        test_queries = ["revenue", "ABC Construction", "profit"]
        
        for query in test_queries:
            results = system.search_data(query, limit=3)
            print(f"   '{query}': {len(results)} results found")
            if results:
                for result in results[:2]:
                    if result["type"] == "search_match":
                        print(f"      - {result['matched_text']} ({result['content_type']})")
                    else:
                        print(f"      - {result['cell_address']}: {result['cell_value']}")
        
        print(f"\n🎉 SUCCESS! Your Excel file is now fully searchable in the database!")
        print(f"💡 You can now run: python test_excel_db_system.py for full testing")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        system.close()

if __name__ == "__main__":
    asyncio.run(main())