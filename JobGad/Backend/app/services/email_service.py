"""
Email service — sends transactional emails using FastAPI-Mail.
All email functions are non-fatal: if email fails, the main operation still succeeds.
"""
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from app.core.config import settings

APP_URL = "https://job-gad.vercel.app"

# ─── Mail Configuration ───────────────────────────────────────────────────────

try:
    mail_config = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    fm = FastMail(mail_config)
    print("[Email] Mail service initialized successfully")
except Exception as e:
    print(f"[Email] Mail config failed — email sending disabled: {e}")
    fm = None


# ─── Base Email Sender ────────────────────────────────────────────────────────

async def send_email(
    recipients: list[str],
    subject: str,
    body: str,
) -> bool:
    if not fm:
        print(f"[Email] Mail not configured — skipping '{subject}' to {recipients}")
        return False
    try:
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=body,
            subtype=MessageType.html,
        )
        await fm.send_message(message)
        print(f"[Email] Sent '{subject}' to {recipients}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send '{subject}': {e}")
        return False


# ─── Email Templates ──────────────────────────────────────────────────────────

def _base_template(title: str, content: str) -> str:
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff;
                    border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="background-color: #2563EB; padding: 24px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px;">JobGad</h1>
                <p style="color: #bfdbfe; margin: 4px 0 0 0; font-size: 14px;">
                    AI-Powered Career Acceleration
                </p>
            </div>
            <div style="padding: 32px;">
                <h2 style="color: #1e293b; margin-top: 0;">{title}</h2>
                {content}
            </div>
            <div style="background-color: #f8fafc; padding: 16px; text-align: center;
                        border-top: 1px solid #e2e8f0;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    © 2025 JobGad Platform. All rights reserved.
                </p>
                <p style="color: #94a3b8; font-size: 12px; margin: 4px 0 0 0;">
                    University of Bamenda, Cameroon
                </p>
            </div>
        </div>
    </body>
    </html>
    """


# ─── Specific Email Functions ─────────────────────────────────────────────────

async def send_welcome_email(email: str, full_name: str) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Welcome to <strong>JobGad</strong>! Your account has been created successfully.
        </p>
        <p style="color: #374151;">Here is what you can do next:</p>
        <ul style="color: #374151;">
            <li>Complete your profile</li>
            <li>Upload your CV for AI skill extraction</li>
            <li>Run job matching to find the best opportunities</li>
            <li>Practice with our AI interview coach</li>
        </ul>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/profile"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                Complete Your Profile
            </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
            If you did not create this account, please ignore this email.
        </p>
    """
    await send_email(
        recipients=[email],
        subject="Welcome to JobGad! 🎉",
        body=_base_template("Welcome to JobGad!", content),
    )


async def send_company_approved_email(email: str, full_name: str, company_name: str) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Great news! Your company <strong>{company_name}</strong> has been
            <span style="color: #16a34a; font-weight: bold;">approved</span> by our admin team.
        </p>
        <p style="color: #374151;">You can now:</p>
        <ul style="color: #374151;">
            <li>Post job listings</li>
            <li>Review applications from graduates</li>
        </ul>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/hr"
               style="background-color: #16a34a; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                Go to HR Dashboard
            </a>
        </div>
    """
    await send_email(
        recipients=[email],
        subject=f"✅ Company Approved — {company_name}",
        body=_base_template("Company Approved!", content),
    )


async def send_company_rejected_email(
    email: str, full_name: str, company_name: str, reason: str,
) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Unfortunately, your company registration for <strong>{company_name}</strong>
            has been <span style="color: #dc2626; font-weight: bold;">rejected</span>.
        </p>
        <div style="background-color: #fef2f2; border-left: 4px solid #dc2626;
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;"><strong>Reason:</strong> {reason}</p>
        </div>
        <p style="color: #374151;">
            You can address these issues and re-submit your company registration.
        </p>
    """
    await send_email(
        recipients=[email],
        subject=f"❌ Company Registration Rejected — {company_name}",
        body=_base_template("Company Registration Rejected", content),
    )


