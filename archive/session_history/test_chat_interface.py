#!/usr/bin/env python3
"""
Test the chat interface functionality
"""

import asyncio
import httpx

async def test_chat():
    """Test chat interface with various queries."""
    print("🧪 TESTING CHAT INTERFACE")
    print("=" * 30)
    
    base_url = "http://localhost:8003"
    
    test_queries = [
        "What companies are in my Excel file?",
        "Show me revenue information",
        "What subsidiaries do I have?",
        "Explain the financial structure"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for query in test_queries:
            print(f"\n🔍 Testing: {query}")
            
            try:
                response = await client.post(
                    f"{base_url}/chat",
                    json={
                        "message": query,
                        "agent_name": "Dato Ahmad Rahman", 
                        "use_rag": True
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Response ({data['execution_time_ms']}ms):")
                    print(f"   {data['response'][:150]}{'...' if len(data['response']) > 150 else ''}")
                else:
                    print(f"❌ Error: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())