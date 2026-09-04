from typing import Dict, Any, List


def build_system_prompt(
    client_name: str,
    tone: str,
    services: List[str],
    prices: Dict[str, Any],
    faq: Dict[str, str]
) -> str:
    """
    Build the system prompt for the LLM based on client configuration.
    """
    services_str = ", ".join(services) if services else "not specified"
    
    prices_str = "\n".join([f"- {k}: {v}" for k, v in prices.items()]) if prices else "not specified"
    
    faq_str = "\n".join([f"Q: {k}\nA: {v}" for k, v in faq.items()]) if faq else "not specified"
    
    return f"""Ты — ИИ-ассистент компании «{client_name}». Отвечай в тоне: {tone}.
Используй ТОЛЬКО факты из:
Услуги: {services_str}
Цены:
{prices_str}
FAQ:
{faq_str}

Цель: квалифицировать (услуга, бюджет, срочность) и записать на слот через book_slot.
Если не знаешь ответа или сработало правило эскалации — вызови handoff и мягко передай диалог человеку.
Отвечай коротко (1-3 предложения), без воды.

Важно: представляйся как ИИ-ассистент в первом сообщении. Не выдумывай цены или условия, которых нет в конфиге."""


def build_tools_definition() -> List[Dict[str, Any]]:
    """
    Define tools (functions) available to the LLM.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "book_slot",
                "description": "Book a time slot for the customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "datetime": {
                            "type": "string",
                            "description": "Date and time in ISO format (YYYY-MM-DDTHH:MM)"
                        },
                        "service": {
                            "type": "string",
                            "description": "Service name to book"
                        }
                    },
                    "required": ["datetime", "service"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "save_lead",
                "description": "Save lead qualification data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service the customer is interested in"
                        },
                        "budget": {
                            "type": "number",
                            "description": "Customer's budget"
                        },
                        "urgency": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "How urgent is the request"
                        },
                        "intent_to_book": {
                            "type": "boolean",
                            "description": "Does the customer intend to book"
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative"],
                            "description": "Customer sentiment"
                        },
                        "wants_human": {
                            "type": "boolean",
                            "description": "Does the customer explicitly want to talk to a human"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "handoff",
                "description": "Escalate conversation to a human operator",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Reason for handoff (customer request, complex question, negative sentiment, high budget)"
                        }
                    },
                    "required": ["reason"]
                }
            }
        }
    ]


QUALIFICATION_SCHEMA = """
{
  "service": "string - service customer is interested in",
  "budget": "number - customer's budget or null",
  "urgency": "string - low|medium|high",
  "intent_to_book": "boolean",
  "sentiment": "string - positive|neutral|negative",
  "wants_human": "boolean"
}
"""
