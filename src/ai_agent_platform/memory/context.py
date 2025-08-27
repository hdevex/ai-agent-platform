"""
Memory and context management for AI agents.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import uuid

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory, ConversationSummaryBufferMemory

from ..database.connection import get_redis
from ..llm.providers import get_llm_manager

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """Individual context item."""
    id: str
    type: str  # "message", "document", "tool_result", "memory"
    content: str
    metadata: Dict[str, Any]
    timestamp: str
    agent_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class ConversationTurn:
    """Single conversation turn."""
    turn_id: str
    user_message: str
    agent_response: str
    context_used: List[ContextItem]
    timestamp: str
    metadata: Dict[str, Any]


class MemoryStore:
    """Redis-based memory store for agent conversations and context."""
    
    def __init__(self):
        """Initialize memory store."""
        self.redis = None
        logger.info("🧠 Memory store initialized")
    
    async def _get_redis(self):
        """Get Redis connection."""
        if self.redis is None:
            self.redis = await get_redis()
        return self.redis
    
    async def store_context_item(
        self, 
        context_item: ContextItem, 
        ttl_seconds: int = 86400
    ) -> bool:
        """Store context item in Redis."""
        try:
            redis = await self._get_redis()
            key = f"context:{context_item.id}"
            value = json.dumps(asdict(context_item), default=str)
            
            await redis.setex(key, ttl_seconds, value)
            
            # Add to agent's context index if agent_id provided
            if context_item.agent_id:
                index_key = f"agent_context:{context_item.agent_id}"
                await redis.sadd(index_key, context_item.id)
                await redis.expire(index_key, ttl_seconds)
            
            # Add to session's context index if session_id provided
            if context_item.session_id:
                session_key = f"session_context:{context_item.session_id}"
                await redis.sadd(session_key, context_item.id)
                await redis.expire(session_key, ttl_seconds)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store context item: {e}")
            return False
    
    async def get_context_item(self, context_id: str) -> Optional[ContextItem]:
        """Retrieve context item by ID."""
        try:
            redis = await self._get_redis()
            key = f"context:{context_id}"
            
            value = await redis.get(key)
            if value:
                data = json.loads(value)
                return ContextItem(**data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get context item: {e}")
            return None
    
    async def get_agent_context(
        self, 
        agent_id: str, 
        limit: int = 50
    ) -> List[ContextItem]:
        """Get recent context for an agent."""
        try:
            redis = await self._get_redis()
            index_key = f"agent_context:{agent_id}"
            
            # Get context item IDs
            context_ids = await redis.smembers(index_key)
            
            # Retrieve and sort context items
            context_items = []
            for context_id in list(context_ids)[:limit]:
                context_item = await self.get_context_item(context_id.decode())
                if context_item:
                    context_items.append(context_item)
            
            # Sort by timestamp (newest first)
            context_items.sort(
                key=lambda x: datetime.fromisoformat(x.timestamp), 
                reverse=True
            )
            
            return context_items[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get agent context: {e}")
            return []
    
    async def store_conversation_turn(
        self, 
        turn: ConversationTurn,
        ttl_seconds: int = 86400
    ) -> bool:
        """Store conversation turn."""
        try:
            redis = await self._get_redis()
            key = f"conversation:{turn.turn_id}"
            value = json.dumps(asdict(turn), default=str)
            
            await redis.setex(key, ttl_seconds, value)
            
            # Add to session's conversation index
            if turn.metadata.get("session_id"):
                session_key = f"session_turns:{turn.metadata['session_id']}"
                await redis.lpush(session_key, turn.turn_id)
                await redis.expire(session_key, ttl_seconds)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store conversation turn: {e}")
            return False
    
    async def get_session_history(
        self, 
        session_id: str, 
        limit: int = 20
    ) -> List[ConversationTurn]:
        """Get conversation history for a session."""
        try:
            redis = await self._get_redis()
            session_key = f"session_turns:{session_id}"
            
            # Get turn IDs (most recent first)
            turn_ids = await redis.lrange(session_key, 0, limit - 1)
            
            # Retrieve conversation turns
            turns = []
            for turn_id in turn_ids:
                turn_key = f"conversation:{turn_id.decode()}"
                turn_data = await redis.get(turn_key)
                if turn_data:
                    turn_dict = json.loads(turn_data)
                    # Reconstruct ContextItem objects
                    turn_dict["context_used"] = [
                        ContextItem(**item) for item in turn_dict["context_used"]
                    ]
                    turns.append(ConversationTurn(**turn_dict))
            
            return turns
            
        except Exception as e:
            logger.error(f"❌ Failed to get session history: {e}")
            return []


class AgentMemory:
    """Agent memory management with different memory types."""
    
    def __init__(self, agent_id: str, session_id: Optional[str] = None):
        """Initialize agent memory."""
        self.agent_id = agent_id
        self.session_id = session_id or str(uuid.uuid4())
        self.memory_store = MemoryStore()
        
        # LangChain memory instances
        self.short_term_memory = ConversationBufferWindowMemory(
            k=10,  # Keep last 10 exchanges
            return_messages=True,
        )
        
        self.long_term_memory = None  # Will initialize when LLM is available
        
        logger.info(f"🧠 Agent memory initialized for agent {agent_id}, session {self.session_id}")
    
    async def _initialize_long_term_memory(self):
        """Initialize long-term memory with summarization."""
        if self.long_term_memory is None:
            try:
                llm_manager = get_llm_manager()
                # Create a simple LLM wrapper for LangChain compatibility
                class LLMWrapper:
                    async def apredict(self, text: str) -> str:
                        return await llm_manager.completion(text)
                    
                    def predict(self, text: str) -> str:
                        # Synchronous wrapper (not ideal but needed for LangChain)
                        import asyncio
                        return asyncio.run(self.apredict(text))
                
                self.long_term_memory = ConversationSummaryBufferMemory(
                    llm=LLMWrapper(),
                    max_token_limit=2000,
                    return_messages=True,
                )
                
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize long-term memory: {e}")
    
    async def add_message(self, message: BaseMessage):
        """Add message to memory."""
        try:
            # Add to short-term memory
            if isinstance(message, HumanMessage):
                self.short_term_memory.chat_memory.add_user_message(message.content)
            elif isinstance(message, AIMessage):
                self.short_term_memory.chat_memory.add_ai_message(message.content)
            
            # Add to long-term memory if available
            if self.long_term_memory:
                if isinstance(message, HumanMessage):
                    self.long_term_memory.chat_memory.add_user_message(message.content)
                elif isinstance(message, AIMessage):
                    self.long_term_memory.chat_memory.add_ai_message(message.content)
            
            # Store as context item
            context_item = ContextItem(
                id=str(uuid.uuid4()),
                type="message",
                content=message.content,
                metadata={
                    "message_type": type(message).__name__,
                    "session_id": self.session_id,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent_id=self.agent_id,
                session_id=self.session_id,
            )
            
            await self.memory_store.store_context_item(context_item)
            
        except Exception as e:
            logger.error(f"❌ Failed to add message to memory: {e}")
    
    async def add_context(
        self, 
        content: str, 
        context_type: str = "document",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add context information to memory."""
        try:
            context_item = ContextItem(
                id=str(uuid.uuid4()),
                type=context_type,
                content=content,
                metadata=metadata or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent_id=self.agent_id,
                session_id=self.session_id,
            )
            
            await self.memory_store.store_context_item(context_item)
            
        except Exception as e:
            logger.error(f"❌ Failed to add context to memory: {e}")
    
    async def get_conversation_history(self) -> List[BaseMessage]:
        """Get conversation history as LangChain messages."""
        try:
            # Get from short-term memory first
            messages = self.short_term_memory.chat_memory.messages
            
            if messages:
                return messages
            
            # Fallback to stored session history
            turns = await self.memory_store.get_session_history(self.session_id)
            history_messages = []
            
            for turn in reversed(turns):  # Reverse to get chronological order
                history_messages.append(HumanMessage(content=turn.user_message))
                history_messages.append(AIMessage(content=turn.agent_response))
            
            return history_messages
            
        except Exception as e:
            logger.error(f"❌ Failed to get conversation history: {e}")
            return []
    
    async def get_relevant_context(
        self, 
        query: str, 
        limit: int = 5
    ) -> List[ContextItem]:
        """Get relevant context items for a query."""
        try:
            # Get recent context for this agent
            context_items = await self.memory_store.get_agent_context(
                self.agent_id, 
                limit=limit * 2  # Get more to filter from
            )
            
            # Simple relevance filtering (could be enhanced with embeddings)
            relevant_items = []
            query_lower = query.lower()
            
            for item in context_items:
                content_lower = item.content.lower()
                # Simple keyword matching
                if any(word in content_lower for word in query_lower.split()):
                    relevant_items.append(item)
            
            return relevant_items[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get relevant context: {e}")
            return []
    
    async def save_conversation_turn(
        self, 
        user_message: str, 
        agent_response: str, 
        context_used: Optional[List[ContextItem]] = None
    ):
        """Save complete conversation turn."""
        try:
            turn = ConversationTurn(
                turn_id=str(uuid.uuid4()),
                user_message=user_message,
                agent_response=agent_response,
                context_used=context_used or [],
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "agent_id": self.agent_id,
                    "session_id": self.session_id,
                }
            )
            
            await self.memory_store.store_conversation_turn(turn)
            
        except Exception as e:
            logger.error(f"❌ Failed to save conversation turn: {e}")
    
    async def clear_session(self):
        """Clear current session memory."""
        try:
            self.short_term_memory.clear()
            if self.long_term_memory:
                self.long_term_memory.clear()
                
            logger.info(f"🧹 Cleared memory for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to clear session memory: {e}")


