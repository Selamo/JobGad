import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    
    headline = Column(String(255))
    bio = Column(Text)
    github_url = Column(String(500))
    linkedin_url = Column(String(500))
    portfolio_url = Column(String(500))
    
    education_level = Column(String(100))
    field_of_study = Column(String(255))
    institution = Column(String(255))
    graduation_year = Column(Integer)
    target_role = Column(String(255))
    
    iri_score = Column(Float, default=0.0)
    profile_completeness = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

  # Relationships
    user = relationship("User", back_populates="profile")
    skills = relationship("Skill", back_populates="profile", cascade="all, delete-orphan")
    skill_vector = relationship("SkillVector", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    job_matches = relationship("JobMatch", back_populates="profile", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="profile", cascade="all, delete-orphan")

class Skill(Base):
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    
    name = Column(String(255), nullable=False)
    category = Column(String(100)) # technical | soft | tool | domain
    proficiency = Column(String(50)) # beginner | intermediate | advanced | expert
    source = Column(String(100)) # extracted | self_reported | inferred
    confidence = Column(Float, default=1.0)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="skills")

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    
    type = Column(String(100), nullable=False) # cv | portfolio | transcript | project
    file_name = Column(String(500))
    storage_url = Column(String(1000))
    extracted_text = Column(Text)
    processing_status = Column(String(50), default="pending")
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="documents")

class SkillVector(Base):
    __tablename__ = "skill_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), unique=True)
    
    pinecone_vector_id = Column(String(255))
    embedding_model = Column(String(255))
    
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="skill_vector")
