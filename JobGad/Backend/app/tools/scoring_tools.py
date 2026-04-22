"""
Scoring tools — human-readable match explanation generators.

These are pure utility functions with no I/O; they turn raw similarity scores
and structured data into meaningful text that the frontend can display.
"""
from app.models.job import JobListing
from app.models.profile import Profile


# ─── Match Score Tier ─────────────────────────────────────────────────────────

def score_to_tier(score: float) -> str:
    """
    Convert a cosine similarity score (0.0 – 1.0) into a human-readable tier.

    Tiers:
      ≥ 0.85  → Excellent Match
      ≥ 0.70  → Strong Match
      ≥ 0.55  → Good Match
      ≥ 0.40  → Partial Match
      < 0.40  → Weak Match
    """
    if score >= 0.85:
        return "Excellent Match"
    elif score >= 0.70:
        return "Strong Match"
    elif score >= 0.55:
        return "Good Match"
    elif score >= 0.40:
        return "Partial Match"
    return "Weak Match"


# ─── Skill Overlap ────────────────────────────────────────────────────────────

def find_skill_overlap(profile: Profile, job: JobListing) -> dict:
    """
    Compare a user's skill list to the keywords in a job's requirements text.
    Returns matching and missing skill sets.
    """
    if not job.requirements:
        return {"matched": [], "missing": []}

    profile_skill_names = {s.name.lower() for s in (profile.skills or [])}
    req_words = set(job.requirements.lower().split())

    # Simple keyword intersection (good enough without NLP)
    matched = sorted(
        name for name in profile_skill_names if name in req_words
    )
    # Words in requirements that look like skills (longer tokens, not stopwords)
    stopwords = {"and", "or", "the", "of", "in", "a", "an", "to", "with", "for",
                 "is", "are", "be", "that", "this", "will", "must", "can", "etc"}
    potential_skills = {
        w for w in req_words if len(w) > 3 and w not in stopwords
    }
    missing = sorted(potential_skills - profile_skill_names)[:10]  # cap at 10

    return {"matched": matched, "missing": missing}


# ─── Match Reason Text ────────────────────────────────────────────────────────

def build_match_reason(
    score: float,
    profile: Profile,
    job: JobListing,
) -> str:
    """
    Generate a plain-English explanation of why a job was matched to a profile.
    Stored in JobMatch.match_reason for display in the UI.
    """
    tier = score_to_tier(score)
    overlap = find_skill_overlap(profile, job)
    matched = overlap["matched"]
    missing = overlap["missing"]

    parts = [f"{tier} (similarity: {score:.0%})."]

    if matched:
        skill_list = ", ".join(matched[:5])
        parts.append(f"Your skills match key requirements: {skill_list}.")
    else:
        parts.append("Your overall profile aligns well with this role.")

    if profile.target_role and profile.target_role.lower() in job.title.lower():
        parts.append(f"This role aligns with your target role: {profile.target_role}.")

    if missing:
        gap_list = ", ".join(missing[:3])
        parts.append(f"Potential skill gaps to address: {gap_list}.")

    return " ".join(parts)


# ─── Profile Text Builder ─────────────────────────────────────────────────────

def build_profile_text(profile: Profile) -> str:
    """
    Concatenate profile fields into a single text string for embedding.
    This is the representation that gets compared against job embeddings.
    """
    parts = []

    if profile.headline:
        parts.append(profile.headline)
    if profile.bio:
        parts.append(profile.bio)
    if profile.target_role:
        parts.append(f"Target role: {profile.target_role}")
    if profile.field_of_study:
        parts.append(f"Field of study: {profile.field_of_study}")
    if profile.education_level:
        parts.append(f"Education: {profile.education_level}")
    if profile.skills:
        skill_names = ", ".join(s.name for s in profile.skills)
        parts.append(f"Skills: {skill_names}")

    return " | ".join(parts) if parts else "Graduate profile"


# ─── Job Text Builder ─────────────────────────────────────────────────────────

def build_job_text(job: JobListing) -> str:
    """
    Concatenate job fields into a single text string for embedding.
    """
    parts = [job.title]
    if job.description:
        # Truncate to 512 chars to stay within embedding model limits
        parts.append(job.description[:512])
    if job.requirements:
        parts.append(job.requirements[:256])
    if job.employment_type:
        parts.append(job.employment_type)
    return " | ".join(parts)
