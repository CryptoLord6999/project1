import redis.asyncio as redis
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from app.config import settings


class DialogueManager:
    """
    Manages conversation state and context for each lead.
    Uses Redis for short-term memory and PostgreSQL for long-term storage.
    """
    
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.context_window_size = 10
        self.summary_interval = 20  # Create summary every N messages
    
    async def get_context(self, lead_id: int) -> Dict[str, Any]:
        """
        Get conversation context for a lead.
        Returns: {summary, recent_messages}
        """
        key_prefix = f"dialogue:{lead_id}"
        
        # Get summary
        summary = await self.redis.get(f"{key_prefix}:summary")
        
        # Get recent messages (stored as sorted set by timestamp)
        messages = await self.redis.zrange(
            f"{key_prefix}:messages",
            0,
            -1,
            withscores=True
        )
        
        recent_messages = []
        for msg_data, score in messages[-self.context_window_size:]:
            recent_messages.append(json.loads(msg_data))
        
        return {
            "summary": summary or "",
            "recent_messages": recent_messages
        }
    
    async def add_message(
        self,
        lead_id: int,
        role: str,
        text: str,
        ts: Optional[datetime] = None
    ):
        """Add a message to the conversation history."""
        key_prefix = f"dialogue:{lead_id}"
        ts = ts or datetime.utcnow()
        
        msg_data = json.dumps({
            "role": role,
            "text": text,
            "ts": ts.isoformat()
        })
        
        # Add to sorted set with timestamp as score
        await self.redis.zadd(
            f"{key_prefix}:messages",
            {msg_data: ts.timestamp()}
        )
        
        # Check if we need to create/update summary
        msg_count = await self.redis.zcard(f"{key_prefix}:messages")
        if msg_count > 0 and msg_count % self.summary_interval == 0:
            await self._update_summary(lead_id)
    
    async def _update_summary(self, lead_id: int):
        """
        Create or update conversation summary.
        This would typically call LLM to generate summary.
        For MVP, we'll keep it simple.
        """
        key_prefix = f"dialogue:{lead_id}"
        messages = await self.redis.zrange(
            f"{key_prefix}:messages",
            0,
            -1
        )
        
        # Simple summary: count messages and note last topic
        # In production, this would call LLM for abstractive summarization
        summary = f"Dialog contains {len(messages)} messages. Last updated: {datetime.utcnow().isoformat()}"
        
        await self.redis.set(f"{key_prefix}:summary", summary)
    
    async def clear_context(self, lead_id: int):
        """Clear all context for a lead."""
        key_prefix = f"dialogue:{lead_id}"
        await self.redis.delete(f"{key_prefix}:messages", f"{key_prefix}:summary")
    
    async def build_llm_context(
        self,
        lead_id: int,
        system_prompt: str
    ) -> List[Dict[str, str]]:
        """
        Build the full context for LLM request.
        Returns list of messages in OpenAI format.
        """
        context = await self.get_context(lead_id)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add summary if exists
        if context["summary"]:
            messages.append({
                "role": "system",
                "content": f"[Conversation Summary]: {context['summary']}"
            })
        
        # Add recent messages
        for msg in context["recent_messages"]:
            messages.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["text"]
            })
        
        return messages
    
    async def set_typing_indicator_key(self, lead_id: int, channel: str):
        """Set a key to track that we're generating a response (for typing indicator)."""
        key = f"typing:{channel}:{lead_id}"
        await self.redis.setex(key, 5, "1")  # 5 second TTL
    
    async def get_typing_indicator_key(self, lead_id: int, channel: str) -> bool:
        """Check if typing indicator is active."""
        key = f"typing:{channel}:{lead_id}"
        return await self.redis.exists(key)


dialogue_manager = DialogueManager()
