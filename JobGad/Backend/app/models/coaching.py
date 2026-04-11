import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class CoachingSession(Base):
    __tablename__ = "coaching_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    target_job_id = Column(UUID(as_uuid=True), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True)
    
    session_type = Column(String(100)) # behavioral | technical | mixed
    status = Column(String(50), default="active") # active | completed | paused
    
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    overall_score = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="coaching_sessions")
    target_job = relationship("JobListing", back_populates="coaching_sessions")
    messages = relationship("SessionMessage", back_populates="session", cascade="all, delete-orphan")

class SessionMessage(Base):
    __tablename__ = "session_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("coaching_sessions.id", ondelete="CASCADE"))
    
    role = Column(String(20), nullable=False) # interviewer | candidate
    content = Column(String, nullable=False)
    message_type = Column(String(50)) # question | answer | feedback | follow_up
    
    evaluation = Column(JSONB, nullable=True) # {score, clarity, accuracy, confidence, notes}
    sequence_no = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    session = relationship("CoachingSession", back_populates="messages")

class Iriscore(Base):
    __tablename__ = "iri_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    
    overall_score = Column(Float, nullable=False) # 0-100
    communication = Column(Float)
    technical_accuracy = Column(Float)
    confidence = Column(Float)
    structure = Column(Float)
    
    sessions_count = Column(Integer, default=0)
    snapshot_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="iri_scores")
