import httpx
from typing import Dict, Any, Optional
from app.config import settings


class WhatsAppGreenAPIConnector:
    """
    Connector for WhatsApp via Green API (wa.green-api.com).
    Handles sending messages and receiving updates.
    """
    
    def __init__(self):
        self.instance_id = settings.green_api_id
        self.api_token = settings.green_api_token
        self.base_url = f"https://api.green-api.com/waInstance{self.instance_id}"
        self.timeout = 30.0
    
    def _get_auth_params(self) -> Dict[str, str]:
        return {
            "waInstanceidInstance": self.instance_id,
            "apiTokenInstance": self.api_token
        }
    
    async def send_message(
        self,
        chat_id: str,
        text: str
    ) -> bool:
        """
        Send a text message to a WhatsApp chat.
        chat_id should be in format: phoneNumber@c.us (e.g., 79991234567@c.us)
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                params=self._get_auth_params(),
                json={
                    "chatId": chat_id,
                    "message": text
                }
            )
            return response.status_code == 200
    
    async def send_chat_action(self, chat_id: str, action: str = "typing") -> bool:
        """
        Send chat action (typing indicator).
        Green API supports: typing, recordAudio, upload
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendChatAction",
                params=self._get_auth_params(),
                json={
                    "chatId": chat_id,
                    "action": action
                }
            )
            return response.status_code == 200
    
    async def notify_owner(
        self,
        owner_phone: str,
        lead_info: Dict[str, Any],
        conversation_transcript: str
    ) -> bool:
        """
        Send lead notification to owner via WhatsApp.
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
{conversation_transcript[:2000]}
"""
        
        return await self.send_message(owner_phone, message)
    
    def parse_webhook(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Green API webhook.
        Returns dict with chat_id, sender, text, or None if not a text message.
        
        Green API webhook format:
        {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {...},
            "timestamp": 1234567890,
            "idMessage": "...",
            "senderData": {...},
            "messageData": {...}
        }
        """
        # Only process incoming messages
        if webhook_data.get("typeWebhook") != "incomingMessageReceived":
            return None
        
        message_data = webhook_data.get("messageData", {})
        
        # Only handle text messages (filter out media, stickers, etc.)
        if message_data.get("typeMessage") != "textMessage":
            return None
        
        text_message = message_data.get("textMessageData", {})
        text = text_message.get("textMessage")
        
        if not text:
            return None
        
        sender_data = webhook_data.get("senderData", {})
        chat_id = sender_data.get("chatId")
        sender = sender_data.get("sender")
        
        return {
            "chat_id": chat_id,
            "sender": sender,
            "text": text,
            "message_id": webhook_data.get("idMessage"),
            "timestamp": webhook_data.get("timestamp")
        }


whatsapp_connector = WhatsAppGreenAPIConnector()