async def send_hr_approved_email(email: str, full_name: str, company_name: str) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Your HR account for <strong>{company_name}</strong> has been
            <span style="color: #16a34a; font-weight: bold;">approved</span>!
        </p>
        <p style="color: #374151;">You can now:</p>
        <ul style="color: #374151;">
            <li>Post job listings for your company</li>
            <li>Review and manage applications</li>
            <li>Shortlist and contact candidates</li>
        </ul>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/hr"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                Post Your First Job
            </a>
        </div>
    """
    await send_email(
        recipients=[email],
        subject=f"✅ HR Account Approved — {company_name}",
        body=_base_template("HR Account Approved!", content),
    )


async def send_hr_rejected_email(
    email: str, full_name: str, company_name: str, reason: str,
) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Your HR account request for <strong>{company_name}</strong> has been
            <span style="color: #dc2626; font-weight: bold;">rejected</span>.
        </p>
        <div style="background-color: #fef2f2; border-left: 4px solid #dc2626;
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;"><strong>Reason:</strong> {reason}</p>
        </div>
    """
    await send_email(
        recipients=[email],
        subject=f"❌ HR Account Rejected — {company_name}",
        body=_base_template("HR Account Rejected", content),
    )


async def send_application_received_email(
    hr_email: str, hr_name: str, applicant_name: str,
    job_title: str, company_name: str, application_id: str,
) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{hr_name}</strong>,</p>
        <p style="color: #374151;">
            A new application has been received for <strong>{job_title}</strong>
            at <strong>{company_name}</strong>.
        </p>
        <div style="background-color: #eff6ff; border-left: 4px solid #2563EB;
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;">
                <strong>Applicant:</strong> {applicant_name}<br/>
                <strong>Position:</strong> {job_title}<br/>
                <strong>Status:</strong> Pending Review
            </p>
        </div>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/hr"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                Review Application
            </a>
        </div>
    """
    await send_email(
        recipients=[hr_email],
        subject=f"📩 New Application — {job_title} | {applicant_name}",
        body=_base_template("New Job Application Received", content),
    )


async def send_application_status_email(
    email: str, full_name: str, job_title: str,
    company_name: str, new_status: str, hr_notes: str = None,
) -> None:
    status_colors = {
        "reviewed": "#f59e0b", "shortlisted": "#16a34a",
        "rejected": "#dc2626", "accepted": "#16a34a",
    }
    status_messages = {
        "reviewed":    "Your application is currently being reviewed by the HR team.",
        "shortlisted": "Congratulations! You have been shortlisted for this position.",
        "rejected":    "Unfortunately, your application was not successful this time.",
        "accepted":    "Congratulations! You have been accepted for this position!",
    }
    color = status_colors.get(new_status, "#6b7280")
    message = status_messages.get(new_status, "Your application status has been updated.")
    notes_section = ""
    if hr_notes:
        notes_section = f"""
        <div style="background-color: #f8fafc; border-left: 4px solid #94a3b8;
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;">
                <strong>Message from HR:</strong> {hr_notes}
            </p>
        </div>
        """
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Your application for <strong>{job_title}</strong> at
            <strong>{company_name}</strong> has been updated.
        </p>
        <div style="background-color: #f0fdf4; border-left: 4px solid {color};
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;">
                <strong>New Status:</strong>
                <span style="color: {color}; font-weight: bold; text-transform: uppercase;">
                    {new_status}
                </span><br/>
                {message}
            </p>
        </div>
        {notes_section}
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/applications"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                View My Applications
            </a>
        </div>
    """
    await send_email(
        recipients=[email],
        subject=f"📋 Application Update — {job_title} at {company_name}",
        body=_base_template("Application Status Update", content),
    )


