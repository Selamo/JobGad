"""
CV Generator — uses Groq AI to generate a tailored, professional CV.
Groq is used for fast text generation.
Gemini Live is reserved for audio interview coaching only.
"""
import json
import asyncio
from typing import Optional

from app.core.config import settings


def _build_prompt(profile: dict, job: dict, additional_info: Optional[dict] = None) -> str:
    additional = json.dumps(additional_info) if additional_info else "None provided"
    return f"""You are an expert CV writer and career coach. Generate a professional,
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
- Additional Experience: {profile.get('additional_experience', 'Not provided')}
- Additional Projects: {profile.get('additional_projects', 'Not provided')}
- Additional Skills: {profile.get('additional_skills', 'Not provided')}
- Certifications: {profile.get('certifications', 'Not provided')}

JOB BEING APPLIED FOR:
- Job Title: {job.get('title', 'Not provided')}
- Company: {job.get('company', 'Not provided')}
- Location: {job.get('location', 'Not provided')}
- Employment Type: {job.get('employment_type', 'Not provided')}
- Job Description: {job.get('description', 'Not provided')[:1000]}
- Requirements: {job.get('requirements', 'Not provided')[:800]}

ADDITIONAL INFORMATION:
{additional}

INSTRUCTIONS:
1. Generate a TAILORED CV highlighting skills most relevant to THIS specific job
2. Write a compelling professional summary for this role
3. If the profile is missing important info, list 2-4 specific questions in missing_info_questions
4. If profile has enough info, return empty array for missing_info_questions
5. Make the CV professional, concise, and ATS-friendly
6. Return ONLY valid JSON, no markdown backticks, no explanation

Return EXACTLY this JSON structure:
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
        "What is your work experience? (internships, part-time, freelance)",
        "Do you have any projects you have built? Please describe them.",
        "Do you have any certifications or online courses completed?"
    ]
}}"""


def _call_groq(prompt: str) -> Optional[dict]:
    """Synchronous Groq call — run in thread pool."""
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert CV writer. Always respond with valid JSON only. No markdown, no backticks, no explanation."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content.strip()

        # Clean up any accidental markdown
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except Exception as e:
        print(f"[CV Generator - Groq] Generation failed: {e}")
        return None


def _fallback_cv(profile: dict) -> dict:
    """Return a minimal CV if AI fails."""
    return {
        "personal_info": {
            "full_name": profile.get("full_name", ""),
            "email": profile.get("email", ""),
            "linkedin": profile.get("linkedin_url", ""),
            "github": profile.get("github_url", ""),
            "location": "",
        },
        "professional_summary": profile.get("bio", ""),
        "relevant_skills": {
            "technical": profile.get("skills", []),
            "soft": [],
            "tools": [],
        },
        "education": [{
            "degree": profile.get("education_level", ""),
            "field": profile.get("field_of_study", ""),
            "institution": profile.get("institution", ""),
            "year": str(profile.get("graduation_year", "")),
            "achievements": "",
        }],
        "experience": [],
        "projects": [],
        "certifications": [],
        "missing_info_questions": [
            "What is your work experience? (internships, part-time, freelance)",
            "Do you have any projects you have built?",
            "Do you have any certifications or online courses?",
        ],
    }


async def generate_cv_content(
    profile: dict,
    job: dict,
    additional_info: Optional[dict] = None,
) -> dict:
    """Generate tailored CV content using Groq AI."""
    prompt = _build_prompt(profile, job, additional_info)

    # Run synchronous Groq call in thread pool
    result = await asyncio.get_event_loop().run_in_executor(
        None, _call_groq, prompt
    )

    if result is None:
        print("[CV Generator] Groq failed, using fallback CV")
        return _fallback_cv(profile)

    return result


async def generate_cv_with_clarifications(
    profile: dict,
    job: dict,
    answers: dict,
) -> dict:
    """Regenerate CV after user has answered clarifying questions."""
    enriched_profile = {**profile}
    if answers:
        # Map answers to profile fields — handles both keyed and question-text keys
        enriched_profile["additional_experience"] = answers.get(
            "experience",
            answers.get("What is your work experience? (internships, part-time, freelance)", "")
        )
        enriched_profile["additional_projects"] = answers.get(
            "projects",
            answers.get("Do you have any projects you have built?", "")
        )
        enriched_profile["certifications"] = answers.get(
            "certifications",
            answers.get("Do you have any certifications or online courses?", "")
        )
        enriched_profile["additional_skills"] = answers.get("skills", "")

    return await generate_cv_content(
        profile=enriched_profile,
        job=job,
        additional_info=answers,
    )