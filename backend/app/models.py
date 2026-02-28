from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./bulk_mailer.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    unsubscribed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    subject = Column(String)
    body = Column(Text)
    status = Column(String, default="draft")  # draft, running, completed, paused
    created_at = Column(DateTime, default=datetime.utcnow)

class SendingLog(Base):
    __tablename__ = "sending_logs"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    status = Column(String) # sending, sent, failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign")
    contact = relationship("Contact")

def init_db():
    Base.metadata.create_all(bind=engine)
