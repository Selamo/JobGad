"""
Social tools — fetch and analyze data from GitHub, GitLab, and portfolio websites.
"""
import httpx
import re
from bs4 import BeautifulSoup


# ─── GitHub ───────────────────────────────────────────────────────────────────

def extract_github_username(url: str) -> str | None:
    """Extract username from a GitHub URL."""
    url = url.strip().rstrip("/")
    patterns = [
        r"github\.com/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            username = match.group(1)
            # Ignore paths like github.com/username/repo
            return username
    return None


def extract_gitlab_username(url: str) -> str | None:
    """Extract username from a GitLab URL."""
    url = url.strip().rstrip("/")
    match = re.search(r"gitlab\.com/([a-zA-Z0-9_.-]+)", url)
    if match:
        return match.group(1)
    return None


async def fetch_github_skills(github_url: str) -> list[dict]:
    """
    Fetch public repos from GitHub and extract languages as skills.
    Returns list of skill dicts.
    """
    username = extract_github_username(github_url)
    if not username:
        print(f"[GitHub] Could not extract username from: {github_url}")
        return []

    skills = {}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch public repos
            repos_response = await client.get(
                f"https://api.github.com/users/{username}/repos",
                params={"per_page": 30, "sort": "updated"},
                headers={"Accept": "application/vnd.github.v3+json"},
            )

            if repos_response.status_code != 200:
                print(f"[GitHub] Failed to fetch repos for {username}: {repos_response.status_code}")
                return []

            repos = repos_response.json()

            # Collect language stats across all repos
            language_counts = {}
            topics_set = set()

            for repo in repos:
                if repo.get("fork"):
                    continue  # Skip forked repos

                # Count primary language
                lang = repo.get("language")
                if lang:
                    language_counts[lang] = language_counts.get(lang, 0) + 1

                # Collect topics/tags
                for topic in repo.get("topics", []):
                    topics_set.add(topic)

            # Fetch languages detail for top 5 repos
            for repo in repos[:5]:
                if repo.get("fork"):
                    continue
                lang_response = await client.get(
                    repo["languages_url"],
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if lang_response.status_code == 200:
                    for lang in lang_response.json():
                        language_counts[lang] = language_counts.get(lang, 0) + 1

            # Convert languages to skills
            total_repos = len([r for r in repos if not r.get("fork")])

            for lang, count in language_counts.items():
                ratio = count / max(total_repos, 1)
                if ratio >= 0.5:
                    proficiency = "advanced"
                elif ratio >= 0.25:
                    proficiency = "intermediate"
                else:
                    proficiency = "beginner"

                skills[lang.lower()] = {
                    "name": lang,
                    "category": "technical",
                    "proficiency": proficiency,
                }

            # Convert topics to tool/domain skills
            tool_keywords = {
                "docker", "kubernetes", "react", "vue", "angular",
                "fastapi", "django", "flask", "nodejs", "express",
                "tensorflow", "pytorch", "scikit-learn", "pandas",
                "postgresql", "mongodb", "redis", "graphql",
                "aws", "gcp", "azure", "firebase", "supabase",
            }

            for topic in topics_set:
                topic_lower = topic.lower()
                if topic_lower in tool_keywords and topic_lower not in skills:
                    skills[topic_lower] = {
                        "name": topic.title(),
                        "category": "tool",
                        "proficiency": "intermediate",
                    }

        print(f"[GitHub] Extracted {len(skills)} skills for {username}")
        return list(skills.values())

    except Exception as e:
        print(f"[GitHub] Error fetching skills: {e}")
        return []


async def fetch_gitlab_skills(gitlab_url: str) -> list[dict]:
    """
    Fetch public repos from GitLab and extract languages as skills.
    """
    username = extract_gitlab_username(gitlab_url)
    if not username:
        print(f"[GitLab] Could not extract username from: {gitlab_url}")
        return []

    skills = {}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"https://gitlab.com/api/v4/users/{username}/projects",
                params={"per_page": 20, "order_by": "last_activity_at"},
            )

            if response.status_code != 200:
                print(f"[GitLab] Failed to fetch projects: {response.status_code}")
                return []

            projects = response.json()
            language_counts = {}

            for project in projects:
                # Fetch languages for each project
                lang_response = await client.get(
                    f"https://gitlab.com/api/v4/projects/{project['id']}/languages"
                )
                if lang_response.status_code == 200:
                    for lang, percentage in lang_response.json().items():
                        language_counts[lang] = language_counts.get(lang, 0) + percentage

            # Convert to skills
            total = sum(language_counts.values()) or 1
            for lang, count in language_counts.items():
                ratio = count / total
                if ratio >= 0.4:
                    proficiency = "advanced"
                elif ratio >= 0.2:
                    proficiency = "intermediate"
                else:
                    proficiency = "beginner"

                skills[lang.lower()] = {
                    "name": lang,
                    "category": "technical",
                    "proficiency": proficiency,
                }

        print(f"[GitLab] Extracted {len(skills)} skills for {username}")
        return list(skills.values())

    except Exception as e:
        print(f"[GitLab] Error fetching skills: {e}")
        return []


# ─── Portfolio Website ────────────────────────────────────────────────────────

async def fetch_portfolio_skills(portfolio_url: str) -> list[dict]:
    """
    Scrape a portfolio website, extract visible text,
    and use Gemini to identify skills mentioned.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobGad-Bot/1.0)"},
        ) as client:
            response = await client.get(portfolio_url)

            if response.status_code != 200:
                print(f"[Portfolio] Failed to fetch {portfolio_url}: {response.status_code}")
                return []

            # Parse HTML and extract clean text
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style tags
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)

            # Limit text length
            text = text[:3000]

            if not text.strip():
                return []

            # Use Gemini to extract skills from portfolio text
            from app.tools.ai_tools import extract_skills_from_text
            skills = await extract_skills_from_text(text)

            print(f"[Portfolio] Extracted {len(skills)} skills from {portfolio_url}")
            return skills

    except Exception as e:
        print(f"[Portfolio] Error scraping {portfolio_url}: {e}")
        return []


# ─── Platform Detector ────────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    """Detect which platform a URL belongs to."""
    url = url.lower()
    if "github.com" in url:
        return "github"
    elif "gitlab.com" in url:
        return "gitlab"
    elif "linkedin.com" in url:
        return "linkedin"
    else:
        return "portfolio"


async def fetch_skills_from_url(url: str) -> tuple[str, list[dict]]:
    """
    Auto-detect platform from URL and fetch skills.
    Returns (platform_name, skills_list)
    """
    platform = detect_platform(url)

    if platform == "github":
        skills = await fetch_github_skills(url)
    elif platform == "gitlab":
        skills = await fetch_gitlab_skills(url)
    elif platform == "linkedin":
        # LinkedIn blocks scraping — return empty with a note
        print("[LinkedIn] Automated scraping not supported")
        skills = []
    else:
        skills = await fetch_portfolio_skills(url)

    return platform, skills