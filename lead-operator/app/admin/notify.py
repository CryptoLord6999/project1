import httpx
from typing import Dict, Any
from app.config import settings


async def notify_owner(
    lead: Any,
    reason: str,
    conversation_summary: str = "",
    db: Any = None
) -> bool:
    """
    Send notification to owner about hot lead or handoff.
    Uses Telegram by default (as per MVP spec).
    """
    from app.db.models import Message
    from sqlalchemy import select
    
    # Get conversation transcript
    if db:
        result = db.execute(
            select(Message)
            .where(Message.lead_id == lead.id)
            .order_by(Message.ts)
        )
        messages = result.scalars().all()
        
        transcript = "\n".join([
            f"[{m.role}]: {m.text}"
            for m in messages[-20:]  # Last 20 messages
        ])
    else:
        transcript = conversation_summary
    
    # Build lead info dict
    qual = lead.qualification or {}
    lead_info = {
        "client_name": "Unknown",  # Would need to fetch from ClientConfig
        "channel": lead.channel,
        "contact": lead.contact,
        "status": lead.status.value if hasattr(lead.status, 'value') else str(lead.status),
        "service": qual.get("service"),
        "budget": qual.get("budget"),
        "urgency": qual.get("urgency"),
        "intent_to_book": qual.get("intent_to_book"),
        "sentiment": qual.get("sentiment"),
        "handoff_reason": reason
    }
    
    # Send via Telegram
    from app.connectors.telegram import telegram_connector
    
    return await telegram_connector.notify_owner(
        owner_id=settings.owner_telegram_id,
        lead_info=lead_info,
        conversation_transcript=transcript
    )
