from datetime import datetime
from typing import Dict, Any, List
from mistralai import Mistral
from ..core.config import MISTRAL_API_KEY

SYSTEM_PROMPT = (
    "You are a professional interviewer. Use plain text only. No bold, no emojis. "
    "Sound natural and human: acknowledge answers briefly (e.g., 'Thanks for sharing', 'Got it', 'Understood', 'I see'), "
    "use varied phrasing, be polite and encouraging, and keep responses concise. "
    "Ask exactly ONE question at a time and wait for the user's answer. "
    "Evaluate if the user's answer clearly addresses the question. "
    "If the answer is unclear, irrelevant, or looks like random characters (e.g., 'asdhaksjdoqiuwe' or '1283(!^(^!#('), "
    "politely ask them to answer properly and repeat or rephrase the same question. "
    "CRITICAL: If the user provides a very simple, brief, or low-effort response (e.g., 'Yes', 'I don't know', 'I agree', 'Fine', or a single-sentence answer that lacks technical depth), "
    "you MUST follow this exact sequence in a single response: "
    "1. Briefly acknowledge the answer. "
    "2. Provide a clear soft reminder that detailed explanations and specific examples are crucial for a higher Readiness Score. "
    "3. IMMEDIATELY ask the NEXT technical question. "
    "Do NOT repeat the current question or wait for the user to elaborate on it. Simply give the reminder and MOVE ON to the next question to maintain momentum. "
    "Only repeat a question if the answer was completely irrelevant or gibberish (e.g. random characters). "
    "Focus primarily (around 80%) on technical questions tailored strictly to the candidate's target job title provided in the context. "
    "You MUST explicitly refer to the candidate's target job title in your greeting and throughout the interview to maintain relevance. "
    "Your questions must strictly match the complexity of the chosen 'Difficulty Level'. "
    "Beginner questions should be foundational, Intermediate should be scenario-based, and Advanced should be deep-dive architecture or optimization questions. "
    "Do not ask about other roles or general questions unless they relate to this specific target role. "
    "At the end of the interview, provide a summary of the candidate's performance. "
    "In your final feedback explanation, DO NOT mention the numerical score (e.g., don't say 'You got 85/100' or 'Your score is 85'), as the user will see it in a dedicated circular display. Focus only on constructive feedback. "
    "After your feedback text, on a new line, provide the score in this exact format: 'Interview Readiness Score: XX/100'. "
    "SCORING CRITERIA: "
    "1. Technical Accuracy (40%): How correct and relevant are their answers? "
    "2. Communication & Depth (40%): Did they provide detailed explanations and technical terminology? (MANDATORY: Deduct 5-8 points from the final Readiness Score for EVERY simple or low-effort response given after a reminder). "
    "3. Role Alignment (20%): How well do their answers align with the requirements of the target job title? "
    "In the first 1-2 questions, ask the candidate to introduce themselves and confirm their interest in the target job title. "
    "Then cover professional interview methodology: algorithms & data structures, system design, language/framework expertise, databases, testing, performance, security, and best practices relevant to the role. "
    "You MUST ask exactly the number of questions specified in the 'Interview Length' context. "
    "Do NOT count the questions yourself; instead, rely strictly on the 'PROGRESS TRACKING' information provided in the context below. "
    "NEVER provide the final feedback summary or the [FINISH] tag until the 'PROGRESS TRACKING' indicates that all questions have been asked. "
    "After the candidate provides their answer to the final question (the Nth question, where N is the Interview Length), do not ask any more interview questions. "
    "Instead, your very next response must be a final closing message formatted EXACTLY as follows: "
    "1. Start with a warm thank you to the user (e.g., 'Thank you for completing the interview!'). This MUST be exactly one paragraph. "
    "2. Follow with EXACTLY two newlines (\\n\\n). "
    "3. Then provide a brief, light explanation of their performance (the feedback summary). This MUST be exactly one paragraph. "
    "4. Finally, on a new line, provide the score line: 'Interview Readiness Score: XX/100'. "
    "5. Append [FINISH] at the very end. "
    "EXAMPLE FINAL MESSAGE:\n"
    "Thank you for your time today! It was a pleasure speaking with you.\n\n"
    "You demonstrated strong technical knowledge in Python and databases, though you could improve on system design. Good luck!\n"
    "Interview Readiness Score: 85/100\n"
    "[FINISH]"
)

