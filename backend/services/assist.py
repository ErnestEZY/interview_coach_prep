"""
AI Writing Assist Service
Uses open-mistral-nemo to polish/rewrite user-provided text.
Keeps it lightweight — fast responses, low token cost.
"""

import os
import re
from typing import List, Optional
from dotenv import load_dotenv

try:
    from mistralai import Mistral
except (ImportError, AttributeError):
    try:
        from mistralai.client import Mistral
    except ImportError:
        from mistralai import MistralClient as Mistral

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
ASSIST_MODEL = "open-mistral-nemo"

# Action verbs that match exactly what the resume builder UI shows to users
_RESUME_ACTION_VERBS = (
    "Developed, Implemented, Designed, Optimized, Led, Managed, Created, Improved, "
    "Increased, Reduced, Analyzed, Engineered, Launched, Collaborated"
)


def _safe_trim(text: str, char_limit: int) -> str:
    """Trim text to char_limit without cutting mid-word. Prefers sentence boundary, falls back to word boundary."""
    if len(text) <= char_limit:
        return text
    # Try to cut at last sentence-ending punctuation within limit
    chunk = text[:char_limit]
    for sep in ('. ', '! ', '? '):
        idx = chunk.rfind(sep)
        if idx > int(char_limit * 0.7):   # only if we kept at least 70%
            return chunk[:idx + 1].rstrip()
    # Fall back to last space (word boundary)
    idx = chunk.rfind(' ')
    if idx > int(char_limit * 0.7):
        return chunk[:idx].rstrip()
    return chunk.rstrip()


def _strip_markdown(text: str) -> str:
    """Remove ALL markdown formatting and wrapping quotes from text."""
    # Remove bold/italic: **word**, *word*, __word__, _word_
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_\n]+)_{1,3}', r'\1', text)
    # Remove any stray lone asterisks or underscores
    text = re.sub(r'(?<!\w)\*+(?!\w)', '', text)
    text = re.sub(r'(?<!\w)_+(?!\w)', '', text)
    # Remove markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = text.strip()
    # Strip wrapping quotes the model sometimes adds: "output" or 'output'
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    return text


# ── Shared instruction preamble ─────────────────────────────────────────────
_BASE_INSTRUCTIONS = (
    "You are a professional resume writing assistant helping job seekers present themselves strongly. "
    "Your job is to ENHANCE and ELEVATE the user's text — making it more impactful, professional, and detailed. "
    "You may expand and improve the content, but do NOT invent false facts, fake companies, or fictional metrics.\n"
    "Rules you MUST follow:\n"
    "1. Expand on the original meaning to make it more professional and detailed — do not just rephrase.\n"
    "2. Use stronger, more precise vocabulary. Replace weak verbs with powerful action verbs.\n"
    "3. Do NOT start with 'I have', 'I am', or 'My'. Omit the subject pronoun.\n"
    "4. NEVER use markdown formatting — no **bold**, no *italic*, no bullet dashes, no headers.\n"
    "5. Plain text ONLY. If you include ** or __ symbols in your output, you have failed.\n"
    "6. Do NOT wrap the output in quotation marks — return the raw text directly.\n"
    "7. Do NOT add any explanation, preamble, or commentary — return ONLY the enhanced content.\n"
)


