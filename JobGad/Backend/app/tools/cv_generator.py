"""
CV Generator — uses Gemini AI to generate a tailored, professional CV
based on the user's profile and a specific job listing.
"""
import json
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


async def generate_cv_content(
    profile: dict,
    job: dict,
    additional_info: dict = None,
) -> dict:
    """
    Use Gemini to generate a tailored CV for a specific job.
    
    Returns structured CV data:
    {
        "personal_info": {...},
        "professional_summary": "...",
        "relevant_skills": [...],
        "experience": [...],
        "education": [...],
        "projects": [...],
        "certifications": [...],
        "missing_info_questions": [...]  # Questions if profile is incomplete
    }
    """
    additional = json.dumps(additional_info) if additional_info else "None provided"

    prompt = f"""
    You are an expert CV writer and career coach. Generate a professional, 
    tailored CV for the following candidate applying for a specific job.

    CANDIDATE PROFILE:
    - Full Name: {profile.get('full_name', 'Not provided')}
    - Headline: {profile.get('headline', 'Not provided')}
    - Bio: {profile.get('bio', 'Not provided')}
    - Education Level: {profile.get('education_level', 'Not provided')}
    - Field of Study: {profile.get('field_of_study', 'Not provided')}
    - Institution: {profile.get('institution', 'Not provided')}
    - Graduation Year: {profile.get('graduation_year', 'Not provided')}
    - Target Role: {profile.get('target_role', 'Not provided')}
    - Skills: {', '.join(profile.get('skills', [])) or 'Not provided'}
    - GitHub: {profile.get('github_url', 'Not provided')}
    - LinkedIn: {profile.get('linkedin_url', 'Not provided')}

    JOB BEING APPLIED FOR:
    - Job Title: {job.get('title', 'Not provided')}
    - Company: {job.get('company', 'Not provided')}
    - Location: {job.get('location', 'Not provided')}
    - Employment Type: {job.get('employment_type', 'Not provided')}
    - Job Description: {job.get('description', 'Not provided')[:1000]}
    - Requirements: {job.get('requirements', 'Not provided')[:800]}

    ADDITIONAL INFORMATION PROVIDED BY CANDIDATE:
    {additional}

    INSTRUCTIONS:
    1. Generate a TAILORED CV that highlights skills and experience 
       most relevant to THIS specific job
    2. Only include skills that match or relate to the job requirements
    3. Write a compelling professional summary specifically for this role
    4. If the profile is missing important information for this role,
       list questions in missing_info_questions
    5. Make the CV professional, concise, and ATS-friendly
    6. Return ONLY valid JSON, no explanation, no markdown

    Return this exact JSON structure:
    {{
        "personal_info": {{
            "full_name": "...",
            "email": "...",
            "linkedin": "...",
            "github": "...",
            "location": "..."
        }},
        "professional_summary": "2-3 sentence compelling summary tailored to this role",
        "relevant_skills": {{
            "technical": ["skill1", "skill2"],
            "soft": ["skill1", "skill2"],
            "tools": ["tool1", "tool2"]
        }},
        "education": [
            {{
                "degree": "...",
                "field": "...",
                "institution": "...",
                "year": "...",
                "achievements": "..."
            }}
        ],
        "experience": [
            {{
                "title": "...",
                "company": "...",
                "duration": "...",
                "responsibilities": ["...", "..."],
                "achievements": ["...", "..."]
            }}
        ],
        "projects": [
            {{
                "name": "...",
                "description": "...",
                "technologies": ["...", "..."],
                "link": "..."
            }}
        ],
        "certifications": ["cert1", "cert2"],
        "missing_info_questions": [
            "Question if profile is missing important info for this role"
        ]
    }}
    """

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except Exception as e:
        print(f"[CV Generator] Content generation failed: {e}")
        return {
            "personal_info": {"full_name": profile.get("full_name", "")},
            "professional_summary": profile.get("bio", ""),
            "relevant_skills": {"technical": profile.get("skills", [])},
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "missing_info_questions": [],
        }


async def generate_cv_with_clarifications(
    profile: dict,
    job: dict,
    answers: dict,
) -> dict:
    """
    Regenerate CV after user has answered clarifying questions.
    Merges answers into profile before generating.
    """
    # Merge answers into profile
    enriched_profile = {**profile}
    if answers:
        enriched_profile["additional_experience"] = answers.get(
            "experience", ""
        )
        enriched_profile["additional_projects"] = answers.get("projects", "")
        enriched_profile["certifications"] = answers.get("certifications", "")
        enriched_profile["additional_skills"] = answers.get("skills", "")

    return await generate_cv_content(
        profile=enriched_profile,
        job=job,
        additional_info=answers,
    )