def interview_reply(history: List[Dict[str, str]], job_title: str = "", resume_feedback: Dict[str, Any] = None, questions_limit: int = 10, difficulty: str = "Beginner", current_asked_count: int = 0, force_end: bool = False) -> str:
    if not MISTRAL_API_KEY:
        if not history:
            prefix = f"Starting {difficulty} interview for {job_title}. " if job_title else ""
            return prefix + "Hi, thanks for joining today. To start, could you tell me about yourself?"
        return "Thanks. What interests you about this role, and how does it fit your goals?"
    
    client = Mistral(api_key=MISTRAL_API_KEY)
    
    custom_system = SYSTEM_PROMPT
    if job_title or resume_feedback or questions_limit or difficulty:
        custom_system += "\n\nCANDIDATE CONTEXT:\n"
        if job_title:
            custom_system += f"- Target Job Title: {job_title}\n"
            custom_system += f"  (CRITICAL: Always reference this role and ensure all questions are highly specific to a {job_title} professional.)\n"
        if resume_feedback:
            custom_system += f"- Resume Analysis: {resume_feedback}\n"
        if questions_limit:
            custom_system += f"- Interview Length: {questions_limit} questions.\n"
        if difficulty:
            custom_system += f"- Difficulty Level: {difficulty}\n"
            if difficulty == "Beginner":
                custom_system += "  (Focus on HR/Behavioral questions + basic technical fundamentals of the role.)\n"
            elif difficulty == "Intermediate":
                custom_system += "  (Focus on role-specific technical skills, real-world scenarios, and practical applications.)\n"
            elif difficulty == "Advanced":
                custom_system += "  (Focus on high-level system design, complex problem solving, architecture, and deep technical expertise.)\n"
        
    # Add explicit progress tracking
    remaining = questions_limit - current_asked_count
    custom_system += f"\n\nCRITICAL PROGRESS TRACKING:\n"
    custom_system += f"- Total Questions Required: {questions_limit}\n"
    custom_system += f"- Questions Asked So Far: {current_asked_count}\n"
    custom_system += f"- Questions Remaining: {remaining}\n"
    
    if force_end:
        custom_system += f"\nSTRICT RULE: The user has manually ended the session. You MUST acknowledge this and provide a brief closing message. Explain that since the interview was not completed, no Readiness Score can be generated. Do NOT provide a score line. Append [FINISH] at the end."
    elif current_asked_count < questions_limit:
        if current_asked_count == 0:
            custom_system += f"\nSTRICT RULE: This is the VERY BEGINNING of the interview. You MUST ONLY greet the user and ask the FIRST question (introduction). You are FORBIDDEN from providing a score or ending the interview now. If you mention 'Score' or 'Performance', you are failing your task."
        else:
            custom_system += f"\nSTRICT RULE: You MUST ask interview question #{current_asked_count + 1} now. You are NOT allowed to end the interview. DO NOT provide a score, DO NOT say goodbye, and DO NOT use the [FINISH] tag. If you try to end now, you are failing your task."
        custom_system += "\nWait for the user's answer before asking the next question."
    else:
        custom_system += f"\nSTRICT RULE: All {questions_limit} questions are done. The user has just answered the final question. You MUST now provide the final wrap-up: Thank you message, then feedback summary, then the score line, then [FINISH]."
        custom_system += "\nDo NOT ask any more questions."

    custom_system += "\n\nEnsure you follow the question count strictly. Do not hallucinate that the interview is over until the count reaches the limit."

    msgs = [{"role": "system", "content": custom_system}] + history
    completion = client.chat.complete(
        model="mistral-small-latest", 
        messages=msgs, 
        temperature=0.3
    )
    content = completion.choices[0].message.content
    
    # VETO: Hard-strip any premature scores if we haven't reached the limit
    if current_asked_count < questions_limit or force_end:
        import re
        content = re.sub(r"Interview Readiness Score:.*", "", content, flags=re.IGNORECASE).strip()
        if not force_end:
            content = content.replace("[FINISH]", "").strip()
        # Also strip "Performance Feedback" or similar headers if they appear prematurely
        if not force_end:
            content = re.sub(r"(Performance Feedback|Summary of Performance|Overall Feedback):.*", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
        
        # RE-PROMPT if the AI tried to end early and gave us a useless message (only for non-force-end)
        if not force_end and (not content or "?" not in content or "thank you" in content.lower() or "goodbye" in content.lower()):
            # Add a correction message and try once more
            correction_msgs = msgs + [{"role": "assistant", "content": content}]
            correction_msgs.append({
                "role": "user", 
                "content": f"[SYSTEM CORRECTION]: You tried to end the interview early or didn't ask a question. You have only asked {current_asked_count} questions out of {questions_limit}. You MUST continue. Please ask a high-quality, {difficulty}-level technical question about {job_title} now. Do NOT say goodbye."
            })
            retry_completion = client.chat.complete(
                model="mistral-small-latest", 
                messages=correction_msgs, 
                temperature=0.3
            )
            content = retry_completion.choices[0].message.content
            content = re.sub(r"Interview Readiness Score:.*", "", content, flags=re.IGNORECASE).strip()
            content = content.replace("[FINISH]", "").strip()
            content = re.sub(r"(Performance Feedback|Summary of Performance|Overall Feedback):.*", "", content, flags=re.IGNORECASE | re.DOTALL).strip()

    return content
