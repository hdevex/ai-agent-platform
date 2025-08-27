import json
from fastapi.testclient import TestClient
from ai_agent_platform.finance_manager_demo import app, parse_query

# Monkeypatch the data retriever and LM Studio call for isolation

def mock_get_relevant_data(self, analysis, max_tokens=1500):
    return [
        {"type": "financial", "sheet": "Sheet1", "data": "Revenue: 100000"},
        {"type": "entity", "sheet": "Sheet2", "data": "ABC Corporation"}
    ]

async def mock_call_lm_studio(messages):
    return "Mocked AI response"

# Patch the classes and functions
app.dependency_overrides[parse_query] = lambda x: {"intent_scores": {"financial_analysis": 1.0}, "target_sheets": []}
from ai_agent_platform.real_excel_chat_system import TokenEfficientDataRetriever, call_lm_studio
TokenEfficientDataRetriever.get_relevant_data = mock_get_relevant_data
call_lm_studio = mock_call_lm_studio

client = TestClient(app)

def test_upload_endpoint():
    files = {
        "file": ("test.xlsx", b"dummycontent", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    data = {"specific_query": "Show revenue"}
    response = client.post("/excel/upload", files=files, data=data)
    assert response.status_code == 200
    json_resp = response.json()
    assert json_resp["status"] == "success"
    assert "analysis_preview" in json_resp

def test_chat_endpoint():
    payload = {
        "message": "What is the revenue of ABC?",
        "agent_name": "Dato' Ahmad Rahman",
        "use_rag": True
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    json_resp = response.json()
    assert json_resp["response"] == "Mocked AI response"
    assert isinstance(json_resp["sources_used"], list)
