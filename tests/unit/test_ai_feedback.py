"""
Unit Tests — backend/services/ai_feedback.py
Tests: parse_json_response, score breakdown validation, ScoreBreakdown clamping
No network calls — Mistral API is mocked.
"""
import os
import sys
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.ai_feedback import parse_json_response, build_resume_prompt


class TestParseJsonResponse:
    def test_valid_json_parsed(self):
        data = {
            "IsResume": True,
            "Score": 78,
            "ScoreBreakdown": {
                "ImpactScore": 32,
                "SkillScore": 24,
                "StructureScore": 16,
                "ATSScore": 6
            },
            "Advantages": ["Good structure"],
            "Disadvantages": ["Needs summary"],
            "Suggestions": ["Add a summary section"],
            "Keywords": ["Python", "FastAPI"],
            "Location": "Kuala Lumpur",
            "DetectedJobTitle": "Software Engineer"
        }
        result = parse_json_response(json.dumps(data))
        assert result["Score"] == 78
        assert result["IsResume"] is True

    def test_markdown_code_block_stripped(self):
        data = {"IsResume": True, "Score": 50, "ScoreBreakdown": {
            "ImpactScore": 20, "SkillScore": 15,
            "StructureScore": 10, "ATSScore": 5},
            "Advantages": [], "Disadvantages": [], "Suggestions": [],
            "Keywords": [], "Location": "", "DetectedJobTitle": ""}
        raw = f"```json\n{json.dumps(data)}\n```"
        result = parse_json_response(raw)
        assert result["Score"] == 50

    def test_malformed_json_returns_fallback(self):
        result = parse_json_response("{not valid json}")
        assert result["IsResume"] is True
        assert result["Score"] == 50

    def test_missing_is_resume_defaults_true(self):
        data = {"Score": 60, "ScoreBreakdown": {
            "ImpactScore": 24, "SkillScore": 18,
            "StructureScore": 12, "ATSScore": 6},
            "Advantages": [], "Disadvantages": [],
            "Suggestions": [], "Keywords": []}
        result = parse_json_response(json.dumps(data))
        assert result["IsResume"] is True

    def test_score_breakdown_sum_matches_score(self):
        data = {
            "IsResume": True, "Score": 80,
            "ScoreBreakdown": {
                "ImpactScore": 35, "SkillScore": 25,
                "StructureScore": 15, "ATSScore": 5
            },
            "Advantages": [], "Disadvantages": [],
            "Suggestions": [], "Keywords": []
        }
        result = parse_json_response(json.dumps(data))
        bd = result["ScoreBreakdown"]
        total = bd["ImpactScore"] + bd["SkillScore"] + bd["StructureScore"] + bd["ATSScore"]
        assert total == result["Score"]

    def test_score_clamped_to_max(self):
        """ImpactScore > 40 must be clamped."""
        data = {
            "IsResume": True, "Score": 100,
            "ScoreBreakdown": {
                "ImpactScore": 60,  # exceeds max 40
                "SkillScore": 20,
                "StructureScore": 15,
                "ATSScore": 5
            },
            "Advantages": [], "Disadvantages": [],
            "Suggestions": [], "Keywords": []
        }
        result = parse_json_response(json.dumps(data))
        assert result["ScoreBreakdown"]["ImpactScore"] <= 40

    def test_score_breakdown_non_negative(self):
        data = {
            "IsResume": True, "Score": 30,
            "ScoreBreakdown": {
                "ImpactScore": -5,
                "SkillScore": 20,
                "StructureScore": 10,
                "ATSScore": 5
            },
            "Advantages": [], "Disadvantages": [],
            "Suggestions": [], "Keywords": []
        }
        result = parse_json_response(json.dumps(data))
        for val in result["ScoreBreakdown"].values():
            assert val >= 0


class TestBuildResumePrompt:
    def test_prompt_contains_text(self):
        prompt = build_resume_prompt("I am a developer", "context here")
        assert "I am a developer" in prompt

    def test_prompt_contains_context(self):
        prompt = build_resume_prompt("resume text", "some RAG context")
        assert "some RAG context" in prompt

    def test_ocr_warning_added_when_ocr_used(self):
        prompt = build_resume_prompt("text", "ctx", ocr_used=True)
        assert "ATS" in prompt and "Canva" in prompt

    def test_ocr_warning_absent_without_flag(self):
        prompt = build_resume_prompt("text", "ctx", ocr_used=False)
        assert "Canva-style" not in prompt
