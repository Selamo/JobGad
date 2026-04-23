import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class JobListing(Base):
    __tablename__ = "job_listings"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title           = Column(String(255), nullable=False)
    location        = Column(String(255))
    description     = Column(Text, nullable=False)
    requirements    = Column(Text)
    salary_range    = Column(String(100))
    employment_type = Column(String(100))  # full-time | part-time | contract | internship
    source          = Column(String(100))
    source_url      = Column(String(1000))
    pinecone_vector_id = Column(String(255))
    is_active       = Column(Boolean, default=True)
    posted_at       = Column(DateTime(timezone=True), default=datetime.utcnow)

    # New fields
    company_id      = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    department_id   = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    posted_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    application_deadline = Column(DateTime(timezone=True), nullable=True)
    status          = Column(String(50), default="published")  # draft | published | closed

    # Relationships
    company          = relationship("Company", back_populates="job_listings")
    department       = relationship("Department", back_populates="job_listings")
    poster           = relationship("User", foreign_keys=[posted_by])
    matches          = relationship("JobMatch", back_populates="job", cascade="all, delete-orphan")
    coaching_sessions = relationship("CoachingSession", back_populates="target_job")
    applications     = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    generated_cvs    = relationship("GeneratedCV", back_populates="job", cascade="all, delete-orphan")


class JobMatch(Base):
    __tablename__ = "job_matches"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id       = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    job_id           = Column(UUID(as_uuid=True), ForeignKey("job_listings.id", ondelete="CASCADE"))
    similarity_score = Column(Float, nullable=False)
    match_reason     = Column(Text)
    status           = Column(String(50), default="suggested")  # suggested | saved | applied | rejected
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('profile_id', 'job_id', name='_profile_job_uc'),)

    # Relationships
    profile = relationship("Profile", back_populates="job_matches")
    job     = relationship("JobListing", back_populates="matches")