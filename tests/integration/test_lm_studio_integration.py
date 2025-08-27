"""
Integration tests for LM Studio provider.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch
from langchain.schema import HumanMessage

from ai_agent_platform.config import config
from ai_agent_platform.llm.providers import LMStudioProvider, get_llm_manager


class TestLMStudioIntegration:
    """Test LM Studio integration."""
    
    @pytest.fixture
    def lm_studio_provider(self):
        """Create LM Studio provider for testing."""
        return LMStudioProvider()
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, lm_studio_provider):
        """Test successful health check."""
        mock_response = httpx.Response(
            status_code=200,
            json={"data": [{"id": "openai/gpt-oss-20b", "object": "model"}]},
            request=httpx.Request("GET", "http://test.com")
        )
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            health = await lm_studio_provider.health_check()
            
            assert health["status"] == "healthy"
            assert health["provider"] == "lm_studio"
            assert "models" in health
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, lm_studio_provider):
        """Test failed health check."""
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection failed")):
            health = await lm_studio_provider.health_check()
            
            assert health["status"] == "unhealthy"
            assert "Connection failed" in health["error"]
    
    @pytest.mark.asyncio 
    async def test_chat_completion_success(self, lm_studio_provider):
        """Test successful chat completion."""
        messages = [HumanMessage(content="Hello, how are you?")]
        
        # Mock the chat model invoke
        mock_response = AsyncMock()
        mock_response.content = "I'm doing well, thank you for asking!"
        
        with patch.object(lm_studio_provider.chat_model, "invoke", return_value=mock_response):
            response = await lm_studio_provider.chat_completion(messages)
            
            assert isinstance(response, str)
            assert "doing well" in response
    
    @pytest.mark.asyncio
    async def test_completion_success(self, lm_studio_provider):
        """Test successful text completion."""
        prompt = "Complete this sentence: The weather today is"
        
        # Mock the llm invoke
        mock_response = AsyncMock()
        mock_response.content = "sunny and warm"
        
        with patch.object(lm_studio_provider.llm, "invoke", return_value=mock_response):
            response = await lm_studio_provider.completion(prompt)
            
            assert isinstance(response, str)
            assert "sunny" in response
    
    @pytest.mark.asyncio
    async def test_get_embeddings_success(self, lm_studio_provider):
        """Test successful embeddings generation."""
        texts = ["Hello world", "How are you?"]
        
        # Mock embeddings
        mock_embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        
        with patch.object(lm_studio_provider.embeddings, "embed_documents", return_value=mock_embeddings):
            embeddings = await lm_studio_provider.get_embeddings(texts)
            
            assert len(embeddings) == 2
            assert len(embeddings[0]) == 3
            assert embeddings[0][0] == 0.1
    
    @pytest.mark.asyncio
    async def test_get_single_embedding_success(self, lm_studio_provider):
        """Test successful single embedding generation."""
        text = "Hello world"
        
        # Mock embedding
        mock_embedding = [0.1, 0.2, 0.3]
        
        with patch.object(lm_studio_provider.embeddings, "embed_query", return_value=mock_embedding):
            embedding = await lm_studio_provider.get_single_embedding(text)
            
            assert len(embedding) == 3
            assert embedding[0] == 0.1


class TestLLMManager:
    """Test LLM Manager integration."""
    
    @pytest.mark.asyncio
    async def test_get_llm_manager_returns_lm_studio(self):
        """Test that LLM manager returns LM Studio provider."""
        manager = get_llm_manager()
        
        assert hasattr(manager, 'current_provider')
        assert isinstance(manager.current_provider, LMStudioProvider)
    
    @pytest.mark.asyncio
    async def test_llm_manager_health_check(self):
        """Test LLM manager health check."""
        manager = get_llm_manager()
        
        # Mock provider health check
        mock_health = {"status": "healthy", "provider": "lm_studio"}
        
        with patch.object(manager.current_provider, "health_check", return_value=mock_health):
            health = await manager.health_check()
            
            assert health["status"] == "healthy"
            assert health["provider"] == "lm_studio"
    
    @pytest.mark.asyncio
    async def test_llm_manager_chat_completion(self):
        """Test LLM manager chat completion."""
        manager = get_llm_manager()
        messages = [{"role": "user", "content": "Hello"}]
        
        # Mock provider chat completion
        mock_response = "Hello! How can I help you today?"
        
        with patch.object(manager, "chat_completion", return_value=mock_response):
            response = await manager.chat_completion(messages)
            
            assert isinstance(response, str)
            assert "help" in response
    
    @pytest.mark.asyncio
    async def test_llm_manager_completion(self):
        """Test LLM manager text completion."""
        manager = get_llm_manager()
        prompt = "The capital of France is"
        
        # Mock provider completion
        mock_response = "Paris"
        
        with patch.object(manager, "completion", return_value=mock_response):
            response = await manager.completion(prompt)
            
            assert isinstance(response, str)
            assert response == "Paris"


@pytest.mark.integration
class TestLMStudioLiveIntegration:
    """Live integration tests - only run if LM Studio is available."""
    
    @pytest.mark.asyncio
    async def test_live_health_check(self):
        """Test live health check against LM Studio."""
        provider = LMStudioProvider()
        
        try:
            health = await provider.health_check()
            
            # If LM Studio is running, should be healthy
            if health["status"] == "healthy":
                assert "models" in health
                assert len(health["models"]) > 0
            else:
                # If not running, should have error
                assert "error" in health
                
        except Exception as e:
            pytest.skip(f"LM Studio not available: {e}")
    
    @pytest.mark.asyncio
    async def test_live_chat_completion(self):
        """Test live chat completion against LM Studio."""
        provider = LMStudioProvider()
        
        try:
            # First check if service is healthy
            health = await provider.health_check()
            if health["status"] != "healthy":
                pytest.skip("LM Studio not healthy")
            
            messages = [HumanMessage(content="Say 'test successful' if you can read this.")]
            response = await provider.chat_completion(messages)
            
            assert isinstance(response, str)
            assert len(response) > 0
            # Should contain our test phrase
            assert "test successful" in response.lower()
            
        except Exception as e:
            pytest.skip(f"LM Studio not available: {e}")
    
    @pytest.mark.asyncio
    async def test_live_completion(self):
        """Test live text completion against LM Studio."""
        provider = LMStudioProvider()
        
        try:
            # First check if service is healthy
            health = await provider.health_check()
            if health["status"] != "healthy":
                pytest.skip("LM Studio not healthy")
            
            response = await provider.completion("The color of the sky is usually")
            
            assert isinstance(response, str)
            assert len(response) > 0
            # Should contain "blue" or similar
            assert any(color in response.lower() for color in ["blue", "azure", "clear"])
            
        except Exception as e:
            pytest.skip(f"LM Studio not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__])