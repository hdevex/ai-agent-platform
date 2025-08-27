#!/usr/bin/env python3
"""
Test script to verify the fixed upload endpoint works correctly
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from real_excel_chat_system import RealExcelChatSystem

async def test_real_system():
    """Test that the real system works with different query types"""
    print("Testing RealExcelChatSystem with different query types...")

    real_system = RealExcelChatSystem()

    test_queries = [
        "cost of sales infra-port",  # Should return financial data, not companies
        "division names",            # Should return organizational data, not companies
        "revenue figures",           # Should return financial data
        "what companies are there"   # Should return company data
    ]

    for query in test_queries:
        print(f"\nTesting query: '{query}'")
        try:
            response = await real_system.chat_with_excel_data(query)
            # Handle Unicode characters safely
            safe_response = response.encode('ascii', 'ignore').decode('ascii')
            print(f"SUCCESS Response: {safe_response[:200]}..." if len(safe_response) > 200 else f"SUCCESS Response: {safe_response}")

            # Check if response is different for different queries
            if "company" in query.lower() and "cost of sales" not in response.lower():
                print("   WARNING: Company query didn't return company data")
            elif "cost of sales" in query.lower() and "company" not in response.lower():
                print("   GOOD: Financial query returned different data than company query")

        except Exception as e:
            print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_real_system())