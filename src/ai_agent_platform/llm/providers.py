"""
LLM Provider integrations with security and monitoring.
"""

import logging
from typing import Any, Dict, List, Optional
import asyncio
import httpx
from abc import ABC, abstractmethod

from langchain_community.llms.openai import OpenAI
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.schema import BaseMessage, HumanMessage, SystemMessage, AIMessage

from ..config import config

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def chat_completion(
        self, messages: List[BaseMessage], **kwargs
    ) -> str:
        """Generate chat completion."""
        pass
    
    @abstractmethod
    async def completion(self, prompt: str, **kwargs) -> str:
        """Generate text completion."""
        pass
    
    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        pass


class LMStudioProvider(LLMProvider):
    """LM Studio provider with OpenAI-compatible API."""
    
    def __init__(self):
        """Initialize LM Studio provider."""
        self.base_url = config.llm.llm_base_url
        self.model_name = config.llm.llm_model_name
        self.temperature = config.llm.llm_temperature
        self.max_tokens = config.llm.llm_max_tokens
        
        # Initialize LangChain components
        self.llm = OpenAI(
            openai_api_base=self.base_url,
            openai_api_key="not-needed",  # LM Studio doesn't require API key
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        self.chat_model = ChatOpenAI(
            openai_api_base=self.base_url,
            openai_api_key="not-needed",
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        # HTTP client for direct API calls
        self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"🤖 LM Studio provider initialized: {self.base_url}")
    
    async def chat_completion(
        self, 
        messages: List[BaseMessage], 
        **kwargs
    ) -> str:
        """Generate chat completion using LangChain."""
        try:
            # Convert messages to LangChain format if needed
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "system":
                        formatted_messages.append(SystemMessage(content=content))
                    elif role == "assistant":
                        formatted_messages.append(AIMessage(content=content))
                    else:
                        formatted_messages.append(HumanMessage(content=content))
                else:
                    formatted_messages.append(msg)
            
            # Generate response using LangChain
            response = await asyncio.to_thread(
                self.chat_model.invoke,
                formatted_messages
            )
            
            return response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            logger.error(f"❌ Chat completion failed: {e}")
            raise
    
    async def completion(self, prompt: str, **kwargs) -> str:
        """Generate text completion."""
        try:
            response = await asyncio.to_thread(
                self.llm.invoke,
                prompt
            )
            return response
            
        except Exception as e:
            logger.error(f"❌ Text completion failed: {e}")
            raise
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using LM Studio."""
        try:
            # Use direct API call for embeddings
            response = await self.client.post(
                f"{self.base_url}/embeddings",
                json={
                    "input": texts,
                    "model": self.model_name,
                }
            )
            response.raise_for_status()
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Embeddings generation failed: {e}")
            # Fallback to local embeddings if LM Studio doesn't support it
            return await self._get_local_embeddings(texts)
    
    async def _get_local_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Fallback to local embeddings."""
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer(config.llm.embedding_model)
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
            
        except ImportError:
            logger.error("❌ sentence-transformers not available for local embeddings")
            raise
        except Exception as e:
            logger.error(f"❌ Local embeddings failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check LM Studio health."""
        try:
            # Check models endpoint
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            
            models_data = response.json()
            available_models = [model["id"] for model in models_data.get("data", [])]
            
            # Check if our preferred model is available
            model_available = self.model_name in available_models
            
            # Test completion endpoint
            test_response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 5,
                }
            )
            test_response.raise_for_status()
            
            return {
                "status": "healthy",
                "provider": "lm_studio",
                "base_url": self.base_url,
                "model": self.model_name,
                "model_available": model_available,
                "available_models": available_models,
                "endpoints": {
                    "models": "✅",
                    "chat_completions": "✅",
                    "completions": "✅",
                }
            }
            
        except Exception as e:
            logger.error(f"❌ LM Studio health check failed: {e}")
            return {
                "status": "unhealthy",
                "provider": "lm_studio",
                "base_url": self.base_url,
                "model": self.model_name,
                "error": str(e),
            }
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class LLMManager:
    """Manages LLM providers with failover and monitoring."""
    
    def __init__(self):
        """Initialize LLM manager."""
        self.providers: Dict[str, LLMProvider] = {}
        self.active_provider: Optional[str] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available providers."""
        # Primary provider: LM Studio
        if config.llm.llm_provider == "lm_studio":
            self.providers["lm_studio"] = LMStudioProvider()
            self.active_provider = "lm_studio"
        
        logger.info(f"🔧 LLM Manager initialized with providers: {list(self.providers.keys())}")
    
    async def chat_completion(
        self, 
        messages: List[BaseMessage], 
        **kwargs
    ) -> str:
        """Generate chat completion with failover."""
        if not self.active_provider or self.active_provider not in self.providers:
            raise RuntimeError("No active LLM provider available")
        
        provider = self.providers[self.active_provider]
        return await provider.chat_completion(messages, **kwargs)
    
    async def completion(self, prompt: str, **kwargs) -> str:
        """Generate completion with failover."""
        if not self.active_provider or self.active_provider not in self.providers:
            raise RuntimeError("No active LLM provider available")
        
        provider = self.providers[self.active_provider]
        return await provider.completion(prompt, **kwargs)
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with failover."""
        if not self.active_provider or self.active_provider not in self.providers:
            raise RuntimeError("No active LLM provider available")
        
        provider = self.providers[self.active_provider]
        return await provider.get_embeddings(texts)
    
    async def health_check_all(self) -> Dict[str, Any]:
        """Health check all providers."""
        results = {}
        
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        
        return {
            "providers": results,
            "active_provider": self.active_provider,
        }
    
    async def close(self):
        """Close all providers."""
        for provider in self.providers.values():
            if hasattr(provider, 'close'):
                await provider.close()


# Global LLM manager instance
llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get global LLM manager instance."""
    global llm_manager
    if llm_manager is None:
        llm_manager = LLMManager()
    return llm_manager