"""
Provider Router — centralised multi-provider fallback utility.

Rotation strategy:
  Resume / Interview  : Groq → BazaarLink (qwen) → BazaarLink (deepseek) → OpenRouter
  CRAG / Guardrails   : Gemini → OpenRouter
  AI Writing Assist   : BazaarLink → OpenRouter → Groq
"""

import json
import time
from typing import Optional
from openai import OpenAI

try:
    from google import genai as _genai
    from google.genai import types as _gtypes
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False

from ..core.config import (
    GROQ_API_KEY, GROQ_BASE_URL,
    BAZAARLINK_API_KEY, BAZAARLINK_BASE_URL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    GEMINI_API_KEY,
)

# ── Client builders ────────────────────────────────────────────────────────

def _groq() -> OpenAI:
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

def _bazaarlink() -> OpenAI:
    return OpenAI(api_key=BAZAARLINK_API_KEY, base_url=BAZAARLINK_BASE_URL)

def _openrouter() -> OpenAI:
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

def _is_rate_limit(e: Exception) -> bool:
    err = str(e)
    return any(k in err for k in ["429", "400", "500", "rate", "limit", "quota", "overload"])

# ── Main inference (Resume + Interview): Groq → BazaarLink → OpenRouter ───

def chat_main(
    messages: list,
    model_groq: str = "qwen/qwen3.8-27b",
    model_bl: str = "qwen/qwen3.7-flash:free",
    model_bl2: str = "deepseek/deepseek-v4-flash-0731free:free",
    model_or: str = "nvidia/nemotron-3-super-120b-a12b:free",
    response_format: Optional[dict] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    retry_delay: float = 2.0,
) -> str:
    """Try Groq → BazaarLink (qwen) → BazaarLink (deepseek) → OpenRouter."""
    kwargs = {"messages": messages, "temperature": temperature}
    if response_format:
        kwargs["response_format"] = response_format
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    # 1. Groq
    if GROQ_API_KEY:
        try:
            resp = _groq().chat.completions.create(model=model_groq, **kwargs)
            content = resp.choices[0].message.content
            if content:
                return content
            raise ValueError("Empty response from Groq")
        except Exception as e:
            print(f"[Router] Groq failed ({type(e).__name__}) → BazaarLink qwen")
            time.sleep(retry_delay)

    # 2. BazaarLink (qwen)
    if BAZAARLINK_API_KEY:
        try:
            resp = _bazaarlink().chat.completions.create(model=model_bl, **kwargs)
            content = resp.choices[0].message.content
            if content:
                return content
            raise ValueError("Empty response from BazaarLink qwen")
        except Exception as e:
            print(f"[Router] BazaarLink qwen failed ({type(e).__name__}) → BazaarLink deepseek")
            time.sleep(retry_delay)

    # 3. BazaarLink (deepseek) — different upstream pool
    if BAZAARLINK_API_KEY:
        try:
            resp = _bazaarlink().chat.completions.create(model=model_bl2, **kwargs)
            content = resp.choices[0].message.content
            if content:
                return content
            raise ValueError("Empty response from BazaarLink deepseek")
        except Exception as e:
            print(f"[Router] BazaarLink deepseek failed ({type(e).__name__}) → OpenRouter")
            time.sleep(retry_delay)

    # 4. OpenRouter
    if OPENROUTER_API_KEY:
        resp = _openrouter().chat.completions.create(model=model_or, **kwargs)
        return resp.choices[0].message.content

    raise RuntimeError("All main inference providers exhausted")


# ── CRAG / Guardrails: Gemini → Mistral → OpenRouter ─────────────────────

def chat_crag(
    prompt: str,
    model_gemini: str = "gemini-3.5-flash-lite",
    model_or: str = "nvidia/nemotron-3.5-lightning:free",
    retry_delay: float = 2.0,
) -> str:
    """Try Gemini → OpenRouter. Mistral removed (chat always 429 on free tier)."""

    # 1. Gemini
    if GEMINI_API_KEY and _GEMINI_AVAILABLE:
        try:
            gclient = _genai.Client(api_key=GEMINI_API_KEY)
            resp = gclient.models.generate_content(
                model=model_gemini,
                contents=prompt,
                config=_gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    automatic_function_calling=_gtypes.AutomaticFunctionCallingConfig(disable=True)
                )
            )
            if resp.text:
                return resp.text
            raise ValueError("Empty response from Gemini")
        except Exception as e:
            print(f"[Router] Gemini CRAG failed ({type(e).__name__}) → OpenRouter")
            time.sleep(retry_delay)

    # 2. OpenRouter
    if OPENROUTER_API_KEY:
        resp = _openrouter().chat.completions.create(
            model=model_or,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return resp.choices[0].message.content

    raise RuntimeError("All CRAG providers exhausted")


# ── AI Writing Assist: BazaarLink → OpenRouter → Groq ─────────────────────

def chat_assist(
    system_prompt: str,
    user_prompt: str,
    model_bl: str = "qwen/qwen3.7-flash:free",
    model_or: str = "nvidia/nemotron-3.5-lightning:free",
    model_groq: str = "qwen/qwen3.8-27b",
    temperature: float = 0.4,
    max_tokens: int = 1024,
    retry_delay: float = 2.0,
) -> str:
    """Try BazaarLink → OpenRouter → Groq."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]
    kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}

    # 1. BazaarLink
    if BAZAARLINK_API_KEY:
        try:
            resp = _bazaarlink().chat.completions.create(model=model_bl, **kwargs)
            content = resp.choices[0].message.content
            if content:
                return content.strip()
            raise ValueError("Empty response from BazaarLink")
        except Exception as e:
            print(f"[Router] BazaarLink assist failed ({type(e).__name__}) → OpenRouter")
            time.sleep(retry_delay)

    # 2. OpenRouter
    if OPENROUTER_API_KEY:
        try:
            resp = _openrouter().chat.completions.create(model=model_or, **kwargs)
            content = resp.choices[0].message.content
            if content:
                return content.strip()
            raise ValueError("Empty response from OpenRouter")
        except Exception as e:
            print(f"[Router] OpenRouter assist failed ({type(e).__name__}) → Groq")
            time.sleep(retry_delay)

    # 3. Groq
    if GROQ_API_KEY:
        resp = _groq().chat.completions.create(model=model_groq, **kwargs)
        return resp.choices[0].message.content.strip()

    raise RuntimeError("All assist providers exhausted")
