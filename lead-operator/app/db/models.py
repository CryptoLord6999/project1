from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class LeadStatus(enum.Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    HOT = "hot"
    HANDED_OFF = "handed_off"
    CLOSED = "closed"


class ClientConfig(Base):
    __tablename__ = "client_configs"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    # Channels and credentials stored securely or referenced
    telegram_chat_id = Column(String(255))
    whatsapp_phone = Column(String(50))
    # Services, prices, FAQ, slots stored as JSON
    services = Column(JSON, default=list)
    prices = Column(JSON, default=dict)
    faq = Column(JSON, default=dict)
    slots = Column(JSON, default=list)
    tone = Column(String(255), default="friendly")
    handoff_rules = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    leads = relationship("Lead", back_populates="client_config")


class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("client_configs.id"), nullable=False)
    channel = Column(String(50), nullable=False)  # 'telegram' or 'whatsapp'
    contact = Column(String(255), nullable=False)  # chat_id or phone
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW)
    qualification = Column(JSON, default=dict)  # {service, budget, urgency, intent, sentiment, wants_human}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client_config = relationship("ClientConfig", back_populates="leads")
    messages = relationship("Message", back_populates="lead", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user', 'agent', 'owner'
    text = Column(Text, nullable=False)
    ts = Column(DateTime, default=datetime.utcnow)
    
    lead = relationship("Lead", back_populates="messages")


class SlotBooking(Base):
    __tablename__ = "slot_bookings"
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("client_configs.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    slot_datetime = Column(DateTime, nullable=False)
    status = Column(String(50), default="pending")  # pending, confirmed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    
    lead = relationship("Lead")
