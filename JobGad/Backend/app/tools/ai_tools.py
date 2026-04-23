"""
AI tools — Gemini-powered skill extraction and profile analysis.
"""
import json
import google.generativeai as genai
from app.core.config import settings

# Configure Gemini once at module load
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


async def extract_skills_from_text(text: str) -> list[dict]:
    """
    Use Gemini to extract skills from CV/document text.
    Returns a list of dicts:
    [
        {"name": "Python", "category": "technical", "proficiency": "advanced"},
        {"name": "Team Leadership", "category": "soft", "proficiency": "intermediate"},
    ]
    """
    prompt = f"""
    You are an expert HR analyst. Analyze the following CV/resume text and extract all skills.

    For each skill, determine:
    - name: the skill name (e.g. "Python", "Machine Learning", "Team Leadership")
    - category: one of these exact values → technical | soft | tool | domain
    - proficiency: one of these exact values → beginner | intermediate | advanced | expert

    Rules:
    - Extract ONLY real skills, not job titles or company names
    - Be specific (e.g. "React.js" not just "web development")
    - Infer proficiency from context (years of experience, project complexity, etc.)
    - Return ONLY valid JSON array, no explanation, no markdown code blocks

    Return format:
    [
        {{"name": "Python", "category": "technical", "proficiency": "advanced"}},
        {{"name": "Communication", "category": "soft", "proficiency": "intermediate"}}
    ]

    CV Text:
    {text[:4000]}
    """

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Clean up if Gemini wraps response in markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        skills = json.loads(raw)

        # Validate each skill has required fields and correct values
        valid_categories = {"technical", "soft", "tool", "domain"}
        valid_proficiencies = {"beginner", "intermediate", "advanced", "expert"}

        cleaned = []
        for skill in skills:
            if not isinstance(skill, dict):
                continue

            name = skill.get("name", "").strip()
            category = skill.get("category", "technical").lower()
            proficiency = skill.get("proficiency", "intermediate").lower()

            if not name:
                continue
            if category not in valid_categories:
                category = "technical"
            if proficiency not in valid_proficiencies:
                proficiency = "intermediate"

            cleaned.append({
                "name": name,
                "category": category,
                "proficiency": proficiency,
            })

        return cleaned

    except Exception as e:
        print(f"[AI Tools] Skill extraction failed: {e}")
        return []


async def generate_skill_gap_analysis(
    profile_skills: list[str],
    target_role: str,
    job_requirements: str = "",
) -> dict:
    """
    Generate a skill gap analysis comparing profile skills to a target role.
    Returns:
    {
        "matching_skills": [...],
        "missing_skills": [...],
        "recommendations": [...],
        "readiness_score": 75
    }
    """
    skills_text = ", ".join(profile_skills) if profile_skills else "No skills listed"

    prompt = f"""
    You are an expert career advisor. Analyze the skill gap for this candidate.

    Target Role: {target_role}
    Candidate Current Skills: {skills_text}
    Job Requirements: {job_requirements[:1000] if job_requirements else "Use general industry knowledge for this role"}

    Return ONLY valid JSON, no explanation, no markdown:
    {{
        "matching_skills": ["skill1", "skill2"],
        "missing_skills": ["skill3", "skill4"],
        "recommendations": [
            "Take a course in X to improve Y",
            "Build a project using Z"
        ],
        "readiness_score": 75
    }}

    readiness_score must be a number between 0 and 100.
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
        print(f"[AI Tools] Skill gap analysis failed: {e}")
        return {
            "matching_skills": [],
            "missing_skills": [],
            "recommendations": ["Could not generate analysis. Please try again."],
            "readiness_score": 0,
        }

async def generate_cv_improvement_suggestions(
    cv_text: str,
    target_role: str,
    missing_skills: list[str],
) -> dict:
    """
    Analyze a CV and suggest specific improvements based on target role
    and identified skill gaps.
    Returns actionable CV improvement suggestions.
    """
    prompt = f"""
    You are an expert CV/resume coach. Analyze this CV and provide specific 
    improvement suggestions for the target role.

    Target Role: {target_role}
    Skills to develop: {", ".join(missing_skills[:10]) if missing_skills else "None identified"}

    CV Text:
    {cv_text[:3000]}

    Return ONLY valid JSON, no explanation, no markdown:
    {{
        "overall_cv_score": 72,
        "strengths": [
            "Strong project experience",
            "Clear education background"
        ],
        "weaknesses": [
            "Missing quantifiable achievements",
            "No mention of teamwork examples"
        ],
        "specific_improvements": [
            "Add metrics to your project descriptions e.g. improved performance by 40%",
            "Include a skills section highlighting your top 8-10 technical skills"
        ],
        "suggested_sections_to_add": [
            "Certifications",
            "Open Source Contributions"
        ],
        "keyword_suggestions": [
            "microservices",
            "REST API",
            "agile"
        ]
    }}

    overall_cv_score must be a number between 0 and 100.
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
        print(f"[AI Tools] CV improvement suggestions failed: {e}")
        return {
            "overall_cv_score": 0,
            "strengths": [],
            "weaknesses": [],
            "specific_improvements": ["Could not generate suggestions. Please try again."],
            "suggested_sections_to_add": [],
            "keyword_suggestions": [],
        }


async def generate_learning_roadmap(
    missing_skills: list[str],
    target_role: str,
    current_proficiency: str = "beginner",
) -> dict:
    """
    Generate a personalized learning roadmap to fill skill gaps.
    Returns structured learning plan with resources and timeline.
    """
    prompt = f"""
    You are an expert career coach and learning advisor.
    Create a personalized learning roadmap for this candidate.

    Target Role: {target_role}
    Skills to Learn: {", ".join(missing_skills[:10]) if missing_skills else "General skills for the role"}
    Current Level: {current_proficiency}

    Return ONLY valid JSON, no explanation, no markdown:
    {{
        "estimated_weeks_to_ready": 12,
        "phases": [
            {{
                "phase": 1,
                "title": "Foundation",
                "duration_weeks": 4,
                "skills_to_learn": ["skill1", "skill2"],
                "resources": [
                    {{
                        "title": "Resource name",
                        "type": "course/book/tutorial/youtube",
                        "url": "https://...",
                        "free": true
                    }}
                ],
                "milestone": "Build a simple project using skill1 and skill2"
            }}
        ],
        "recommended_projects": [
            {{
                "title": "Project name",
                "description": "Brief description",
                "skills_practiced": ["skill1", "skill2"],
                "difficulty": "beginner/intermediate/advanced"
            }}
        ],
        "daily_study_hours_recommended": 2
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
        print(f"[AI Tools] Learning roadmap generation failed: {e}")
        return {
            "estimated_weeks_to_ready": 0,
            "phases": [],
            "recommended_projects": [],
            "daily_study_hours_recommended": 2,
        }