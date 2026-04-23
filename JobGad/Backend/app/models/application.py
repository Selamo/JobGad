import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id     = Column(UUID(as_uuid=True), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)

    # Status tracking
    # pending | reviewed | shortlisted | rejected | accepted
    status      = Column(String(50), default="pending", nullable=False)
    cover_letter = Column(Text, nullable=True)

    # Generated CV linked to this application
    generated_cv_id = Column(UUID(as_uuid=True), ForeignKey("generated_cvs.id", ondelete="SET NULL"), nullable=True)

    # HR review
    hr_notes    = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    applied_at  = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    job          = relationship("JobListing", back_populates="applications")
    user         = relationship("User", foreign_keys=[user_id], back_populates="applications")
    profile      = relationship("Profile", back_populates="applications")
    generated_cv = relationship("GeneratedCV", foreign_keys=[generated_cv_id])
    reviewer     = relationship("User", foreign_keys=[reviewed_by])


class GeneratedCV(Base):
    __tablename__ = "generated_cvs"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id   = Column(UUID(as_uuid=True), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=True)

    file_name        = Column(String(500))
    storage_url      = Column(String(1000))
    file_format      = Column(String(10), default="pdf")  # pdf | docx
    content_snapshot = Column(Text)  # Raw text used to generate the CV
    generated_at     = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="generated_cvs")
    job  = relationship("JobListing", back_populates="generated_cvs")


class Notification(Base):
    __tablename__ = "notifications"

    id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # application_received | status_changed | job_match | cv_ready
    type    = Column(String(50), nullable=False)
    title   = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)

    # Optional links
    related_job_id         = Column(UUID(as_uuid=True), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True)
    related_application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    user                = relationship("User", back_populates="notifications")
    related_job         = relationship("JobListing", foreign_keys=[related_job_id])
    related_application = relationship("Application", foreign_keys=[related_application_id])