async def send_cv_ready_email(
    email: str, full_name: str, job_title: str,
    company_name: str, download_url: str,
) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Your AI-generated CV for <strong>{job_title}</strong> at
            <strong>{company_name}</strong> is ready for download!
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/cv"
               style="background-color: #16a34a; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                Download Your CV
            </a>
        </div>
        <p style="color: #6b7280; font-size: 14px;">
            Review your CV before submitting your application.
        </p>
    """
    await send_email(
        recipients=[email],
        subject=f"📄 Your AI CV is Ready — {job_title}",
        body=_base_template("Your AI-Generated CV is Ready!", content),
    )


async def send_interview_completed_email(
    email: str, full_name: str, job_title: str,
    iri_score: float, feedback_summary: str,
) -> None:
    score_color = "#16a34a" if iri_score >= 70 else "#f59e0b" if iri_score >= 50 else "#dc2626"
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            Your AI interview coaching session for <strong>{job_title}</strong>
            has been completed.
        </p>
        <div style="text-align: center; margin: 24px 0;">
            <div style="display: inline-block; background-color: {score_color};
                        color: white; border-radius: 50%; width: 80px; height: 80px;
                        line-height: 80px; font-size: 28px; font-weight: bold;">
                {int(iri_score)}
            </div>
            <p style="color: #374151; margin: 8px 0 0 0;">Interview Readiness Index (IRI)</p>
        </div>
        <div style="background-color: #f8fafc; border-left: 4px solid {score_color};
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;">
                <strong>Feedback Summary:</strong><br/>{feedback_summary}
            </p>
        </div>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/coaching"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                View Full Report
            </a>
        </div>
    """
    await send_email(
        recipients=[email],
        subject=f"🎯 Interview Results — IRI Score: {int(iri_score)}/100",
        body=_base_template("Your Interview Results Are Ready!", content),
    )


async def send_job_match_email(
    email: str, full_name: str, match_count: int,
    top_job_title: str, top_company: str, top_score: float,
) -> None:
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            We found <strong>{match_count} new job matches</strong> for your profile!
        </p>
        <div style="background-color: #eff6ff; border-left: 4px solid #2563EB;
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;">
                <strong>Top Match:</strong> {top_job_title} at {top_company}<br/>
                <strong>Match Score:</strong> {int(top_score * 100)}%
            </p>
        </div>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/jobs"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                View All Matches
            </a>
        </div>
    """
    await send_email(
        recipients=[email],
        subject=f"🎯 {match_count} New Job Matches Found!",
        body=_base_template("New Job Matches Found!", content),
    )


async def send_job_alert_email(
    email: str, full_name: str, job_title: str,
    company_name: str, match_score: int,
    job_location: str, employment_type: str,
) -> None:
    score_color = "#16a34a" if match_score >= 80 else "#2563EB" if match_score >= 60 else "#f59e0b"
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">A new job has been posted that matches your profile.</p>
        <div style="background-color: #eff6ff; border-left: 4px solid #2563EB;
                    padding: 16px; margin: 16px 0; border-radius: 4px;">
            <p style="color: #374151; margin: 0;">
                <strong>Position:</strong> {job_title}<br/>
                <strong>Company:</strong> {company_name}<br/>
                <strong>Location:</strong> {job_location}<br/>
                <strong>Type:</strong> {employment_type.replace('-', ' ').title()}<br/>
                <strong>Match Score:</strong>
                <span style="color: {score_color}; font-weight: bold;">{match_score}%</span>
            </p>
        </div>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{APP_URL}/jobs"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                View Job &amp; Apply
            </a>
        </div>
        <p style="color: #6b7280; font-size: 12px;">
            You are receiving this because your profile matches this job.
        </p>
    """
    await send_email(
        recipients=[email],
        subject=f"🎯 New Job Match — {job_title} at {company_name} ({match_score}% match)",
        body=_base_template("New Job Match Alert!", content),
    )


async def send_password_reset_email(
    email: str, full_name: str, reset_token: str,
) -> None:
    reset_url = f"{APP_URL}/reset-password?token={reset_token}"
    content = f"""
        <p style="color: #374151;">Hi <strong>{full_name}</strong>,</p>
        <p style="color: #374151;">
            We received a request to reset your JobGad password.
            Click the button below to set a new password.
        </p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{reset_url}"
               style="background-color: #2563EB; color: white; padding: 12px 24px;
                      border-radius: 6px; text-decoration: none; font-weight: bold;">
                Reset My Password
            </a>
        </div>
        <p style="color: #6b7280; font-size: 13px;">
            This link expires in <strong>30 minutes</strong>.
            If you did not request this, ignore this email.
        </p>
        <p style="color: #6b7280; font-size: 12px; margin-top: 16px;">
            Or copy this link: {reset_url}
        </p>
    """
    await send_email(
        recipients=[email],
        subject="🔐 Reset your JobGad password",
        body=_base_template("Password Reset Request", content),
    )