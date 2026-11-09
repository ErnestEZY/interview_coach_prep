"""
Unit Tests — backend/services/resume_parser.py
Tests: is_pdf, is_docx, clean_text, DOCX extraction
Uses real file I/O with temporary files; no DB or network needed.
"""
import os
import sys
import io
import tempfile
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.resume_parser import (
    is_pdf,
    is_docx,
    clean_text,
    extract_resume_text,
    is_letter_spaced,
    letter_spaced_ratio,
)
from docx import Document


def make_docx_file(text: str = "Software Engineer with Python skills") -> str:
    """Create a real temporary DOCX file and return its path."""
    buf = io.BytesIO()
    doc = Document()
    doc.add_heading("John Doe", level=1)
    doc.add_paragraph("Email: john@example.com")
    doc.add_paragraph("Summary")
    doc.add_paragraph(text)
    doc.add_paragraph("Education: BSc Computer Science, 2024")
    doc.add_paragraph("Skills: Python, FastAPI, MongoDB")
    doc.save(buf)
    buf.seek(0)

    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp.write(buf.read())
    tmp.close()
    return tmp.name


class TestFileTypeDetection:
    def test_pdf_detected(self):
        assert is_pdf("resume.pdf") is True
        assert is_pdf("resume.PDF") is True

    def test_docx_detected(self):
        assert is_docx("resume.docx") is True
        assert is_docx("resume.DOCX") is True

    def test_txt_not_pdf(self):
        assert is_pdf("resume.txt") is False

    def test_txt_not_docx(self):
        assert is_docx("resume.txt") is False


class TestCleanText:
    def test_removes_extra_spaces(self):
        result = clean_text("hello   world")
        assert "  " not in result

    def test_removes_extra_newlines(self):
        result = clean_text("line1\n\n\nline2")
        assert "\n\n" not in result

    def test_strips_whitespace(self):
        result = clean_text("   hello   ")
        assert result == "hello"

    def test_empty_returns_empty(self):
        assert clean_text("") == ""

    def test_none_returns_empty(self):
        assert clean_text(None) == ""


class TestLetterSpacedDetection:
    """Glyph-by-glyph PDFs must be told apart from resumes that read fine."""

    BROKEN = (
        "S o f t w a r e E n g i n e e r i n g s t u d e n t a t U n i v e r s i t y\n"
        "w i t h 2 y e a r s o f e x p e r i e n c e b u i l d i n g a p p s\n"
        "J a v a S c r i p t , C S S , H T L M a n d G o o g l e A p p s S c r i p t\n"
    )
    HEALTHY = (
        "Software Engineering student at University of Wollongong Malaysia\n"
        "with experience building full-stack and AI-powered applications\n"
        "JavaScript, CSS, HTML and Google Apps Script across five systems\n"
    )

    def test_broken_extraction_is_detected(self):
        assert letter_spaced_ratio(self.BROKEN) == 1.0
        assert is_letter_spaced(self.BROKEN) is True

    def test_readable_prose_is_not_flagged(self):
        assert letter_spaced_ratio(self.HEALTHY) == 0.0
        assert is_letter_spaced(self.HEALTHY) is False

    def test_short_all_caps_heading_is_tolerated(self):
        """A styled "S T U D E N T" banner must not condemn the whole document."""
        text = self.HEALTHY + "S T U D E N T\n"
        assert is_letter_spaced(text) is False

    def test_mostly_broken_document_is_flagged(self):
        assert is_letter_spaced(self.BROKEN + self.BROKEN) is True

    def test_empty_and_missing_text_scores_zero(self):
        assert letter_spaced_ratio("") == 0.0
        assert letter_spaced_ratio(None) == 0.0
        assert is_letter_spaced("") is False


class TestDocxExtraction:
    def test_extract_docx_returns_text(self):
        path = make_docx_file("Python developer with 3 years of experience")
        try:
            text, mime, ocr_used = extract_resume_text(path)
            assert len(text) > 20
            assert "python" in text.lower() or "developer" in text.lower()
        finally:
            os.unlink(path)

    def test_extract_docx_mime_type(self):
        path = make_docx_file()
        try:
            _, mime, _ = extract_resume_text(path)
            assert "wordprocessingml" in mime or "docx" in mime.lower()
        finally:
            os.unlink(path)

    def test_extract_docx_ocr_false(self):
        path = make_docx_file()
        try:
            _, _, ocr_used = extract_resume_text(path)
            assert ocr_used is False
        finally:
            os.unlink(path)

    def test_unsupported_file_raises(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(b"some text")
        tmp.close()
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                extract_resume_text(tmp.name)
        finally:
            os.unlink(tmp.name)