def _call_nemo(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
    """Low-level call to open-mistral-nemo."""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not configured.")
    client = Mistral(api_key=MISTRAL_API_KEY)
    resp = client.chat.complete(
        model=ASSIST_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=1024,   # increased: 4 bullets × 250 chars + summary up to 500 chars needs headroom
    )
    return resp.choices[0].message.content.strip()


# ── Summary assist ───────────────────────────────────────────────────────────

def improve_summary(current_text: str, job_title: str = "", char_limit: int = 250) -> str:
    """
    Improve a professional summary — longer, more detailed, more impactful.
    Returns a single paragraph, max `char_limit` characters, using 90%+ of the limit.
    """
    target_low  = int(char_limit * 0.88)   # aim for 88–100% of limit
    system = (
        _BASE_INSTRUCTIONS
        + f"\nYou are improving a Professional Summary section on a resume.\n"
        + "A professional summary is a 2–3 sentence narrative paragraph at the top of a resume — NOT bullet points.\n"
        + "It should flow naturally and cover: who the candidate is professionally, their key skills or strengths, and their career direction or goal.\n"
        + f"The output MUST be a single flowing paragraph between {target_low} and {char_limit} characters — count carefully.\n"
        + f"CRITICAL: You MUST write at least {target_low} characters. Anything shorter is a failed output.\n"
        + "Do NOT use action verbs at the start — this is a narrative, not a bullet point.\n"
        + "Write in third-person-implied or first-person-implied style (e.g. 'Dedicated software engineer...' or 'Software engineer with...').\n"
        + "Make it confident, specific, and professional — like something a career coach would write.\n"
        + "Do NOT use the Google XYZ formula here — this is prose, not an achievement bullet.\n"
        + "NEVER output markdown. Return ONLY the plain text summary, nothing else."
    )
    context = f"Target job title: {job_title}\n\n" if job_title else ""
    user = f"{context}Original summary to improve:\n{current_text}"
    result = _call_nemo(system, user, temperature=0.45)
    result = _strip_markdown(result)
    return _safe_trim(result, char_limit)


# ── Bullet point assist ──────────────────────────────────────────────────────

def improve_bullets(
    bullets: List[str],
    role_context: str = "",
    section: str = "experience",
    char_limit: int = 250,
) -> List[str]:
    """
    Rewrite a list of bullet points using the Google XYZ formula.
    Returns the same number of bullets, each max `char_limit` characters.
    - section: 'experience' or 'projects'
    """
    count = len(bullets)
    bullets_text = "\n".join(f"{i+1}. {b}" for i, b in enumerate(bullets))

    target_low = int(char_limit * 0.85)   # aim for 85–100% of limit per bullet

    if section == "projects":
        section_instruction = (
            "These are project description bullets on a resume.\n"
            "Improve each bullet using the Google XYZ formula:\n"
            "  [Action Verb] [X — what you built/accomplished], resulting in [Y — measurable outcome], by [Z — how you did it].\n"
            "Rules:\n"
            f"- ALWAYS start with a strong past-tense action verb from this list: {_RESUME_ACTION_VERBS}.\n"
            "- Make each bullet more detailed and impactful — expand with context and specific outcomes.\n"
            "- Keep the technology stack or tools if mentioned in the original.\n"
            "- Each bullet must be a full, complete sentence.\n"
            "- NEVER use markdown bold (**word**) or any special formatting — plain text ONLY."
        )
    else:
        section_instruction = (
            "These are work experience achievement bullets on a resume.\n"
            "Improve each bullet using the strict Google XYZ formula:\n"
            "  [Action Verb] [X — what you accomplished] as measured by [Y — quantified result], by [Z — method or approach].\n"
            "Rules:\n"
            f"- ALWAYS start with a strong past-tense action verb from this list: {_RESUME_ACTION_VERBS}.\n"
            "- Make each bullet more detailed and impactful — add context, specifics, and measurable outcomes.\n"
            "- If the original has a metric (%, number, time), keep and highlight it.\n"
            "- If no metric exists, phrase the impact concretely using qualitative specifics.\n"
            "- Each bullet must be a single complete sentence. No pronouns starting with 'I'.\n"
            "- NEVER use markdown bold (**word**) or any special formatting — plain text ONLY."
        )

    system = (
        _BASE_INSTRUCTIONS
        + f"\n{section_instruction}\n\n"
        + f"CHARACTER COUNT RULES (strictly enforced):\n"
        + f"- Each bullet MUST be between {target_low} and {char_limit} characters.\n"
        + f"- Anything under {target_low} characters is too short and counts as a failed output.\n"
        + f"- Do NOT exceed {char_limit} characters — count carefully before returning.\n"
        + f"Return EXACTLY {count} bullet(s), one per line, numbered 1. 2. 3. etc.\n"
        + "Do NOT include any explanation, preamble, or extra text — ONLY the numbered bullets.\n"
        + "Do NOT wrap any word in ** or any markdown symbol. Plain text only."
    )
    context = f"Role/Project context: {role_context}\n\n" if role_context else ""
    user = f"{context}Original bullets:\n{bullets_text}"

    raw = _call_nemo(system, user)

    # Parse numbered lines back into a list, strip any ** the model sneaks in
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    result = []
    for line in lines:
        # Strip leading "1. " / "- " / "• " etc.
        clean = line.lstrip("0123456789.-•) ").strip()
        # Remove ALL markdown formatting
        clean = _strip_markdown(clean)
        if clean:
            result.append(_safe_trim(clean, char_limit))

    # Ensure we return the same count as input (pad/trim if model misbehaves)
    while len(result) < count:
        result.append(bullets[len(result)])  # fall back to original
    return result[:count]


# ── Manual profile field assist ──────────────────────────────────────────────

def improve_manual_field(
    field: str,
    current_text: str,
    job_title: str = "",
    char_limit: int = 500,
) -> str:
    """
    Rewrite a single manual profile form field.
    field: 'summary' | 'skills' | 'achievement'
    Returns rewritten text within char_limit.
    """
    # Per-field safe targets — give a 15-char buffer below the hard HTML maxlength
    # so the output never gets chopped at the input boundary.
    # summary   → maxlength 500, target 430–480  (88–96%)
    # skills    → maxlength 300, target 240–280  (80–93%)
    # achievement → maxlength 500, target 400–470 (80–94%)
    field_safe_ceiling = {
        "summary":     char_limit - 20,   # target max 480
        "skills":      char_limit - 20,   # target max 280
        "achievement": char_limit - 30,   # target max 470 (2 sentences need more breathing room)
    }
    safe_ceil  = field_safe_ceiling.get(field, char_limit - 20)
    target_low = int(safe_ceil * 0.88)

    field_instructions = {
        "summary": (
            f"Improve this Professional Summary for a resume. "
            "A professional summary is a 2–3 sentence narrative paragraph — NOT bullet points and NOT the Google XYZ formula. "
            "It should cover: who the candidate is professionally, their key skills or strengths, and their career direction or goal. "
            f"Write a single flowing paragraph between {target_low} and {safe_ceil} characters — count every character carefully. "
            f"CRITICAL: You MUST write at least {target_low} characters but MUST NOT exceed {safe_ceil} characters. "
            "Write in third-person-implied style (e.g. 'Dedicated software engineer with...' or 'Results-driven analyst specialising in...'). "
            "Make it confident, specific, and professional — like something a career coach would write. "
            "Do NOT start with an action verb — this is narrative prose, not an achievement bullet. "
            "Plain text ONLY — no markdown, no ** symbols, no bold."
        ),
        "skills": (
            f"Improve this list of skills to be cleaner, more complete, and resume-appropriate. "
            f"Return a comma-separated list between {target_low} and {safe_ceil} characters. "
            "Remove duplicates, fix capitalization. Add closely related skills if they logically fit the role. "
            "Plain text ONLY — no markdown, no ** symbols."
        ),
        "achievement": (
            f"Improve this Key Achievement bullet using the exact same Google XYZ formula used in professional resumes:\n"
            f"  [Action Verb] [X — what you accomplished] as measured by [Y — quantified result], by doing [Z — method or approach].\n"
            f"Rules:\n"
            f"- ALWAYS start with a strong past-tense action verb from this list: {_RESUME_ACTION_VERBS}.\n"
            f"- Write 1–2 complete sentences, between {target_low} and {safe_ceil} characters total — count carefully.\n"
            f"- CRITICAL: Do NOT exceed {safe_ceil} characters.\n"
            "- If the original has a metric (%, number, time), keep and highlight it.\n"
            "- If no metric exists, phrase the impact concretely and specifically — no vague statements.\n"
            "- Each sentence must be a complete, standalone achievement. No pronouns starting with 'I'.\n"
            "- Plain text ONLY — no markdown, no ** symbols, no bold."
        ),
    }
    instruction = field_instructions.get(
        field,
        f"Improve this field professionally between {target_low} and {safe_ceil} characters. Plain text only, no markdown."
    )
    system = _BASE_INSTRUCTIONS + f"\n{instruction}\nReturn ONLY the improved text. Zero markdown symbols."
    context = f"Target job title: {job_title}\n\n" if job_title else ""
    user = f"{context}Original text to improve:\n{current_text}"
    result = _call_nemo(system, user, temperature=0.45)
    result = _strip_markdown(result)
    return _safe_trim(result, char_limit)