class ContextManager:
    """Manages context and memory for multiple agents and sessions."""
    
    def __init__(self):
        """Initialize context manager."""
        self.agent_memories: Dict[str, AgentMemory] = {}
        logger.info("🎭 Context manager initialized")
    
    def get_agent_memory(
        self, 
        agent_id: str, 
        session_id: Optional[str] = None
    ) -> AgentMemory:
        """Get or create agent memory instance."""
        key = f"{agent_id}:{session_id}" if session_id else agent_id
        
        if key not in self.agent_memories:
            self.agent_memories[key] = AgentMemory(agent_id, session_id)
        
        return self.agent_memories[key]
    
    async def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """Clean up expired session memories."""
        try:
            current_time = datetime.now(timezone.utc)
            expired_keys = []
            
            for key, memory in self.agent_memories.items():
                # This is a simplified cleanup - in production, you'd want
                # to track session activity timestamps
                pass  # Implementation would depend on session tracking
            
            for key in expired_keys:
                del self.agent_memories[key]
            
            if expired_keys:
                logger.info(f"🧹 Cleaned up {len(expired_keys)} expired sessions")
                
        except Exception as e:
            logger.error(f"❌ Failed to clean up expired sessions: {e}")


# Global context manager instance
context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Get global context manager instance."""
    global context_manager
    if context_manager is None:
        context_manager = ContextManager()
    return context_manager