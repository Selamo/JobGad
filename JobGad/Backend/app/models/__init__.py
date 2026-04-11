from app.core.database import Base
from app.models.user import User
from app.models.profile import Profile, Skill, Document, SkillVector
from app.models.job import JobListing, JobMatch
from app.models.coaching import CoachingSession, SessionMessage, Iriscore

# By importing all these here, SQLAlchemy knows about them when Base.metadata is accessed.
# This makes alembic configuration extremely straightforward because it can just import Base from here.
__all__ = [
    "Base",
    "User",
    "Profile",
    "Skill",
    "Document",
    "SkillVector",
    "JobListing",
    "JobMatch",
    "CoachingSession",
    "SessionMessage",
    "Iriscore"
]
