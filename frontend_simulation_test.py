#!/usr/bin/env python3
"""
Frontend UI Simulation Test
Test the system exactly as your frontend would use it
"""

import asyncio
import httpx
import json
from pathlib import Path

class FrontendSimulator:
    """Simulate exactly what the frontend JavaScript does."""
    
    def __init__(self):
        self.base_url = "http://localhost:8003"
        
    async def simulate_chat_request(self, message: str):
        """Simulate the exact chat request from your frontend."""
        print(f"🖥️  SIMULATING FRONTEND CHAT REQUEST")
        print(f"User types: '{message}'")
        print("JavaScript creates request...")
        
        # Exact payload your frontend sends
        payload = {
            "message": message,
            "agent_name": "Dato Ahmad Rahman",
            "use_rag": True
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print("📡 Sending POST to /chat...")
                response = await client.post(
                    f"{self.base_url}/chat",
                    json=payload,  # JSON payload like frontend
                    headers={'Content-Type': 'application/json'}
                )
                
                print(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ SUCCESS - Response received:")
                    print(f"   Agent: {data.get('agent_name', 'Unknown')}")
                    print(f"   Time: {data.get('execution_time_ms', 0)}ms")
                    print(f"   Sources: {data.get('sources_used', [])}")
                    print(f"   Response: {data.get('response', '')[:200]}...")
                    return data
                else:
                    print(f"❌ ERROR: HTTP {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)}")
            return None
    
    async def simulate_excel_upload(self, file_path: str, query: str):
        """Simulate the exact Excel upload from your frontend."""
        print(f"\n📄 SIMULATING FRONTEND EXCEL UPLOAD")
        print(f"User selects file: {Path(file_path).name}")
        print(f"User types query: '{query}'")
        print("JavaScript creates FormData...")
        
        if not Path(file_path).exists():
            print(f"❌ File not found: {file_path}")
            return None
            
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Simulate exact FormData from frontend
                files = {
                    'file': (Path(file_path).name, open(file_path, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                }
                data = {
                    'analysis_type': 'general',
                    'specific_query': query
                }
                
                print("📡 Sending POST to /excel/upload...")
                response = await client.post(
                    f"{self.base_url}/excel/upload",
                    files=files,
                    data=data  # Form data like frontend
                )
                
                files['file'][1].close()  # Close file
                
                print(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ SUCCESS - Upload processed:")
                    print(f"   Filename: {result.get('filename', 'Unknown')}")
                    print(f"   Status: {result.get('status', 'Unknown')}")
                    print(f"   Analysis: {result.get('analysis_preview', '')[:300]}...")
                    return result
                else:
                    print(f"❌ ERROR: HTTP {response.status_code}")
                    print(f"   Response: {response.text[:500]}")
                    return None
                    
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)}")
            return None
    
    async def test_ui_flow(self):
        """Test the complete UI flow as user would experience it."""
        print("🌐 COMPLETE FRONTEND UI SIMULATION")
        print("=" * 60)
        
        # Test 1: Chat without Excel data
        print("\n🧪 TEST 1: Chat Request (like typing in web interface)")
        result1 = await self.simulate_chat_request("What companies are in my Excel files?")
        
        # Test 2: Excel upload
        excel_file = "/mnt/c/Users/nvntr/Documents/ai_agent_platform/data/input/multi_sheet.xlsx"
        print("\n🧪 TEST 2: Excel Upload (like using web form)")
        result2 = await self.simulate_excel_upload(excel_file, "What companies are mentioned in TURN-COS-GP_RM?")
        
        # Test 3: Chat after Excel upload
        print("\n🧪 TEST 3: Chat After Upload (should use Excel data)")
        result3 = await self.simulate_chat_request("List the construction companies from my uploaded Excel file")
        
        # Analysis
        print(f"\n📊 SIMULATION ANALYSIS:")
        print(f"   Chat without Excel: {'✅ Works' if result1 else '❌ Failed'}")
        print(f"   Excel upload: {'✅ Works' if result2 else '❌ Failed'}")
        print(f"   Chat with Excel: {'✅ Works' if result3 else '❌ Failed'}")
        
        return {
            "chat_without_excel": result1,
            "excel_upload": result2,
            "chat_with_excel": result3
        }

async def main():
    """Run complete frontend simulation."""
    simulator = FrontendSimulator()
    
    print("🔧 Starting frontend simulation test...")
    print("This will test exactly what your browser JavaScript does\n")
    
    results = await simulator.test_ui_flow()
    
    print(f"\n🎯 FRONTEND SIMULATION COMPLETE")
    print(f"Now you can compare this with your actual browser experience!")
    
    # Save results for comparison
    with open("/mnt/c/Users/nvntr/Documents/ai_agent_platform/frontend_test_results.json", "w") as f:
        # Convert to JSON-serializable format
        serializable_results = {}
        for key, value in results.items():
            if value:
                serializable_results[key] = {
                    "status": "success",
                    "response_preview": str(value).get('response', str(value))[:200] if isinstance(value, dict) else str(value)[:200]
                }
            else:
                serializable_results[key] = {"status": "failed"}
        
        json.dump(serializable_results, f, indent=2)
    
    print(f"📄 Results saved to frontend_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())