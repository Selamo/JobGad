"""
Job Seeder — populates the database with realistic sample job listings
linked to demo companies and indexes them in Pinecone for AI matching.
Safe to run multiple times — skips existing data.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select

from app.core.config import settings
from app.models.job import JobListing
from app.models.company import Company, Department
from app.models.user import User
from app.tools.pinecone_tools import upsert_job_vector
from app.tools.scoring_tools import build_job_text

# ─── Demo Companies ───────────────────────────────────────────────────────────

DEMO_COMPANIES = [
    {
        "name": "TechCorp Africa",
        "description": "Leading technology company building innovative solutions for African businesses.",
        "industry": "Technology",
        "website": "https://techcorp-africa.com",
        "city": "Douala",
        "country": "Cameroon",
        "departments": ["Engineering", "Product", "Data Science"],
    },
    {
        "name": "Innovate Cameroon",
        "description": "Fintech startup revolutionizing digital payments across Central Africa.",
        "industry": "Fintech",
        "website": "https://innovate-cm.com",
        "city": "Yaoundé",
        "country": "Cameroon",
        "departments": ["Frontend", "Backend", "Mobile"],
    },
    {
        "name": "AI Solutions Africa",
        "description": "AI-powered solutions for businesses across Sub-Saharan Africa.",
        "industry": "Artificial Intelligence",
        "website": "https://ai-solutions-africa.com",
        "city": "Douala",
        "country": "Cameroon",
        "departments": ["Machine Learning", "Research", "Engineering"],
    },
    {
        "name": "CloudBase Africa",
        "description": "Cloud infrastructure and DevOps solutions for African enterprises.",
        "industry": "Cloud Computing",
        "website": "https://cloudbase-africa.com",
        "city": "Remote",
        "country": "Cameroon",
        "departments": ["DevOps", "Infrastructure", "Security"],
    },
    {
        "name": "SecureNet Africa",
        "description": "Cybersecurity firm protecting African businesses from digital threats.",
        "industry": "Cybersecurity",
        "website": "https://securenet-africa.com",
        "city": "Douala",
        "country": "Cameroon",
        "departments": ["Security", "Penetration Testing", "Compliance"],
    },
]

# ─── Sample Jobs ──────────────────────────────────────────────────────────────

SAMPLE_JOBS = [
    {
        "company_name": "TechCorp Africa",
        "department": "Engineering",
        "title": "Backend Python Developer",
        "location": "Douala, Cameroon",
        "description": """
            We are looking for a skilled Backend Python Developer to join our 
            growing engineering team. You will be responsible for building and 
            maintaining scalable APIs and microservices that power our web and 
            mobile applications used by thousands of users across Cameroon.
        """,
        "requirements": """
            - 2+ years of experience with Python
            - Strong knowledge of FastAPI or Django REST Framework
            - Experience with PostgreSQL or MySQL databases
            - Understanding of REST API design principles
            - Familiarity with Docker and containerization
            - Knowledge of Git version control
            - Experience with async programming is a plus
            - Good communication skills in English or French
        """,
        "salary_range": "500,000 - 800,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 30,
    },
    {
        "company_name": "Innovate Cameroon",
        "department": "Frontend",
        "title": "Frontend React Developer",
        "location": "Yaoundé, Cameroon",
        "description": """
            Join our dynamic team as a Frontend Developer. You will work closely 
            with our design team to build beautiful, responsive user interfaces 
            for our fintech products used across Central Africa.
        """,
        "requirements": """
            - Proficiency in React.js and JavaScript (ES6+)
            - Experience with TypeScript is a plus
            - Strong understanding of HTML5 and CSS3
            - Experience with state management (Redux or Zustand)
            - Familiarity with REST APIs and GraphQL
            - Experience with Tailwind CSS or styled-components
            - Knowledge of responsive design principles
            - Portfolio of previous work required
        """,
        "salary_range": "400,000 - 600,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 21,
    },
    {
        "company_name": "TechCorp Africa",
        "department": "Engineering",
        "title": "Full Stack Developer",
        "location": "Douala, Cameroon",
        "description": """
            We need a versatile Full Stack Developer who can work on both frontend 
            and backend systems. You will be building features end-to-end for our 
            e-commerce platform serving thousands of users daily across Cameroon 
            and neighboring countries.
        """,
        "requirements": """
            - Experience with React.js or Vue.js on the frontend
            - Backend experience with Node.js, Python, or PHP
            - Database experience with PostgreSQL or MongoDB
            - Understanding of CI/CD pipelines
            - Experience with cloud services (AWS, GCP, or Azure)
            - Strong problem-solving skills
            - Good communication skills
            - Ability to work in an agile team
        """,
        "salary_range": "600,000 - 900,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 25,
    },
    {
        "company_name": "AI Solutions Africa",
        "department": "Machine Learning",
        "title": "Machine Learning Engineer",
        "location": "Remote",
        "description": """
            We are building AI-powered solutions for African businesses and need a 
            talented ML Engineer. You will design, train, and deploy machine learning 
            models that solve real problems for our clients across the continent.
        """,
        "requirements": """
            - Strong Python programming skills
            - Experience with TensorFlow or PyTorch
            - Knowledge of scikit-learn and pandas
            - Understanding of NLP and computer vision concepts
            - Experience with model deployment using FastAPI or Flask
            - Familiarity with cloud ML platforms (AWS SageMaker, GCP AI)
            - Strong mathematics background (linear algebra, statistics)
            - Experience with data preprocessing and feature engineering
        """,
        "salary_range": "800,000 - 1,200,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 45,
    },
    {
        "company_name": "Innovate Cameroon",
        "department": "Mobile",
        "title": "Mobile Developer (React Native)",
        "location": "Yaoundé, Cameroon",
        "description": """
            Build cross-platform mobile applications used by over 50,000 users 
            across Cameroon and neighboring countries. You will work on our 
            mobile banking and payments application.
        """,
        "requirements": """
            - 2+ years of React Native development experience
            - Strong JavaScript and TypeScript skills
            - Experience with mobile UI/UX design patterns
            - Knowledge of iOS and Android deployment process
            - Experience with REST APIs and WebSocket integration
            - Familiarity with state management (Redux)
            - Experience with push notifications and offline storage
            - Understanding of mobile security best practices
        """,
        "salary_range": "500,000 - 750,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 20,
    },
    {
        "company_name": "CloudBase Africa",
        "department": "DevOps",
        "title": "DevOps Engineer",
        "location": "Remote",
        "description": """
            We are looking for a DevOps Engineer to help us scale our infrastructure. 
            You will manage our cloud infrastructure, CI/CD pipelines, and ensure 
            high availability of our services for clients across Africa.
        """,
        "requirements": """
            - Strong experience with Docker and Kubernetes
            - Experience with AWS, GCP, or Azure cloud platforms
            - Knowledge of CI/CD tools (GitHub Actions, Jenkins, GitLab CI)
            - Experience with Infrastructure as Code (Terraform, Ansible)
            - Strong Linux system administration skills
            - Experience with monitoring tools (Prometheus, Grafana)
            - Knowledge of networking and security best practices
            - Scripting skills in Bash or Python
        """,
        "salary_range": "700,000 - 1,000,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 35,
    },
    {
        "company_name": "TechCorp Africa",
        "department": "Data Science",
        "title": "Data Analyst",
        "location": "Douala, Cameroon",
        "description": """
            Help us turn data into actionable insights. You will analyze large datasets, 
            build dashboards, and help business teams make data-driven decisions that 
            drive growth across our African markets.
        """,
        "requirements": """
            - Strong SQL skills for data querying
            - Experience with Python (pandas, numpy, matplotlib, seaborn)
            - Experience with data visualization tools (Tableau, Power BI)
            - Understanding of statistical analysis and hypothesis testing
            - Experience with Excel and Google Sheets for reporting
            - Good communication skills to present findings to stakeholders
            - Knowledge of database systems (PostgreSQL, MySQL)
            - Attention to detail and analytical mindset
        """,
        "salary_range": "350,000 - 550,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 28,
    },
    {
        "company_name": "SecureNet Africa",
        "department": "Penetration Testing",
        "title": "Cybersecurity Analyst",
        "location": "Douala, Cameroon",
        "description": """
            Protect our clients systems from cyber threats. You will conduct 
            vulnerability assessments, penetration testing, and help organizations 
            improve their security posture against growing cyber threats in Cameroon.
        """,
        "requirements": """
            - Knowledge of network security protocols and concepts
            - Experience with vulnerability scanning tools (OWASP ZAP, Burp Suite)
            - Understanding of OWASP Top 10 vulnerabilities
            - Experience with penetration testing methodologies
            - Knowledge of firewalls and intrusion detection systems
            - Familiarity with security frameworks (ISO 27001, NIST)
            - Strong analytical and problem-solving skills
            - Security certifications (CEH, CompTIA Security+) are a plus
        """,
        "salary_range": "500,000 - 800,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 40,
    },
    {
        "company_name": "TechCorp Africa",
        "department": "Engineering",
        "title": "Software Engineering Intern",
        "location": "Douala, Cameroon",
        "description": """
            Great opportunity for final year students or fresh graduates to gain 
            real-world software development experience. You will work alongside 
            senior developers on real products used by thousands of users.
        """,
        "requirements": """
            - Currently studying or recently graduated in Computer Science or related field
            - Basic knowledge of at least one programming language (Python, JavaScript, Java)
            - Understanding of basic web development concepts (HTML, CSS, JavaScript)
            - Eagerness to learn and grow professionally
            - Good teamwork and communication skills
            - Knowledge of Git version control is a plus
            - Ability to work full-time for at least 3 months
        """,
        "salary_range": "80,000 - 150,000 FCFA/month",
        "employment_type": "internship",
        "deadline_days": 15,
    },
    {
        "company_name": "AI Solutions Africa",
        "department": "Research",
        "title": "AI Research Scientist",
        "location": "Remote",
        "description": """
            Join our research team to push the boundaries of AI applications 
            in Africa. You will conduct cutting-edge research in machine learning, 
            natural language processing, and computer vision focused on African 
            languages and use cases.
        """,
        "requirements": """
            - PhD or MSc in Computer Science, Machine Learning, or related field
            - Strong publication record or research experience
            - Deep knowledge of neural networks and deep learning
            - Experience with NLP and African language processing is a huge plus
            - Proficiency in Python and ML frameworks (PyTorch, TensorFlow)
            - Ability to write and publish technical papers
            - Strong mathematical background
            - Collaborative mindset and good communication skills
        """,
        "salary_range": "1,000,000 - 1,500,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 60,
    },
    {
        "company_name": "Innovate Cameroon",
        "department": "Backend",
        "title": "Backend Node.js Developer",
        "location": "Yaoundé, Cameroon",
        "description": """
            Build the backend systems powering our digital banking platform. 
            You will work on APIs, payment integrations, and real-time features 
            for our rapidly growing fintech product serving users across Cameroon.
        """,
        "requirements": """
            - Strong experience with Node.js and Express.js
            - Knowledge of TypeScript
            - Experience with PostgreSQL or MongoDB databases
            - Understanding of payment APIs and integrations (MTN MoMo, Orange Money)
            - Experience with WebSockets for real-time features
            - Knowledge of JWT authentication and security best practices
            - Experience with message queues (RabbitMQ, Redis)
            - Familiarity with microservices architecture
        """,
        "salary_range": "500,000 - 750,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 22,
    },
    {
        "company_name": "CloudBase Africa",
        "department": "Security",
        "title": "Cloud Security Engineer",
        "location": "Remote",
        "description": """
            Ensure the security of our cloud infrastructure and client deployments. 
            You will implement security best practices, conduct security reviews, 
            and respond to security incidents across our cloud platforms.
        """,
        "requirements": """
            - Experience with cloud security (AWS Security, GCP Security)
            - Knowledge of IAM, VPC, and cloud networking security
            - Experience with security scanning and monitoring tools
            - Understanding of compliance frameworks (SOC2, ISO 27001)
            - Scripting skills in Python or Bash for automation
            - Experience with SIEM tools
            - Strong incident response experience
            - Cloud security certifications are a plus
        """,
        "salary_range": "800,000 - 1,100,000 FCFA/month",
        "employment_type": "full-time",
        "deadline_days": 30,
    },
]


# ─── Seeder Function ──────────────────────────────────────────────────────────

async def seed_jobs():
    """
    Seeds the database with demo companies and job listings.
    Indexes all jobs in Pinecone for AI matching.
    Safe to run multiple times.
    """
    print("🌱 Starting JobGad Job Seeder...")
    print("=" * 50)

    engine = create_async_engine(settings.DATABASE_URI, echo=False)
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSession() as db:

        # ── Step 1: Create Demo Companies ─────────────────────────────────────
        print("\n📦 Setting up demo companies...")

        company_map = {}
        department_map = {}

        for company_data in DEMO_COMPANIES:
            # Check if company already exists
            existing = await db.execute(
                select(Company).where(
                    Company.name == company_data["name"]
                )
            )
            company = existing.scalar_one_or_none()

            if company:
                print(f"   ⏭️  Company exists: {company_data['name']}")
                company_map[company_data["name"]] = company
            else:
                company = Company(
                    id=uuid.uuid4(),
                    name=company_data["name"],
                    description=company_data["description"],
                    industry=company_data["industry"],
                    website=company_data["website"],
                    city=company_data["city"],
                    country=company_data["country"],
                    status="approved",
                    is_verified=True,
                    approved_at=datetime.now(timezone.utc),
                )
                db.add(company)
                await db.flush()
                company_map[company_data["name"]] = company
                print(f"   ✅ Created company: {company_data['name']}")

            # Create departments for this company
            for dept_name in company_data["departments"]:
                existing_dept = await db.execute(
                    select(Department).where(
                        Department.company_id == company.id,
                        Department.name == dept_name,
                    )
                )
                dept = existing_dept.scalar_one_or_none()

                if not dept:
                    dept = Department(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        name=dept_name,
                    )
                    db.add(dept)
                    await db.flush()

                dept_key = f"{company_data['name']}_{dept_name}"
                department_map[dept_key] = dept

        await db.commit()

        # ── Step 2: Seed Job Listings ──────────────────────────────────────────
        print("\n💼 Seeding job listings...")

        existing_titles = set()
        existing_result = await db.execute(select(JobListing.title))
        for row in existing_result.fetchall():
            existing_titles.add(row[0])

        seeded = 0
        skipped = 0
        pinecone_success = 0
        pinecone_failed = 0

        for job_data in SAMPLE_JOBS:
            if job_data["title"] in existing_titles:
                print(f"   ⏭️  Skipping: {job_data['title']}")
                skipped += 1
                continue

            # Get company
            company = company_map.get(job_data["company_name"])
            if not company:
                print(f"   ❌ Company not found: {job_data['company_name']}")
                continue

            # Get department
            dept_key = f"{job_data['company_name']}_{job_data['department']}"
            department = department_map.get(dept_key)

            # Calculate deadline
            deadline = datetime.now(timezone.utc) + timedelta(
                days=job_data.get("deadline_days", 30)
            )

            # Create job listing
            job = JobListing(
                id=uuid.uuid4(),
                title=job_data["title"],
                location=job_data["location"],
                description=job_data["description"].strip(),
                requirements=job_data["requirements"].strip(),
                salary_range=job_data["salary_range"],
                employment_type=job_data["employment_type"],
                company_id=company.id,
                department_id=department.id if department else None,
                source="seeded",
                status="published",
                is_active=True,
                application_deadline=deadline,
                posted_at=datetime.now(timezone.utc),
            )
            db.add(job)
            await db.flush()

            # Index in Pinecone
            try:
                job_text = build_job_text(job)
                vector_id = await upsert_job_vector(
                    job_id=str(job.id),
                    text=job_text,
                    metadata={
                        "title": job.title,
                        "company": company.name,
                        "location": job.location or "",
                        "employment_type": job.employment_type or "",
                        "is_active": True,
                    },
                )
                job.pinecone_vector_id = vector_id
                pinecone_success += 1
                print(f"   ✅ Seeded + indexed: {job.title} @ {company.name}")
            except Exception as e:
                pinecone_failed += 1
                print(
                    f"   ⚠️  Seeded (Pinecone failed): "
                    f"{job.title} — {e}"
                )

            seeded += 1
            existing_titles.add(job_data["title"])

        await db.commit()

    await engine.dispose()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("✅ SEEDING COMPLETE!")
    print(f"   Companies created:    {len(company_map)}")
    print(f"   Jobs seeded:          {seeded}")
    print(f"   Jobs skipped:         {skipped}")
    print(f"   Pinecone indexed:     {pinecone_success}")
    print(f"   Pinecone failed:      {pinecone_failed}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed_jobs())