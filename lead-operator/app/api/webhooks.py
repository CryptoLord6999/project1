from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import asyncio

from app.db.session import get_db, init_db
from app.db.models import Lead, LeadStatus, Message, ClientConfig, SlotBooking
from app.core.dialogue import dialogue_manager
from app.core.qualifier import extract_qualification, check_handoff_rules
from app.core.booking import booking_manager
from app.core.handoff import handle_handoff, should_trigger_handoff
from app.llm.client import llm_client
from app.llm.prompts import build_system_prompt, build_tools_definition
from app.connectors.telegram import telegram_connector
from app.connectors.whatsapp_greenapi import whatsapp_connector
from app.config import settings

app = FastAPI(title="Lead Operator MVP")


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()
    # Load client configs from YAML files
    await load_client_configs()


async def load_client_configs():
    """Load client configurations from YAML files into database."""
    import yaml
    import os
    from pathlib import Path
    from sqlalchemy import select
    
    clients_dir = Path("clients")
    if not clients_dir.exists():
        return
    
    # This would be implemented to parse YAML and upsert to DB
    # For MVP, we assume configs are loaded manually or via admin endpoint
    pass


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Handle incoming Telegram messages."""
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    parsed = telegram_connector.parse_update(update)
    if not parsed:
        return {"status": "ignored"}  # Not a text message
    
    chat_id = parsed["chat_id"]
    user_id = parsed["user_id"]
    text = parsed["text"]
    
    # Process message asynchronously
    background_tasks.add_task(process_message, "telegram", chat_id, str(user_id), text, db)
    
    return {"status": "ok"}


@app.post("/webhook/whatsapp/{instance_id}")
async def whatsapp_webhook(request: Request, instance_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Handle incoming WhatsApp messages via Green API webhook."""
    if instance_id != settings.green_api_id:
        raise HTTPException(status_code=403, detail="Invalid instance ID")
    
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    parsed = whatsapp_connector.parse_webhook(update)
    if not parsed:
        return {"status": "ignored"}  # Not a text message
    
    chat_id = parsed["chat_id"]
    sender = parsed["sender"]
    text = parsed["text"]
    
    # Process message asynchronously
    background_tasks.add_task(process_message, "whatsapp", chat_id, sender, text, db)
    
    return {"status": "ok"}


async def process_message(
    channel: str,
    chat_id: str,
    contact: str,
    text: str,
    db: Session
):
    """
    Main message processing pipeline.
    1. Find or create lead
    2. Get conversation context
    3. Call LLM
    4. Handle tool calls (booking, handoff)
    5. Send response
    """
    from sqlalchemy import select
    from datetime import datetime
    
    # Determine client_id (for MVP, use first client or derive from chat_id)
    # In production, map chat_id to client via config
    result = db.execute(select(ClientConfig).limit(1))
    client = result.scalar_one_or_none()
    
    if not client:
        return  # No client configured
    
    client_id = client.id
    
    # Find or create lead
    result = db.execute(
        select(Lead).where(
            Lead.client_id == client_id,
            Lead.channel == channel,
            Lead.contact == contact
        )
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        lead = Lead(
            client_id=client_id,
            channel=channel,
            contact=contact,
            status=LeadStatus.NEW,
            qualification={}
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
    
    # Save user message
    user_msg = Message(lead_id=lead.id, role="user", text=text)
    db.add(user_msg)
    db.commit()
    
    # Add to dialogue context
    await dialogue_manager.add_message(lead.id, "user", text)
    
    # Build system prompt
    system_prompt = build_system_prompt(
        client_name=client.name,
        tone=client.tone,
        services=client.services or [],
        prices=client.prices or {},
        faq=client.faq or {}
    )
    
    # Build LLM context
    llm_messages = await dialogue_manager.build_llm_context(lead.id, system_prompt)
    
    # Show typing indicator if taking time
    typing_task = asyncio.create_task(show_typing_indicator(channel, chat_id))
    
    # Call LLM
    tools = build_tools_definition()
    response = await llm_client.chat_completion(
        messages=llm_messages,
        tools=tools,
        temperature=0.7
    )
    
    # Cancel typing indicator
    typing_task.cancel()
    
    agent_text = response["content"]
    tool_calls = response.get("tool_calls", [])
    
    # Process tool calls
    faq_miss_count = 0  # Track FAQ misses (would need more sophisticated tracking)
    handoff_triggered = False
    handoff_reason = None
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        args = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
        
        if tool_name == "save_lead":
            # Update qualification
            current_qual = lead.qualification or {}
            current_qual.update(args)
            lead.qualification = current_qual
            
            # Update status based on qualification
            if current_qual.get("intent_to_book"):
                lead.status = LeadStatus.QUALIFIED
        
        elif tool_name == "book_slot":
            # Parse datetime
            slot_dt = datetime.fromisoformat(args["datetime"])
            service = args.get("service")
            
            # Lock and confirm slot
            locked = await booking_manager.lock_slot(client_id, slot_dt, lead.id)
            if locked:
                booking = await booking_manager.confirm_booking(client_id, slot_dt, lead.id, db)
                agent_text += f"\n✅ Запись подтверждена на {slot_dt.strftime('%d.%m.%Y в %H:%M')}."
                lead.status = LeadStatus.HOT
        
        elif tool_name == "handoff":
            handoff_triggered = True
            handoff_reason = args.get("reason", "unspecified")
    
    # Check hard rules for handoff
    if not handoff_triggered:
        qual = lead.qualification or {}
        triggered, reason = should_trigger_handoff(
            tool_call_name=None,
            qualification=qual,
            faq_miss_count=faq_miss_count,
            handoff_rules=client.handoff_rules or {}
        )
        if triggered:
            handoff_triggered = True
            handoff_reason = reason
    
    # Handle handoff if triggered
    if handoff_triggered:
        await handle_handoff(lead, handoff_reason, db)
        agent_text = "Передаю вас специалисту. Он скоро свяжется с вами."
    
    # Save agent response
    agent_msg = Message(lead_id=lead.id, role="agent", text=agent_text)
    db.add(agent_msg)
    db.commit()
    
    # Add to dialogue context
    await dialogue_manager.add_message(lead.id, "agent", agent_text)
    
    # Send response
    if channel == "telegram":
        await telegram_connector.send_message(int(chat_id), agent_text)
    elif channel == "whatsapp":
        await whatsapp_connector.send_message(chat_id, agent_text)


async def show_typing_indicator(channel: str, chat_id: str):
    """Send typing indicator for a few seconds."""
    try:
        await asyncio.sleep(1)  # Wait a bit before showing typing
        
        if channel == "telegram":
            await telegram_connector.send_chat_action(int(chat_id), "typing")
        elif channel == "whatsapp":
            await whatsapp_connector.send_chat_action(chat_id, "typing")
        
        # Keep indicator alive for up to 5 seconds
        for _ in range(5):
            await asyncio.sleep(1)
            if channel == "telegram":
                await telegram_connector.send_chat_action(int(chat_id), "typing")
            elif channel == "whatsapp":
                await whatsapp_connector.send_chat_action(chat_id, "typing")
    except asyncio.CancelledError:
        pass  # Response ready, stop typing
    except Exception:
        pass  # Ignore errors in typing indicator


import json

# Re-export app for uvicorn
__all__ = ["app"]
