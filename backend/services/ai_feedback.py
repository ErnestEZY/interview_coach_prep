import json
import re
from typing import List, Dict, Any
from mistralai import Mistral
from ..core.config import MISTRAL_API_KEY

from .rag_engine import rag_engine

def build_resume_prompt(text: str, context: str = "") -> str:
    prompt = (
        "You are an expert career coach specializing in helping candidates launch or advance their careers, with a primary focus on fresh graduates. "
        "Analyze the following resume and provide structured feedback in strictly valid JSON format. "
        "Your evaluation should be inclusive of all job seekers but prioritized for the graduate journey by:\n"
        "1. Highlighting academic projects, clubs, and volunteer work as professional strengths for those with limited experience.\n"
        "2. Identifying transferable skills from any work experience (even if unrelated to the target job), showing how these skills apply to the new role.\n"
        "3. Providing actionable advice for both entry-level and experienced candidates, emphasizing how to bridge gaps in professional history.\n\n"
        "Do not include any markdown formatting (like ```json). Return ONLY the JSON object.\n\n"
    )
    
    if context:
        prompt += (
            "### EVALUATION CRITERIA (RAG CONTEXT)\n"
            "Use the following guidelines to evaluate the resume:\n"
            f"{context}\n\n"
        )

    prompt += (
        "The JSON must have the following keys:\n"
        "- \"IsResume\": a boolean (true/false). Be strict: only set to true if the text clearly represents a professional resume, CV, or LinkedIn profile summary. Set to false if the text is irrelevant (e.g., academic reports, assignments, essays, stories, recipes, random gibberish, or completely different document types).\n"
        "- \"Score\": an integer from 0 to 100 representing the overall quality.\n"
        "- \"Advantages\": a list of strings highlighting strong points.\n"
        "- \"Disadvantages\": a list of strings highlighting weak points.\n"
        "- \"Suggestions\": a list of strings for improvement.\n"
        "- \"Keywords\": a list of 10-15 essential skills and industry keywords strictly extracted from the resume text.\n"
        "- \"Location\": a string representing the user's current residential city or state (e.g., 'Kuala Lumpur', 'Petaling Jaya') extracted from the contact information section. Do NOT use company locations or previous work locations. If not found, return an empty string.\n"
        "- \"DetectedJobTitle\": a string representing the most likely target job title for this user based on their experience and skills (e.g., 'Software Engineer', 'Data Scientist'). If not clear, return an empty string.\n"
        "- \"Email\": user email if found.\n"
        "- \"Phone\": user phone number if found.\n"
        "- \"Website\": user portfolio or LinkedIn URL if found.\n"
        "- \"ProfessionalSummary\": a polished 2-3 sentence summary based on the resume content.\n"
        "- \"Education\": a list of objects with keys: \"Institution\", \"Degree\", \"Date\", \"Location\", \"GPA\".\n"
        "- \"Experience\": a list of objects with keys: \"Company\", \"Position\", \"Date\", \"Bullets\" (a list of 3-5 polished, high-impact bullet points starting with action verbs).\n"
        "- \"Projects\": a list of objects with keys: \"Name\", \"Tech\", \"Bullets\" (list of points).\n"
        "- \"SkillsTech\": a comma-separated string of technical skills.\n"
        "- \"SkillsTools\": a comma-separated string of tools/platforms.\n"
        "- \"SkillsSoft\": a comma-separated string of soft skills.\n"
        "- \"Certifications\": a list of strings.\n"
        "- \"Languages\": a list of strings.\n"
        "- \"AdditionalInfo\": a list of strings for any other relevant info.\n\n"
        "STRICT GUIDELINE FOR IsResume:\n"
        "1. If the text has a name and at least one section like 'Experience', 'Education', or 'Skills', it is a resume (true).\n"
        "2. If the text is a short bio or a list of skills, it is still a resume (true).\n"
        "3. Set to false if the content is an academic report, research paper, course assignment, or entirely unrelated to professional identity.\n\n"
        "IMPORTANT: If \"IsResume\" is false, set Score to 0 and all lists to empty, but still return a valid JSON.\n\n"
        "Resume Text:\n" + text
    )
    return prompt

def parse_json_response(resp: str) -> Dict[str, Any]:
    # Remove any markdown code block markers if present
    clean_resp = re.sub(r'```json\s*|\s*```', '', resp).strip()
    try:
        data = json.loads(clean_resp)
        # Ensure IsResume exists
        if "IsResume" not in data:
            data["IsResume"] = True
        return data
    except json.JSONDecodeError:
        # Fallback if JSON is malformed
        return {
            "IsResume": True,
            "Score": 50,
            "Advantages": ["Could not parse detailed advantages."],
            "Disadvantages": ["Could not parse detailed disadvantages."],
            "Suggestions": ["Please try again."],
            "Keywords": [],
            "Location": "",
            "DetectedJobTitle": ""
        }

def get_feedback(text: str) -> Dict[str, Any]:
    if not MISTRAL_API_KEY:
        return {
            "IsResume": True,
            "Score": 75,
            "Advantages": ["Clear structure", "Relevant experience"],
            "Disadvantages": ["Generic statements", "Missing quantified achievements"],
            "Suggestions": ["Add metrics", "Tailor for job keywords"],
            "Keywords": ["Python", "FastAPI", "MongoDB", "Resume", "Interview"],
            "Location": "Kuala Lumpur",
            "DetectedJobTitle": "Software Engineer"
        }
    
    # RAG Step: Retrieve relevant context based on resume content
    # We take the first 800 characters for retrieval to speed up context lookup
    relevant_chunks = rag_engine.retrieve(text[:800], top_k=3)
    context = "\n---\n".join(relevant_chunks)
    
    client = Mistral(api_key=MISTRAL_API_KEY)
    
    completion = client.chat.complete(
        model="mistral-small-latest", # Switch to faster, highly efficient model
        messages=[{"role": "user", "content": build_resume_prompt(text, context)}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    content = completion.choices[0].message.content
    return parse_json_response(content)
