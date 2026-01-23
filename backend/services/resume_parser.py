from typing import Tuple
from docx import Document
from pdfminer.high_level import extract_text
from pypdf import PdfReader
import os

def is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")

def is_docx(filename: str) -> bool:
    return filename.lower().endswith(".docx") or filename.lower().endswith(".doc")

def extract_resume_text(path: str) -> Tuple[str, str]:
    name = os.path.basename(path)
    text = ""
    mime = ""

    if is_pdf(name):
        mime = "application/pdf"
        # Try pdfminer first
        try:
            text = extract_text(path).strip()
        except Exception:
            text = ""
        
        # Fallback to pypdf if pdfminer failed or returned very little text
        if len(text) < 50:
            try:
                reader = PdfReader(path)
                pypdf_text = ""
                for page in reader.pages:
                    pypdf_text += page.extract_text() + "\n"
                if len(pypdf_text.strip()) > len(text):
                    text = pypdf_text.strip()
            except Exception:
                pass
        
        if not text or len(text) < 20:
            raise ValueError(
                "Could not extract text from this PDF. It might be an image-based PDF or a scanned document. "
                "Please upload a PDF with selectable text, or a Word (.docx) file."
            )
        return text, mime

    if name.lower().endswith(".doc"):
        raise ValueError("Please convert .doc to .docx or pdf")
    
    if is_docx(name):
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        doc = Document(path)
        text = "\n".join([p.text for p in doc.paragraphs])
        if not text.strip():
             raise ValueError("The Word document appears to be empty.")
        return text.strip(), mime
    
    raise ValueError(f"Unsupported file type: {name}. Please upload a PDF or DOCX file.")
