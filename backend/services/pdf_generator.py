"""
Server-side ATS-friendly PDF generation using wkhtmltopdf (Qt WebKit).
Produces text-based PDFs matching the live builder preview exactly.
Lightweight, great for Render's free tier!
"""

import os
import io
import tempfile
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
    Generate PDF using wkhtmltopdf (via pdfkit).
    Returns raw PDF bytes (text-based, matches preview exactly!
    """
    import pdfkit

    # Path to wkhtmltopdf (if not in PATH)
    wkhtmltopdf_path = None
    import sys
    import shutil
    # Windows common install locations
    if sys.platform == "win32":
        possible_paths = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                wkhtmltopdf_path = path
                break
    # Respect explicit env var if set (common on some installers)
    if not wkhtmltopdf_path:
        wkhtmltopdf_path = os.getenv("WKHTMLTOPDF_PATH") or os.getenv("WKHTMLTOPDF_CMD")
    # Try to find in PATH
    if not wkhtmltopdf_path:
        which_path = shutil.which("wkhtmltopdf")
        if which_path:
            wkhtmltopdf_path = which_path

    if theme_class not in _VALID_THEMES:
        theme_class = "theme-classic"

    # Render Jinja2 template
    template = _JINJA_ENV.get_template("resume_pdf.html")
    html_content = template.render(resume=resume, theme_class=theme_class)

    # wkhtmltopdf options (perfect match preview)
    options = {
        "page-size": "A4",
        "margin-top": "0mm",
        "margin-right": "0mm",
        "margin-bottom": "0mm",
        "margin-left": "0mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "enable-local-file-access": None,  # Allow local files (if any)
        "quiet": "",
    }

    # Write HTML to temp file (avoids issues with long strings)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_content)
        temp_html_path = f.name

    # Configure pdfkit with our wkhtmltopdf path (if found).
    if not wkhtmltopdf_path:
        print("pdf_generator: wkhtmltopdf not found. Diagnostics:")
        print("  WKHTMLTOPDF_PATH:", os.getenv("WKHTMLTOPDF_PATH"))
        print("  WKHTMLTOPDF_CMD:", os.getenv("WKHTMLTOPDF_CMD"))
        print("  which wkhtmltopdf:", shutil.which("wkhtmltopdf"))
        raise RuntimeError(
            "wkhtmltopdf executable not found. Install wkhtmltopdf in the container or set WKHTMLTOPDF_PATH env var."
        )

    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

    try:
        pdf_bytes = pdfkit.from_file(temp_html_path, False, options=options, configuration=config)
        return pdf_bytes
    except Exception:
        # wkhtmltopdf unavailable or failed to run.
        import traceback
        traceback.print_exc()
        raise RuntimeError(
            "wkhtmltopdf failed to generate PDF. See deployment logs for details."
        )
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_html_path)
        except Exception:
            pass


# Wrapper to make it async (for FastAPI compatibility)
async def generate_resume_pdf_async(resume: Dict[str, Any], theme_class: str) -> bytes:
    import asyncio
    return await asyncio.to_thread(generate_resume_pdf, resume, theme_class)
