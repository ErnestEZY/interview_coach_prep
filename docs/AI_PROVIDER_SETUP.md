# AI Provider Setup — Interview Coach Prep (ICP)

> Last updated: October 2026  
> This document summarises all AI provider decisions, model assignments, and env key requirements for the ICP backend.

---

## Required Environment Variables

| Key | Used for | Can remove? |
|---|---|---|
| `OPENROUTER_API_KEY` | CRAG fallback, guardrails fallback, assist fallback | No |
| `GROQ_API_KEY` | Resume analysis (primary), Interview (primary) | No |
| `BAZAARLINK_API_KEY` | Resume/Interview fallback 1 & 2, Assist primary | No |
| `GEMINI_API_KEY` | CRAG primary, guardrails primary | No |
| `MISTRAL_API_KEY` | RAG embeddings at startup only (`mistral-embed`) | No |
| `MISTRAL_RAG_API_KEY` | Removed — falls back to `MISTRAL_API_KEY` automatically | Yes — remove |
| `GROQ_API_KEY` (Groq) | Resume + Interview fast inference | No |

---

## Provider Router (`backend/services/provider_router.py`)

All AI routing is centralised in `provider_router.py`. Three public functions:

### `chat_main()` — Resume Analysis & Interview Engine
**Rotation: Groq → BazaarLink (qwen) → BazaarLink (deepseek) → OpenRouter**

| # | Provider | Model | Notes |
|---|---|---|---|
| 1 | Groq | `qwen/qwen3.8-27b` | ~0.17s, free, confirmed working |
| 2 | BazaarLink | `qwen/qwen3.7-flash:free` | ~2.8s, free |
| 3 | BazaarLink | `deepseek/deepseek-v4-flash-0731free:free` | Different upstream pool |
| 4 | OpenRouter | `nvidia/nemotron-3-super-120b-a12b:free` | Last resort, slow |

A 2s delay is added between each fallback to avoid cascading 429s.

### `chat_crag()` — CRAG Evaluation & Guardrails
**Rotation: Gemini → OpenRouter**

| # | Provider | Model | Notes |
|---|---|---|---|
| 1 | Gemini | `gemini-3.5-flash-lite` | 1,000 RPD free, stable until July 2027 |
| 2 | OpenRouter | `nvidia/nemotron-3.5-lightning:free` | Fallback |

Mistral **removed** from CRAG chain — chat is always 429 on new free accounts. Only `mistral-embed` works.

### `chat_assist()` — AI Writing Assist
**Rotation: BazaarLink → OpenRouter → Groq**

| # | Provider | Model | Notes |
|---|---|---|---|
| 1 | BazaarLink | `qwen/qwen3.7-flash:free` | Fast rewrites |
| 2 | OpenRouter | `nvidia/nemotron-3.5-lightning:free` | Fallback |
| 3 | Groq | `qwen/qwen3.8-27b` | Last resort |

---

## Service → Function Mapping

| Service file | Function called | Purpose |
|---|---|---|
| `ai_feedback.py` | `chat_main()` | Resume analysis JSON output |
| `interview_engine.py` | `chat_main()` (via `_interview_call`) | Interview question generation |
| `assist.py` | `chat_assist()` | Resume text rewriting |
| `rag_engine.py` | `chat_crag()` | CRAG doc evaluation + input/output guardrails |
| `rag_engine.py` | Mistral direct | `mistral-embed` for RAG chunk embeddings at startup |

---

## RAG Engine (`backend/services/rag_engine.py`)

- **Embeddings**: `mistral-embed` via `MISTRAL_API_KEY` at startup only (no per-request cost)
- **Retrieval**: Keyword-only mode (no embedding API call per request — avoids OpenRouter daily quota)
- **CRAG**: Uses `chat_crag()` — fires in parallel with the main feedback call via `asyncio.gather`
- If CRAG fails, the feedback result is still returned (non-fatal, `return_exceptions=True`)

---

## Provider Status (October 2026)

| Provider | Chat | Embeddings | Rate Limit | Notes |
|---|---|---|---|---|
| Groq | ✅ Free | N/A | Per model, generous | `qwen/qwen3.8-27b` confirmed free |
| BazaarLink | ✅ Free | N/A | Has 429s under load | Two free models available |
| OpenRouter | ✅ Free | ✅ Free | 50 req/day (free) | Daily cap hits quickly |
| Gemini | ✅ Free | N/A | 250-1000 RPD | SSL fails locally, works on Render |
| Mistral | ❌ 429 always | ✅ 1024-dim | 1 RPM (new acct) | Chat unusable; embed works fine |
| AtmoRouter | ❌ Paid only | N/A | N/A | Requires USDC deposit, no free tier |
| OrcaRouter | ❌ 403 | N/A | N/A | Key needs dashboard model access config |
| Groq (old Llama) | ❌ Enterprise | N/A | N/A | llama-3.x moved to Enterprise/paid |

---

## Key Architecture Decisions

1. **Parallel CRAG + Feedback**: `asyncio.get_running_loop()` + `create_task` + `run_in_executor` runs CRAG and the main feedback call simultaneously. Total time = `max(CRAG_time, feedback_time)`.

2. **Keyword-only RAG retrieval**: `retrieve_keyword_only()` used instead of `retrieve()` to avoid OpenRouter embedding quota per request. Embeddings only happen once at server startup.

3. **Interview guardrail removed**: Per-turn LLM guardrail replaced with keyword injection check in `interview_routes.py` to reduce API calls per interview turn from 2 to 1.

4. **Single Mistral key**: `MISTRAL_RAG_API_KEY` removed; `MISTRAL_API_KEY` used for both chat (fallback, currently always 429) and embeddings. Config automatically falls back.

5. **Progress bar timeout**: 90s client-side timeout in `dashboard.js` via `Promise.race`. On timeout, shows red error state with "Analysis Timed Out" SweetAlert.

---

## GitHub OAuth (Register page only)

- GitHub OAuth button on the register page is gated behind T&C + Privacy Policy acceptance
- Login page has no T&C gate (by design)
- `register.js` → `githubOAuth()` method checks `termsAccepted && privacyAccepted` before redirecting

---

## Render Deployment Checklist

Add these env vars in Render dashboard → your service → Environment:

```
OPENROUTER_API_KEY=sk-or-v1-...
GROQ_API_KEY=gsk_...
BAZAARLINK_API_KEY=sk-bl-...
GEMINI_API_KEY=AQ.Ab8...
MISTRAL_API_KEY=mstrl_...
```

Remove if present:
```
MISTRAL_RAG_API_KEY  (no longer needed)
GROQ_API_KEY (old)   (if pointing to old key)
GEMINI_API_KEY       (if pointing to old broken key)
```
