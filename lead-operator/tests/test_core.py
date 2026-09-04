import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


class TestLLMClient:
    """Tests for LLM client JSON extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_qualification_success(self):
        """Test that qualification extraction returns valid JSON."""
        from app.llm.client import DashScopeClient
        
        # Mock response
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"service": "Стрижка", "budget": 1500, "urgency": "high", "intent_to_book": true, "sentiment": "positive", "wants_human": false}'
                },
                "finish_reason": "stop"
            }]
        }
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()
            
            client = DashScopeClient()
            result = await client.extract_json(
                system_prompt="Test prompt",
                user_message="I want to book a haircut for tomorrow",
                json_schema_description='{"service": "string", "budget": "number"}'
            )
            
            assert result["service"] == "Стрижка"
            assert result["budget"] == 1500
            assert result["urgency"] == "high"
            assert result["intent_to_book"] is True
    
    @pytest.mark.asyncio
    async def test_extract_qualification_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        from app.llm.client import DashScopeClient
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": '```json\n{"service": "Маникюр", "budget": 1200}\n```'
                },
                "finish_reason": "stop"
            }]
        }
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()
            
            client = DashScopeClient()
            result = await client.extract_json(
                system_prompt="Test",
                user_message="Test message",
                json_schema_description='{}'
            )
            
            assert result["service"] == "Маникюр"
            assert result["budget"] == 1200


class TestQualifier:
    """Tests for qualification extraction."""
    
    @pytest.mark.asyncio
    async def test_check_handoff_rules_wants_human(self):
        """Test handoff trigger when customer wants human."""
        from app.core.qualifier import check_handoff_rules
        
        qual = {
            "wants_human": True,
            "sentiment": "neutral"
        }
        
        should_handoff, reason = check_handoff_rules(qual, {})
        
        assert should_handoff is True
        assert reason == "customer_requested_human"
    
    @pytest.mark.asyncio
    async def test_check_handoff_rules_negative_sentiment(self):
        """Test handoff trigger on negative sentiment."""
        from app.core.qualifier import check_handoff_rules
        
        qual = {
            "wants_human": False,
            "sentiment": "negative"
        }
        
        should_handoff, reason = check_handoff_rules(qual, {})
        
        assert should_handoff is True
        assert reason == "negative_sentiment"
    
    @pytest.mark.asyncio
    async def test_check_handoff_rules_faq_exhausted(self):
        """Test handoff trigger after 2 FAQ misses."""
        from app.core.qualifier import check_handoff_rules
        
        qual = {"sentiment": "neutral"}
        
        should_handoff, reason = check_handoff_rules(qual, {}, faq_miss_count=2)
        
        assert should_handoff is True
        assert reason == "faq_exhausted"
    
    @pytest.mark.asyncio
    async def test_check_handoff_rules_high_budget(self):
        """Test handoff trigger on high budget."""
        from app.core.qualifier import check_handoff_rules
        
        qual = {
            "budget": 10000,
            "sentiment": "neutral"
        }
        
        handoff_rules = {"high_budget_threshold": 5000}
        should_handoff, reason = check_handoff_rules(qual, handoff_rules)
        
        assert should_handoff is True
        assert reason == "high_budget"
    
    @pytest.mark.asyncio
    async def test_no_handoff_triggered(self):
        """Test that no handoff is triggered for normal lead."""
        from app.core.qualifier import check_handoff_rules
        
        qual = {
            "budget": 2000,
            "sentiment": "positive",
            "wants_human": False
        }
        
        should_handoff, reason = check_handoff_rules(qual, {}, faq_miss_count=0)
        
        assert should_handoff is False
        assert reason is None


class TestBookingManager:
    """Tests for slot booking logic."""
    
    @pytest.mark.asyncio
    async def test_lock_slot_success(self):
        """Test successful slot locking."""
        from app.core.booking import BookingManager
        from datetime import datetime
        
        booking_mgr = BookingManager()
        slot_dt = datetime(2025, 1, 15, 14, 0)
        
        with patch.object(booking_mgr.redis, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = True
            
            result = await booking_mgr.lock_slot(1, slot_dt, 123)
            
            assert result is True
            mock_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lock_slot_already_taken(self):
        """Test slot locking fails when already booked."""
        from app.core.booking import BookingManager
        from datetime import datetime
        
        booking_mgr = BookingManager()
        slot_dt = datetime(2025, 1, 15, 14, 0)
        
        with patch.object(booking_mgr.redis, 'set', new_callable=AsyncMock) as mock_set:
            mock_set.return_value = False  # NX failed, key exists
            
            result = await booking_mgr.lock_slot(1, slot_dt, 123)
            
            assert result is False


class TestTelegramConnector:
    """Tests for Telegram connector."""
    
    def test_parse_update_valid(self):
        """Test parsing valid Telegram update."""
        from app.connectors.telegram import telegram_connector
        
        update = {
            "message": {
                "chat": {"id": 123456},
                "from": {"id": 789012},
                "text": "Hello!",
                "message_id": 42,
                "date": 1234567890
            }
        }
        
        parsed = telegram_connector.parse_update(update)
        
        assert parsed is not None
        assert parsed["chat_id"] == 123456
        assert parsed["user_id"] == 789012
        assert parsed["text"] == "Hello!"
    
    def test_parse_update_ignored_media(self):
        """Test that non-text messages are ignored."""
        from app.connectors.telegram import telegram_connector
        
        update = {
            "message": {
                "chat": {"id": 123456},
                "photo": [{"file_id": "abc123"}]  # Photo message
            }
        }
        
        parsed = telegram_connector.parse_update(update)
        
        assert parsed is None
    
    def test_parse_update_ignored_no_message(self):
        """Test that updates without message field are ignored."""
        from app.connectors.telegram import telegram_connector
        
        update = {
            "callback_query": {"id": "xyz"}
        }
        
        parsed = telegram_connector.parse_update(update)
        
        assert parsed is None


class TestWhatsAppConnector:
    """Tests for WhatsApp Green API connector."""
    
    def test_parse_webhook_valid(self):
        """Test parsing valid WhatsApp webhook."""
        from app.connectors.whatsapp_greenapi import whatsapp_connector
        
        webhook = {
            "typeWebhook": "incomingMessageReceived",
            "instanceData": {"idInstance": 123},
            "timestamp": 1234567890,
            "idMessage": "msg_abc123",
            "senderData": {
                "chatId": "79991234567@c.us",
                "sender": "79991234567@c.us"
            },
            "messageData": {
                "typeMessage": "textMessage",
                "textMessageData": {
                    "textMessage": "Привет, хочу записаться!"
                }
            }
        }
        
        parsed = whatsapp_connector.parse_webhook(webhook)
        
        assert parsed is not None
        assert parsed["chat_id"] == "79991234567@c.us"
        assert parsed["text"] == "Привет, хочу записаться!"
    
    def test_parse_webhook_ignored_media(self):
        """Test that media messages are ignored."""
        from app.connectors.whatsapp_greenapi import whatsapp_connector
        
        webhook = {
            "typeWebhook": "incomingMessageReceived",
            "messageData": {
                "typeMessage": "imageMessage"  # Image, not text
            }
        }
        
        parsed = whatsapp_connector.parse_webhook(webhook)
        
        assert parsed is None
    
    def test_parse_webhook_ignored_outgoing(self):
        """Test that outgoing messages are ignored."""
        from app.connectors.whatsapp_greenapi import whatsapp_connector
        
        webhook = {
            "typeWebhook": "outgoingMessageStatus"
        }
        
        parsed = whatsapp_connector.parse_webhook(webhook)
        
        assert parsed is None
