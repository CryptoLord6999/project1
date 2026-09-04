from typing import Dict, Any, Optional
from app.llm.client import llm_client
from app.llm.prompts import QUALIFICATION_SCHEMA


async def extract_qualification(
    conversation_text: str,
    system_prompt: str
) -> Dict[str, Any]:
    """
    Extract qualification fields from conversation.
    
    Returns dict with:
    - service: str
    - budget: float or None
    - urgency: str (low/medium/high)
    - intent_to_book: bool
    - sentiment: str (positive/neutral/negative)
    - wants_human: bool
    """
    try:
        result = await llm_client.extract_json(
            system_prompt=system_prompt,
            user_message=f"Extract qualification from this conversation:\n\n{conversation_text}",
            json_schema_description=QUALIFICATION_SCHEMA
        )
        
        # Ensure all fields exist with defaults
        return {
            "service": result.get("service"),
            "budget": result.get("budget"),
            "urgency": result.get("urgency", "low"),
            "intent_to_book": result.get("intent_to_book", False),
            "sentiment": result.get("sentiment", "neutral"),
            "wants_human": result.get("wants_human", False)
        }
    except Exception as e:
        # Return default values if extraction fails
        return {
            "service": None,
            "budget": None,
            "urgency": "low",
            "intent_to_book": False,
            "sentiment": "neutral",
            "wants_human": False
        }


def check_handoff_rules(
    qualification: Dict[str, Any],
    handoff_rules: Dict[str, Any],
    faq_miss_count: int = 0
) -> tuple[bool, Optional[str]]:
    """
    Check if handoff should be triggered based on hard rules.
    
    Returns: (should_handoff, reason)
    """
    # Rule 1: Customer explicitly wants human
    if qualification.get("wants_human"):
        return True, "customer_requested_human"
    
    # Rule 2: Negative sentiment
    if qualification.get("sentiment") == "negative":
        return True, "negative_sentiment"
    
    # Rule 3: FAQ miss count (question outside FAQ twice)
    if faq_miss_count >= 2:
        return True, "faq_exhausted"
    
    # Rule 4: Budget above threshold
    budget = qualification.get("budget")
    if budget and "high_budget_threshold" in handoff_rules:
        if budget > handoff_rules["high_budget_threshold"]:
            return True, "high_budget"
    
    return False, None
