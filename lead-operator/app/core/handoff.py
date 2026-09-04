from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import Lead, LeadStatus, Message
from app.admin.notify import notify_owner


async def handle_handoff(
    lead: Lead,
    reason: str,
    db: Session,
    conversation_summary: str = ""
):
    """
    Handle escalation to human operator.
    Updates lead status and notifies owner.
    """
    # Update lead status
    lead.status = LeadStatus.HANDED_OFF
    db.commit()
    
    # Notify owner
    await notify_owner(
        lead=lead,
        reason=reason,
        conversation_summary=conversation_summary,
        db=db
    )


def should_trigger_handoff(
    tool_call_name: Optional[str],
    qualification: Dict[str, Any],
    faq_miss_count: int,
    handoff_rules: Dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Determine if handoff should be triggered.
    
    Checks:
    1. LLM explicitly called handoff tool
    2. Hard rules (wants_human, negative sentiment, FAQ exhausted, high budget)
    """
    # LLM explicitly requested handoff
    if tool_call_name == "handoff":
        return True, "llm_requested"
    
    # Check hard rules
    from app.core.qualifier import check_handoff_rules
    
    should_handoff, reason = check_handoff_rules(
        qualification=qualification,
        handoff_rules=handoff_rules,
        faq_miss_count=faq_miss_count
    )
    
    return should_handoff, reason
