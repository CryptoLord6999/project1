from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import SlotBooking, ClientConfig
import redis.asyncio as redis
from app.config import settings


class BookingManager:
    """
    Manages slot booking with atomic operations to prevent double-booking.
    """
    
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.booking_ttl = 300  # 5 minutes for pending bookings
    
    async def get_available_slots(
        self,
        client_id: int,
        db: Session,
        date: Optional[str] = None
    ) -> list[datetime]:
        """
        Get available slots for a client on a given date.
        Returns list of datetime objects.
        """
        # Get client config
        result = db.execute(
            select(ClientConfig).where(ClientConfig.id == client_id)
        )
        client = result.scalar_one_or_none()
        
        if not client:
            return []
        
        slots_config = client.slots or []
        available = []
        
        now = datetime.utcnow()
        
        for slot_str in slots_config:
            slot_dt = datetime.fromisoformat(slot_str)
            
            # Skip past slots
            if slot_dt <= now:
                continue
            
            # Check if already booked
            is_booked = await self._is_slot_booked(client_id, slot_dt, db)
            if not is_booked:
                available.append(slot_dt)
        
        return available
    
    async def _is_slot_booked(
        self,
        client_id: int,
        slot_dt: datetime,
        db: Session
    ) -> bool:
        """Check if slot is already booked or pending."""
        # Check confirmed bookings in DB
        result = db.execute(
            select(SlotBooking).where(
                SlotBooking.client_id == client_id,
                SlotBooking.slot_datetime == slot_dt,
                SlotBooking.status.in_(["confirmed", "pending"])
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return True
        
        # Check pending locks in Redis
        lock_key = f"slot_lock:{client_id}:{slot_dt.isoformat()}"
        if await self.redis.exists(lock_key):
            return True
        
        return False
    
    async def lock_slot(
        self,
        client_id: int,
        slot_dt: datetime,
        lead_id: int
    ) -> bool:
        """
        Lock a slot temporarily (pending confirmation).
        Returns True if lock was successful, False if slot is already taken.
        """
        lock_key = f"slot_lock:{client_id}:{slot_dt.isoformat()}"
        
        # Try to set lock with NX (only if not exists)
        locked = await self.redis.set(
            lock_key,
            str(lead_id),
            nx=True,
            ex=self.booking_ttl
        )
        
        return bool(locked)
    
    async def confirm_booking(
        self,
        client_id: int,
        slot_dt: datetime,
        lead_id: int,
        db: Session
    ) -> Optional[SlotBooking]:
        """
        Confirm a pending booking in database.
        """
        # Create booking record
        booking = SlotBooking(
            client_id=client_id,
            lead_id=lead_id,
            slot_datetime=slot_dt,
            status="confirmed"
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        
        # Remove Redis lock
        lock_key = f"slot_lock:{client_id}:{slot_dt.isoformat()}"
        await self.redis.delete(lock_key)
        
        return booking
    
    async def release_slot(
        self,
        client_id: int,
        slot_dt: datetime
    ):
        """Release a locked slot (cancel pending booking)."""
        lock_key = f"slot_lock:{client_id}:{slot_dt.isoformat()}"
        await self.redis.delete(lock_key)


booking_manager = BookingManager()
