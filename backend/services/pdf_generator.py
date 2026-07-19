"""
Server-side ATS-friendly PDF generation using WeasyPrint (pure Python).
Produces text-based PDFs matching the live builder preview exactly.
No system binary required — works on Render's free tier out of the box!
"""

import os
import io
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape


# ── Template loader ──────────────────────────────────────────────────────────
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_JINJA_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)

# Valid theme class names
_VALID_THEMES = {
    "theme-classic",
    "theme-modern",
    "theme-kendall",
    "theme-flat",
    "theme-gov",
}


def generate_resume_pdf(resume: Dict[str, Any], theme_class: str) -> bytes:
    """
    Generate PDF using WeasyPrint (pure Python — no system binary needed).
    Returns raw PDF bytes (text-based, matches preview exactly!).
    """
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    if theme_class not in _VALID_THEMES:
        theme_class = "theme-classic"

    # Render Jinja2 template
    template = _JINJA_ENV.get_template("resume_pdf.html")
    html_content = template.render(resume=resume, theme_class=theme_class)

    print(f"pdf_generator: rendering PDF with WeasyPrint, theme={theme_class!r}")

    font_config = FontConfiguration()

    # WeasyPrint renders HTML directly from string — no temp file needed
    pdf_bytes = HTML(string=html_content, base_url=_TEMPLATE_DIR).write_pdf(
        font_config=font_config,
        presentational_hints=True,
    )

    print(f"pdf_generator: PDF generated successfully, size={len(pdf_bytes)} bytes")
    return pdf_bytes


# Wrapper to make it async (for FastAPI compatibility)
async def generate_resume_pdf_async(resume: Dict[str, Any], theme_class: str) -> bytes:
    import asyncio
    return await asyncio.to_thread(generate_resume_pdf, resume, theme_class)
