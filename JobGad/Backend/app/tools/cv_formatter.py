"""
CV Formatter — converts structured CV data into PDF or DOCX files.
"""
import io
from datetime import datetime


# ─── DOCX Formatter ───────────────────────────────────────────────────────────

def generate_cv_docx(cv_data: dict) -> bytes:
    """
    Generate a professional DOCX CV from structured CV data.
    Returns bytes of the DOCX file.
    """
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Set margins
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    personal = cv_data.get("personal_info", {})
    full_name = personal.get("full_name", "")

    # ── Name Header ──────────────────────────────────────────────────────────
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(full_name.upper())
    name_run.bold = True
    name_run.font.size = Pt(20)
    name_run.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)

    # ── Contact Info ─────────────────────────────────────────────────────────
    contact_parts = []
    if personal.get("email"):
        contact_parts.append(personal["email"])
    if personal.get("linkedin"):
        contact_parts.append(personal["linkedin"])
    if personal.get("github"):
        contact_parts.append(personal["github"])
    if personal.get("location"):
        contact_parts.append(personal["location"])

    if contact_parts:
        contact_para = doc.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_run = contact_para.add_run(" | ".join(contact_parts))
        contact_run.font.size = Pt(9)
        contact_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    def add_section_header(title: str):
        """Add a styled section header."""
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(12)
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)
        # Add a line under the header
        border_para = doc.add_paragraph()
        border_para.paragraph_format.space_before = Pt(0)
        border_para.paragraph_format.space_after = Pt(6)
        border_run = border_para.add_run("─" * 80)
        border_run.font.size = Pt(6)
        border_run.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

    # ── Professional Summary ─────────────────────────────────────────────────
    summary = cv_data.get("professional_summary", "")
    if summary:
        add_section_header("Professional Summary")
        summary_para = doc.add_paragraph(summary)
        summary_para.paragraph_format.space_after = Pt(4)
        for run in summary_para.runs:
            run.font.size = Pt(10)

    # ── Skills ───────────────────────────────────────────────────────────────
    skills = cv_data.get("relevant_skills", {})
    if skills:
        add_section_header("Skills")
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                if skill_list:
                    skills_para = doc.add_paragraph()
                    skills_para.paragraph_format.space_after = Pt(2)
                    label_run = skills_para.add_run(f"{category.title()}: ")
                    label_run.bold = True
                    label_run.font.size = Pt(10)
                    skills_list = skill_list if isinstance(skill_list, list) else [skill_list]
                    value_run = skills_para.add_run(", ".join(skills_list))
                    value_run.font.size = Pt(10)
        elif isinstance(skills, list):
            skills_para = doc.add_paragraph(", ".join(skills))
            for run in skills_para.runs:
                run.font.size = Pt(10)

    # ── Education ────────────────────────────────────────────────────────────
    education = cv_data.get("education", [])
    if education:
        add_section_header("Education")
        for edu in education:
            edu_para = doc.add_paragraph()
            edu_para.paragraph_format.space_after = Pt(2)
            degree_run = edu_para.add_run(
                f"{edu.get('degree', '')} in {edu.get('field', '')}"
            )
            degree_run.bold = True
            degree_run.font.size = Pt(10)

            inst_para = doc.add_paragraph()
            inst_para.paragraph_format.space_after = Pt(2)
            inst_run = inst_para.add_run(
                f"{edu.get('institution', '')} — {edu.get('year', '')}"
            )
            inst_run.font.size = Pt(10)
            inst_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

            if edu.get("achievements"):
                ach_para = doc.add_paragraph(f"  {edu['achievements']}")
                for run in ach_para.runs:
                    run.font.size = Pt(10)

    # ── Experience ───────────────────────────────────────────────────────────
    experience = cv_data.get("experience", [])
    if experience:
        add_section_header("Experience")
        for exp in experience:
            title_para = doc.add_paragraph()
            title_para.paragraph_format.space_after = Pt(1)
            title_run = title_para.add_run(
                f"{exp.get('title', '')} — {exp.get('company', '')}"
            )
            title_run.bold = True
            title_run.font.size = Pt(10)

            if exp.get("duration"):
                dur_para = doc.add_paragraph(exp["duration"])
                dur_para.paragraph_format.space_after = Pt(2)
                for run in dur_para.runs:
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

            for resp in exp.get("responsibilities", []):
                resp_para = doc.add_paragraph(
                    style="List Bullet"
                )
                resp_para.paragraph_format.space_after = Pt(1)
                resp_run = resp_para.add_run(resp)
                resp_run.font.size = Pt(10)

            for ach in exp.get("achievements", []):
                ach_para = doc.add_paragraph(style="List Bullet")
                ach_para.paragraph_format.space_after = Pt(1)
                ach_run = ach_para.add_run(f"✓ {ach}")
                ach_run.font.size = Pt(10)
                ach_run.font.color.rgb = RGBColor(0x16, 0xA3, 0x4A)

    # ── Projects ─────────────────────────────────────────────────────────────
    projects = cv_data.get("projects", [])
    if projects:
        add_section_header("Projects")
        for proj in projects:
            proj_para = doc.add_paragraph()
            proj_para.paragraph_format.space_after = Pt(1)
            proj_run = proj_para.add_run(proj.get("name", ""))
            proj_run.bold = True
            proj_run.font.size = Pt(10)

            if proj.get("description"):
                desc_para = doc.add_paragraph(proj["description"])
                desc_para.paragraph_format.space_after = Pt(1)
                for run in desc_para.runs:
                    run.font.size = Pt(10)

            if proj.get("technologies"):
                tech = proj["technologies"]
                tech_list = tech if isinstance(tech, list) else [tech]
                tech_para = doc.add_paragraph()
                tech_para.paragraph_format.space_after = Pt(4)
                tech_label = tech_para.add_run("Tech Stack: ")
                tech_label.bold = True
                tech_label.font.size = Pt(10)
                tech_val = tech_para.add_run(", ".join(tech_list))
                tech_val.font.size = Pt(10)

            if proj.get("link"):
                link_para = doc.add_paragraph(proj["link"])
                link_para.paragraph_format.space_after = Pt(4)
                for run in link_para.runs:
                    run.font.size = Pt(9)
                    run.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)

    # ── Certifications ───────────────────────────────────────────────────────
    certifications = cv_data.get("certifications", [])
    if certifications:
        add_section_header("Certifications")
        for cert in certifications:
            cert_para = doc.add_paragraph(style="List Bullet")
            cert_para.paragraph_format.space_after = Pt(2)
            cert_run = cert_para.add_run(cert)
            cert_run.font.size = Pt(10)

    # ── Footer ───────────────────────────────────────────────────────────────
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_para.paragraph_format.space_before = Pt(20)
    footer_run = footer_para.add_run(
        f"Generated by JobGad AI — {datetime.now().strftime('%B %Y')}"
    )
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)

    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


