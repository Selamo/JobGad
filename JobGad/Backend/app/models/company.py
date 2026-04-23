import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class JoinRequestStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class Company(Base):
    __tablename__ = "companies"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    industry    = Column(String(255))
    website     = Column(String(500))
    city        = Column(String(255))
    country     = Column(String(255))
    address     = Column(String(500))
    latitude    = Column(Float)
    longitude   = Column(Float)
    is_verified = Column(Boolean, default=False)

    # Who created this company
    created_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Superadmin approval
    status      = Column(String(50), default="pending")  # pending | approved | rejected
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at  = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator      = relationship("User", foreign_keys=[created_by])
    approver     = relationship("User", foreign_keys=[approved_by])
    departments  = relationship("Department", back_populates="company", cascade="all, delete-orphan")
    hr_profiles  = relationship("HRProfile", back_populates="company", cascade="all, delete-orphan")
    job_listings = relationship("JobListing", back_populates="company", cascade="all, delete-orphan")


class Department(Base):
    __tablename__ = "departments"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(255), nullable=False)
    description = Column(Text)
    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    company      = relationship("Company", back_populates="departments")
    job_listings = relationship("JobListing", back_populates="department")


class HRProfile(Base):
    __tablename__ = "hr_profiles"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_id       = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_title        = Column(String(255))
    is_company_admin = Column(Boolean, default=False)

    # Superadmin approval
    status      = Column(String(50), default="pending")  # pending | approved | rejected
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    user     = relationship("User", foreign_keys=[user_id], back_populates="hr_profile")
    company  = relationship("Company", back_populates="hr_profiles")
    approver = relationship("User", foreign_keys=[approved_by])


class CompanyJoinRequest(Base):
    __tablename__ = "company_join_requests"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    message    = Column(Text)
    status     = Column(
        SAEnum(JoinRequestStatus, name="join_request_status"),
        default=JoinRequestStatus.pending,
        nullable=False,
    )
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user     = relationship("User", foreign_keys=[user_id])
    company  = relationship("Company")
    reviewer = relationship("User", foreign_keys=[reviewed_by])