"""
Server-side ATS-friendly PDF generation using wkhtmltopdf (Qt WebKit).
Produces text-based PDFs matching the live builder preview exactly.
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


def _find_wkhtmltopdf() -> str | None:
    """
    Locate the wkhtmltopdf binary using multiple strategies.
    Priority: env var > known Linux paths > PATH search > Windows paths.
    """
    import sys
    import shutil

    # 1. Explicit env var (set in Dockerfile or by user)
    path = os.getenv("WKHTMLTOPDF_PATH") or os.getenv("WKHTMLTOPDF_CMD")
    if path and os.path.isfile(path):
        print(f"pdf_generator: wkhtmltopdf from env var: {path!r}")
        return path

    # 2. Known Linux install locations
    # NOTE: the official wkhtmltox .deb installs to /usr/local/bin, NOT /usr/bin
    if sys.platform != "win32":
        linux_paths = [
            "/usr/local/bin/wkhtmltopdf",  # official .deb install location
            "/usr/bin/wkhtmltopdf",        # some distros / apt
        ]
        for p in linux_paths:
            if os.path.isfile(p):
                print(f"pdf_generator: wkhtmltopdf found at: {p!r}")
                return p

    # 3. PATH search
    which = shutil.which("wkhtmltopdf")
    if which:
        print(f"pdf_generator: wkhtmltopdf found in PATH: {which!r}")
        return which

    # 4. Windows standard install locations
    if sys.platform == "win32":
        win_paths = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        ]
        for p in win_paths:
            if os.path.isfile(p):
                print(f"pdf_generator: wkhtmltopdf found at: {p!r}")
                return p

    print("pdf_generator: wkhtmltopdf NOT FOUND. Diagnostics:")
    print("  WKHTMLTOPDF_PATH env:", os.getenv("WKHTMLTOPDF_PATH"))
    print("  PATH search:", shutil.which("wkhtmltopdf"))
    return None


def generate_resume_pdf(resume: Dict[str, Any], theme_class: str) -> bytes:
    """
    Generate PDF using wkhtmltopdf (via pdfkit).
    Returns raw PDF bytes (text-based, matches preview exactly).
    """
    import pdfkit

    if theme_class not in _VALID_THEMES:
        theme_class = "theme-classic"

    wkhtmltopdf_path = _find_wkhtmltopdf()
    if not wkhtmltopdf_path:
        raise RuntimeError(
            "wkhtmltopdf executable not found. "
            "On Windows: install from https://wkhtmltopdf.org/downloads.html. "
            "On Linux/Docker: install via 'apt-get install -y wkhtmltopdf' or set WKHTMLTOPDF_PATH env var."
        )

    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

    # Render Jinja2 template
    template = _JINJA_ENV.get_template("resume_pdf.html")
    html_content = template.render(resume=resume, theme_class=theme_class)

    # wkhtmltopdf options
    options = {
        "page-size": "A4",
        "margin-top": "0mm",
        "margin-right": "0mm",
        "margin-bottom": "0mm",
        "margin-left": "0mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "enable-local-file-access": None,
        "quiet": "",
    }

    # Write HTML to temp file (avoids issues with long strings)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_content)
        temp_html_path = f.name

    try:
        pdf_bytes = pdfkit.from_file(temp_html_path, False, options=options, configuration=config)
        return pdf_bytes
    except Exception:
        import traceback
        traceback.print_exc()
        raise RuntimeError("wkhtmltopdf failed to generate PDF. See deployment logs for details.")
    finally:
        try:
            os.unlink(temp_html_path)
        except Exception:
            pass


# Wrapper to make it async (for FastAPI compatibility)
async def generate_resume_pdf_async(resume: Dict[str, Any], theme_class: str) -> bytes:
    import asyncio
    return await asyncio.to_thread(generate_resume_pdf, resume, theme_class)