# ─── PDF Formatter ────────────────────────────────────────────────────────────

def generate_cv_pdf(cv_data: dict) -> bytes:
    """
    Generate a professional PDF CV from structured CV data.
    Uses reportlab for PDF generation.
    Returns bytes of the PDF file.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        HRFlowable, ListFlowable, ListItem,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    # Colors
    PRIMARY = HexColor("#1E40AF")
    GRAY = HexColor("#64748B")
    LIGHT = HexColor("#CBD5E1")
    GREEN = HexColor("#16A34A")

    styles = getSampleStyleSheet()

    # Custom styles
    name_style = ParagraphStyle(
        "Name",
        fontSize=22,
        fontName="Helvetica-Bold",
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    contact_style = ParagraphStyle(
        "Contact",
        fontSize=9,
        fontName="Helvetica",
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "Section",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=PRIMARY,
        spaceBefore=12,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body",
        fontSize=10,
        fontName="Helvetica",
        spaceAfter=4,
        leading=14,
    )
    bold_style = ParagraphStyle(
        "Bold",
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceAfter=2,
    )
    small_gray_style = ParagraphStyle(
        "SmallGray",
        fontSize=9,
        fontName="Helvetica",
        textColor=GRAY,
        spaceAfter=2,
    )

    story = []
    personal = cv_data.get("personal_info", {})

    # ── Name ──────────────────────────────────────────────────────────────────
    full_name = personal.get("full_name", "").upper()
    story.append(Paragraph(full_name, name_style))

    # ── Contact ───────────────────────────────────────────────────────────────
    contact_parts = []
    if personal.get("email"):
        contact_parts.append(personal["email"])
    if personal.get("linkedin"):
        contact_parts.append(personal["linkedin"])
    if personal.get("github"):
        contact_parts.append(personal["github"])
    if personal.get("location"):
        contact_parts.append(personal["location"])

    if contact_parts:
        story.append(Paragraph(" | ".join(contact_parts), contact_style))

    def add_section(title):
        story.append(Paragraph(title.upper(), section_style))
        story.append(HRFlowable(
            width="100%",
            thickness=0.5,
            color=LIGHT,
            spaceAfter=6,
        ))

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = cv_data.get("professional_summary", "")
    if summary:
        add_section("Professional Summary")
        story.append(Paragraph(summary, body_style))

    # ── Skills ────────────────────────────────────────────────────────────────
    skills = cv_data.get("relevant_skills", {})
    if skills:
        add_section("Skills")
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                if skill_list:
                    skills_list = skill_list if isinstance(skill_list, list) else [skill_list]
                    text = f"<b>{category.title()}:</b> {', '.join(skills_list)}"
                    story.append(Paragraph(text, body_style))
        elif isinstance(skills, list):
            story.append(Paragraph(", ".join(skills), body_style))

    # ── Education ─────────────────────────────────────────────────────────────
    education = cv_data.get("education", [])
    if education:
        add_section("Education")
        for edu in education:
            degree_text = f"{edu.get('degree', '')} in {edu.get('field', '')}"
            story.append(Paragraph(degree_text, bold_style))
            inst_text = f"{edu.get('institution', '')} — {edu.get('year', '')}"
            story.append(Paragraph(inst_text, small_gray_style))
            if edu.get("achievements"):
                story.append(Paragraph(edu["achievements"], body_style))
            story.append(Spacer(1, 4))

    # ── Experience ────────────────────────────────────────────────────────────
    experience = cv_data.get("experience", [])
    if experience:
        add_section("Experience")
        for exp in experience:
            title_text = f"{exp.get('title', '')} — {exp.get('company', '')}"
            story.append(Paragraph(title_text, bold_style))
            if exp.get("duration"):
                story.append(Paragraph(exp["duration"], small_gray_style))

            items = []
            for resp in exp.get("responsibilities", []):
                items.append(ListItem(
                    Paragraph(resp, body_style),
                    bulletColor=PRIMARY,
                ))
            for ach in exp.get("achievements", []):
                items.append(ListItem(
                    Paragraph(f"<font color='#16A34A'>✓</font> {ach}", body_style),
                    bulletColor=GREEN,
                ))
            if items:
                story.append(ListFlowable(items, bulletType="bullet"))
            story.append(Spacer(1, 4))

    # ── Projects ──────────────────────────────────────────────────────────────
    projects = cv_data.get("projects", [])
    if projects:
        add_section("Projects")
        for proj in projects:
            story.append(Paragraph(proj.get("name", ""), bold_style))
            if proj.get("description"):
                story.append(Paragraph(proj["description"], body_style))
            if proj.get("technologies"):
                tech = proj["technologies"]
                tech_list = tech if isinstance(tech, list) else [tech]
                story.append(Paragraph(
                    f"<b>Tech Stack:</b> {', '.join(tech_list)}",
                    body_style,
                ))
            if proj.get("link"):
                story.append(Paragraph(
                    f'<font color="#1E40AF">{proj["link"]}</font>',
                    small_gray_style,
                ))
            story.append(Spacer(1, 4))

    # ── Certifications ────────────────────────────────────────────────────────
    certifications = cv_data.get("certifications", [])
    if certifications:
        add_section("Certifications")
        items = [
            ListItem(Paragraph(cert, body_style), bulletColor=PRIMARY)
            for cert in certifications
        ]
        story.append(ListFlowable(items, bulletType="bullet"))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        "Footer",
        fontSize=8,
        fontName="Helvetica",
        textColor=GRAY,
        alignment=TA_CENTER,
    )
    story.append(Paragraph(
        f"Generated by JobGad AI — {datetime.now().strftime('%B %Y')}",
        footer_style,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()