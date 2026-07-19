"""
Unit Tests — backend/services/pdf_generator.py
Tests: PDF generation using wkhtmltopdf/pdfkit
Verifies PDF starts with magic bytes and works for all themes.
"""
import os
import sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.pdf_generator import generate_resume_pdf, _VALID_THEMES


# Sample resume data for testing
def get_sample_resume() -> dict:
    return {
        "name": "John Doe",
        "title": "Software Engineer",
        "email": "john@example.com",
        "phone": "+1 (555) 123-4567",
        "location": "New York, NY",
        "website": "https://johndoe.dev",
        "summary": "Passionate software engineer with 5+ years of experience in web development.",
        "education": [
            {
                "school": "New York University",
                "location": "New York, NY",
                "degree": "B.S. Computer Science",
                "date": "2020",
                "gpa": "3.9"
            }
        ],
        "experience": [
            {
                "company": "Tech Corp",
                "position": "Senior Software Engineer",
                "date": "2022 - Present",
                "bullets": [
                    "Led a team of 5 engineers to build scalable web applications",
                    "Implemented CI/CD pipelines reducing deployment time by 40%"
                ]
            }
        ],
        "projects": [
            {
                "name": "Open Source Project",
                "tech": "Python, FastAPI",
                "bullets": [
                    "Developed a REST API used by 1000+ developers"
                ]
            }
        ],
        "skills_tech": ["Python", "FastAPI", "MongoDB"],
        "skills_tools": ["Git", "Docker"],
        "skills_soft": ["Communication", "Leadership"],
        "skills_other": ["Problem Solving"],
        "certifications": [{"name": "AWS Certified Developer"}],
        "languages": [{"name": "English"}],
        "extra_info": [{"content": "Available for full-time roles"}]
    }


class TestPDFGenerator:
    def test_all_valid_themes_work(self):
        resume = get_sample_resume()
        for theme in _VALID_THEMES:
            pdf_bytes = generate_resume_pdf(resume, theme)
            assert pdf_bytes is not None
            assert isinstance(pdf_bytes, bytes)
            # Verify PDF magic bytes (%PDF)
            assert pdf_bytes.startswith(b"%PDF")

    def test_invalid_theme_defaults_to_classic(self):
        resume = get_sample_resume()
        pdf_bytes = generate_resume_pdf(resume, "invalid-theme-that-does-not-exist")
        assert pdf_bytes is not None
        assert pdf_bytes.startswith(b"%PDF")

    def test_minimal_resume_works(self):
        minimal_resume = {
            "name": "Jane Smith",
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "languages": [],
            "extra_info": []
        }
        pdf_bytes = generate_resume_pdf(minimal_resume, "theme-modern")
        assert pdf_bytes is not None
        assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
class TestAsyncPDFGenerator:
    async def test_async_generate_pdf(self):
        resume = get_sample_resume()
        from backend.services.pdf_generator import generate_resume_pdf_async
        pdf_bytes = await generate_resume_pdf_async(resume, "theme-classic")
        assert pdf_bytes is not None
        assert pdf_bytes.startswith(b"%PDF")
