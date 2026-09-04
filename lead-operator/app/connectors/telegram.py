import httpx
from typing import Dict, Any, Optional
from app.config import settings


class TelegramConnector:
    """
    Connector for Telegram Bot API.
    Handles sending messages, chat actions, and receiving updates.
    """
    
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.timeout = 30.0
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """Send a text message to a chat."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }
            )
            return response.status_code == 200
    
    async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        """Send chat action (e.g., typing indicator)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendChatAction",
                json={
                    "chat_id": chat_id,
                    "action": action
                }
            )
            return response.status_code == 200
    
    async def notify_owner(
        self,
        owner_id: int,
        lead_info: Dict[str, Any],
        conversation_transcript: str
    ) -> bool:
        """
        Send lead notification to owner.
        Formats a nice card with lead details and transcript.
        """
        status_emoji = {
            "new": "🆕",
            "qualified": "✅",
            "hot": "🔥",
            "handed_off": "👤",
            "closed": "❌"
        }
        
        emoji = status_emoji.get(lead_info.get("status", "new"), "📍")
        
        message = f"""{emoji} *Новый лид!*

*Клиент:* {lead_info.get('client_name', 'Unknown')}
*Канал:* {lead_info.get('channel', 'Unknown')}
*Контакт:* {lead_info.get('contact', 'Unknown')}
*Статус:* {lead_info.get('status', 'new')}

*Квалификация:*
- Услуга: {lead_info.get('service', 'не указана')}
- Бюджет: {lead_info.get('budget', 'не указан')}
- Срочность: {lead_info.get('urgency', 'не указана')}
- Намерение записаться: {'Да' if lead_info.get('intent_to_book') else 'Нет'}
- Sentiment: {lead_info.get('sentiment', 'neutral')}

*Диалог:*
{conversation_transcript[:2000]}  # Limit length
"""
        
        return await self.send_message(owner_id, message, parse_mode="Markdown")
    
    def parse_update(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Telegram webhook update.
        Returns dict with chat_id, user_id, text, or None if not a text message.
        """
        if "message" not in update:
            return None
        
        message = update["message"]
        
        # Only handle text messages
        if "text" not in message:
            return None
        
        return {
            "chat_id": message["chat"]["id"],
            "user_id": message["from"]["id"],
            "text": message["text"],
            "message_id": message["message_id"],
            "timestamp": message.get("date")
        }


telegram_connector = TelegramConnector()
